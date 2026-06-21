# -*- coding: utf-8 -*-
"""腾讯云智能体平台（LKE）Provider。

复用 scripts/ 中的 TC3-HMAC-SHA256 签名逻辑，封装为可被看板调用的 Provider：
  - ListSpace / ListApp     -> 空间与应用盘点
  - DescribeTopModelToken   -> Token 消耗排行
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

from .base import AppItem, BaseProvider, ConversationItem, ProviderError, SpaceItem, TokenItem
from .ssrf import assert_safe_host

VERSION = "2023-11-30"
SERVICE = "lke"
HTTP_TIMEOUT = 15
MAX_RETRIES = 2
PAGE_SIZE = 50
CONV_PAGE_SIZE = 100


class TencentLKEProvider(BaseProvider):
    type_name = "tencent_lke"

    # ---------------- 签名 ----------------
    def _sign(self, action: str, body: bytes, ts: int) -> str:
        date = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
        signed_headers = "content-type;host;x-tc-action"
        canonical_request = (
            "POST\n/\n\n"
            f"content-type:application/json\nhost:{self.host}\nx-tc-action:{action.lower()}\n\n"
            f"{signed_headers}\n"
            f"{hashlib.sha256(body).hexdigest()}"
        )
        credential_scope = f"{date}/{SERVICE}/tc3_request"
        string_to_sign = (
            f"TC3-HMAC-SHA256\n{ts}\n{credential_scope}\n"
            f"{hashlib.sha256(canonical_request.encode()).hexdigest()}"
        )

        def _h(key: bytes, msg: str) -> bytes:
            return hmac.new(key, msg.encode(), hashlib.sha256).digest()

        k_date = _h(("TC3" + self.secret_key).encode(), date)
        k_service = _h(k_date, SERVICE)
        k_signing = _h(k_service, "tc3_request")
        signature = hmac.new(k_signing, string_to_sign.encode(), hashlib.sha256).hexdigest()
        return (
            f"TC3-HMAC-SHA256 Credential={self.secret_id}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        )

    # ---------------- HTTP ----------------
    def _call(self, action: str, payload: dict) -> dict:
        assert_safe_host(self.host)  # SSRF 防护
        url = f"https://{self.host}/"
        body = json.dumps(payload, separators=(",", ":")).encode()

        last_exc: Exception | None = None
        for attempt in range(1, MAX_RETRIES + 1):
            ts = int(time.time())
            headers = {
                "Host": self.host,
                "Content-Type": "application/json",
                "Authorization": self._sign(action, body, ts),
                "X-TC-Action": action,
                "X-TC-Version": VERSION,
                "X-TC-Timestamp": str(ts),
                "X-TC-Region": self.region,
            }
            req = urllib.request.Request(url, data=body, method="POST", headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:  # noqa: S310
                    data = json.loads(resp.read())
                inner = data.get("Response", {})
                if "Error" in inner:
                    err = inner["Error"]
                    raise ProviderError(
                        f"{action} 调用失败: {err.get('Code')} - {err.get('Message')}"
                    )
                return inner
            except urllib.error.HTTPError as exc:
                last_exc = exc
                if exc.code in (502, 503, 504) and attempt < MAX_RETRIES:
                    time.sleep(attempt)
                    continue
                raise ProviderError(f"HTTP {exc.code} 调用 {action} 失败") from exc
            except ProviderError:
                raise
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if attempt < MAX_RETRIES:
                    time.sleep(1)
                    continue
                raise ProviderError(f"网络异常: {exc}") from exc
        raise ProviderError(f"调用 {action} 失败: {last_exc}")

    # ---------------- 业务 ----------------
    def _list_spaces(self) -> list[dict]:
        inner = self._call("ListSpace", {"Region": self.region})
        return inner.get("List") or []

    def _list_apps(self, space_id: str) -> list[dict]:
        apps: list[dict] = []
        for page in range(1, 10):
            inner = self._call(
                "ListApp",
                {
                    "Region": self.region,
                    "PageNumber": page,
                    "PageSize": PAGE_SIZE,
                    "SpaceId": space_id,
                },
            )
            items = inner.get("List") or []
            apps.extend(items)
            try:
                total = int(inner.get("Total") or 0)
            except (TypeError, ValueError):
                total = 0
            if total > 0 and len(apps) >= total:
                break
            if len(items) < PAGE_SIZE:
                break
        return apps

    def fetch_spaces(self) -> list[SpaceItem]:
        if not self.has_credentials():
            raise ProviderError("未配置有效的 SECRET_ID/SECRET_KEY")
        spaces = self._list_spaces()
        result: list[SpaceItem] = []
        for sp in spaces:
            space_id = sp.get("SpaceId")
            if not space_id or space_id == "unknown":
                continue
            raw_apps = self._list_apps(space_id)
            apps = [
                AppItem(
                    name=a.get("Name", "-"),
                    status_code=int(a.get("AppStatus") or 0),
                    app_biz_id=str(a.get("AppBizId") or ""),
                )
                for a in raw_apps
            ]
            result.append(
                SpaceItem(
                    space_id=str(space_id),
                    space_name=sp.get("SpaceName") or str(space_id),
                    apps=apps,
                )
            )
        return result

    def fetch_token_top(self, dimension: int) -> list[TokenItem]:
        if not self.has_credentials():
            raise ProviderError("未配置有效的 SECRET_ID/SECRET_KEY")
        now = datetime.now()
        payload = {
            "ModelName": "",
            "StartTime": (now - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S"),
            "EndTime": now.strftime("%Y-%m-%d %H:%M:%S"),
            "SourceType": 1,
            "SpaceId": "",
            "SourceId": "0",
            "Dimension": dimension,
        }
        inner = self._call("DescribeTopModelToken", payload)
        items = inner.get("Items") or []
        out: list[TokenItem] = []
        for it in items:
            try:
                value = int(it.get("Value") or 0)
            except (TypeError, ValueError):
                value = 0
            out.append(
                TokenItem(
                    name=it.get("Name") or "-",
                    value=value,
                    percentage=float(it.get("Percentage") or 0.0),
                )
            )
        out.sort(key=lambda x: x.value, reverse=True)
        return out

    # ---------------- 对话记录 ----------------
    @staticmethod
    def _to_conversation(item: dict) -> ConversationItem:
        """将 DescribeMsgLogList 单条记录映射为统一结构（字段名做防御性兼容）。"""
        record_id = str(
            item.get("RecordId")
            or item.get("MsgRecordId")
            or item.get("RecordBizId")
            or ""
        )
        session_id = str(item.get("SessionId") or "")
        question = item.get("Question") or ""
        answer = item.get("Answer") or ""
        create_time = (item.get("CreateTime") or "")[:19]
        if not record_id:
            # 无稳定主键时，用关键字段合成一个确定性 ID，便于去重
            seed = f"{session_id}|{create_time}|{question}|{answer}"
            record_id = hashlib.md5(seed.encode("utf-8")).hexdigest()
        return ConversationItem(
            record_id=record_id,
            session_id=session_id,
            user_biz_id=str(item.get("UserBizId") or ""),
            user_nickname=item.get("UserBizNickname") or "",
            question=question,
            answer=answer,
            intent_category=item.get("IntentCategory") or item.get("Intent") or "",
            create_time=create_time,
            raw=item,
        )

    def fetch_conversations(
        self, app_biz_id: str, begin: str, end: str, max_records: int = 500
    ) -> list[ConversationItem]:
        if not self.has_credentials():
            raise ProviderError("未配置有效的 SECRET_ID/SECRET_KEY")
        if not app_biz_id:
            return []
        results: list[ConversationItem] = []
        page = 1
        while True:
            inner = self._call(
                "DescribeMsgLogList",
                {
                    "AppBizId": app_biz_id,
                    "BeginTime": begin,
                    "EndTime": end,
                    "Page": page,
                    "PageSize": CONV_PAGE_SIZE,
                    "Region": self.region,
                },
            )
            items = inner.get("List") or []
            results.extend(self._to_conversation(it) for it in items)
            try:
                total = int(inner.get("Total") or 0)
            except (TypeError, ValueError):
                total = 0
            if max_records and len(results) >= max_records:
                results = results[:max_records]
                break
            if len(items) < CONV_PAGE_SIZE:
                break
            if total and len(results) >= total:
                break
            page += 1
        return results
