# -*- coding: utf-8 -*-
"""对话记录同步：遍历项目下所有应用，拉取对话记录并去重入库。"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from typing import Any, Callable, Optional

from .. import models
from ..config import settings
from ..models import Project
from ..providers import mock
from ..providers.base import ConversationItem
from ..providers.registry import build_provider
from ..repositories.base import ConversationRepository
from ..security import decrypt_secret

logger = logging.getLogger(__name__)

# 进度回调签名：(已处理应用数, 应用总数, 累计拉取条数) -> None
ProgressCallback = Callable[[int, int, int], None]


def min_sync_interval_seconds() -> int:
    """手动对话同步的最小间隔（秒），0 表示不限制。可经环境变量配置。"""
    return settings.conv_sync_min_interval_seconds


def seconds_until_next_sync(project: Project, now: datetime | None = None) -> int:
    """返回距离允许下次同步还需等待的秒数；0 表示当前允许同步。"""
    interval = min_sync_interval_seconds()
    last = project.last_conv_synced_at
    if interval <= 0 or last is None:
        return 0
    now = now or datetime.utcnow()
    remain = interval - (now - last).total_seconds()
    return int(remain) + 1 if remain > 0 else 0


def _collect_apps(spaces) -> list[tuple[str, str]]:
    """从空间列表收集 (app_biz_id, app_name)，去掉空 id。"""
    apps: list[tuple[str, str]] = []
    seen: set[str] = set()
    for sp in spaces:
        for app in sp.apps:
            aid = (app.app_biz_id or "").strip()
            if aid and aid not in seen:
                seen.add(aid)
                apps.append((aid, app.name))
    return apps


def _to_record(
    project_id: int, app_biz_id: str, app_name: str, item: ConversationItem
) -> models.ConversationRecord:
    # raw 默认不落库以节省存储；可经 CONV_STORE_RAW 开启用于排障
    raw = json.dumps(item.raw, ensure_ascii=False) if (settings.conv_store_raw and item.raw) else ""
    return models.ConversationRecord(
        project_id=project_id,
        app_biz_id=app_biz_id,
        app_name=app_name,
        record_id=item.record_id,
        session_id=item.session_id,
        user_biz_id=item.user_biz_id,
        user_nickname=item.user_nickname,
        question=item.question,
        answer=item.answer,
        intent=item.intent,
        intent_category=item.intent_category,
        msg_create_time=item.create_time,
        raw=raw,
    )


def sync_conversations(
    conv_repo: ConversationRepository,
    project: Project,
    begin: str,
    end: str,
    max_records_per_app: int = 500,
    incremental: bool = True,
    progress_cb: Optional[ProgressCallback] = None,
    should_cancel: Optional[Callable[[], bool]] = None,
) -> dict[str, Any]:
    """同步项目下所有应用的对话记录。

    incremental=True（默认）：以已入库的最大 msg_create_time 作为本次起点（不早于传入
        begin），只拉新增量，显著降低单次同步的拉取量与去重内存占用。
    incremental=False：按传入 begin 全量回补。
    progress_cb：可选进度回调，每处理完一个应用回报 (已完成, 总数, 累计拉取)。
    should_cancel：可选终止判断回调，遍历每个应用前检查；返回 True 则提前停止并回写已拉取部分。

    返回汇总：{source, app_count, fetched, inserted, begin, incremental, cancelled}。
    任意环节失败安全回退 Mock，保证开箱可用。
    """
    # 计算本次有效起点：增量模式下取 max(传入 begin, 已入库水位线)
    effective_begin = begin
    if incremental:
        watermark = conv_repo.latest_msg_create_time(project.id)
        if watermark and watermark > begin:
            effective_begin = watermark

    force_mock = not project.is_active
    client = None
    source = "live"
    spaces = []

    if not force_mock:
        try:
            secret_key = decrypt_secret(project.secret_key_enc)
            client = build_provider(
                project.provider_type_key,
                project.secret_id,
                secret_key,
                project.host,
                project.region,
            )
            if not client.has_credentials():
                client = None
                logger.warning(
                    "项目[%s] 未配置有效 SECRET_ID/SECRET_KEY，对话同步回退 Mock",
                    project.id,
                )
            else:
                spaces = client.fetch_spaces()
        except Exception as exc:  # noqa: BLE001 - 回退 Mock
            client = None
            logger.warning(
                "项目[%s] 初始化 Provider 或拉取空间失败，对话同步回退 Mock：%s",
                project.id,
                exc,
            )
    else:
        logger.info("项目[%s] 已停用，对话同步使用 Mock 数据", project.id)

    if client is None:
        source = "mock"
        spaces = mock.mock_spaces()

    apps = _collect_apps(spaces)
    total = len(apps)
    # 应用间限速：仅实时拉取时生效，避免触发云端 QPS 限制
    delay = settings.conv_sync_app_delay_ms / 1000.0 if source == "live" else 0.0

    # 项目级去重：增量模式仅取水位线之后的 record_id，降低内存占用
    existing = conv_repo.existing_record_ids(
        project.id, since=effective_begin if incremental else None
    )
    fetched = 0
    new_records: list[models.ConversationRecord] = []
    seen_in_batch: set[str] = set()
    cancelled = False

    for idx, (app_biz_id, app_name) in enumerate(apps):
        # 协作式终止：每个应用开始前检查一次，被请求终止则保留已拉取部分并停止
        if should_cancel is not None and should_cancel():
            cancelled = True
            logger.info("项目[%s] 对话同步收到终止请求，已处理 %s/%s 个应用", project.id, idx, total)
            break
        if delay and idx > 0:
            time.sleep(delay)
        try:
            if source == "live" and client is not None:
                items = client.fetch_conversations(
                    app_biz_id, effective_begin, end, max_records_per_app
                )
            else:
                items = mock.mock_conversations(app_biz_id, app_name)
        except Exception as exc:  # noqa: BLE001 - 单个应用失败不影响其它应用
            items = []
            logger.warning(
                "项目[%s] 应用[%s] 拉取对话失败，已跳过该应用：%s",
                project.id,
                app_biz_id,
                exc,
            )
        fetched += len(items)
        for item in items:
            rid = item.record_id
            if not rid or rid in existing or rid in seen_in_batch:
                continue
            seen_in_batch.add(rid)
            new_records.append(_to_record(project.id, app_biz_id, app_name, item))
        if progress_cb is not None:
            progress_cb(idx + 1, total, fetched)

    inserted = conv_repo.bulk_insert(new_records)
    # 更新同步水位时间（由调用方负责持久化 project），用于限频与下次增量
    project.last_conv_synced_at = datetime.utcnow()
    logger.info(
        "项目[%s] 对话同步%s（%s/%s）：%s 个应用，拉取 %s 条，新增 %s 条，起点 %s",
        project.id,
        "已终止" if cancelled else "完成",
        source,
        "增量" if incremental else "全量",
        total,
        fetched,
        inserted,
        effective_begin,
    )
    return {
        "source": source,
        "app_count": total,
        "fetched": fetched,
        "inserted": inserted,
        "begin": effective_begin,
        "incremental": incremental,
        "cancelled": cancelled,
    }
