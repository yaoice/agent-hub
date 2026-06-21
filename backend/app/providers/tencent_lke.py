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
import logging
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

from ..config import settings
from .base import AppItem, BaseProvider, ConversationItem, ProviderError, SpaceItem, TokenItem
from .ssrf import assert_safe_host

logger = logging.getLogger(__name__)

VERSION = "2023-11-30"
SERVICE = "lke"
HTTP_TIMEOUT = 15
MAX_RETRIES = 2
PAGE_SIZE = 50
# ListApp 翻页安全上限（PageSize=50 时可覆盖约 2000 个应用，足够且防止排序不稳定时空转）
MAX_APP_PAGES = 40
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
        url = f"{self.scheme}://{self.host}/"
        body = json.dumps(payload, separators=(",", ":")).encode()
        if settings.provider_debug:
            logger.debug("LKE 调用 %s host=%s region=%s", action, self.host, self.region)

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
                started = time.time()
                with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:  # noqa: S310
                    data = json.loads(resp.read())
                inner = data.get("Response", {})
                if "Error" in inner:
                    err = inner["Error"]
                    # 业务错误（鉴权/参数等）记到日志，便于排障定位回退 Mock 的原因
                    logger.warning(
                        "LKE %s 返回错误：%s - %s",
                        action,
                        err.get("Code"),
                        err.get("Message"),
                    )
                    raise ProviderError(
                        f"{action} 调用失败: {err.get('Code')} - {err.get('Message')}"
                    )
                if settings.provider_debug:
                    logger.debug(
                        "LKE 调用 %s 成功，耗时 %.0f ms", action, (time.time() - started) * 1000
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
        """拉取空间下全部应用，按 AppBizId 去重。

        注意：LKE 的 ListApp 分页可能返回重复记录（排序不稳定导致相邻页重叠），
        因此不能用「原始条数凑满 Total 就停」，否则会因重复占位而漏拉真实应用。
        这里改为：翻到真正末页（某页不足一页）或已集齐 Total 个去重应用才停，
        并设页数上限与「本页 0 新增」安全阀，避免排序不稳定时空转。
        """
        apps: list[dict] = []
        seen: set[str] = set()
        for page in range(1, MAX_APP_PAGES + 1):
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
            before = len(seen)
            for a in items:
                aid = str(a.get("AppBizId") or "")
                if aid and aid in seen:
                    continue
                if aid:
                    seen.add(aid)
                apps.append(a)
            try:
                total = int(inner.get("Total") or 0)
            except (TypeError, ValueError):
                total = 0

            # 真正末页（返回不足一页）
            if len(items) < PAGE_SIZE:
                break
            # 已集齐 Total 个去重应用
            if total > 0 and len(seen) >= total:
                break
            # 安全阀：整页都是重复、没有任何新增，停止避免空转
            if len(seen) == before:
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
            intent=item.get("Intent") or "",
            intent_category=item.get("IntentCategory") or "",
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
