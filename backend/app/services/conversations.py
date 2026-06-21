# -*- coding: utf-8 -*-
"""对话记录同步：遍历项目下所有应用，拉取对话记录并去重入库。"""
from __future__ import annotations

import json
from typing import Any

from .. import models
from ..models import Project
from ..providers import mock
from ..providers.base import ConversationItem
from ..providers.registry import build_provider
from ..repositories.base import ConversationRepository
from ..security import decrypt_secret


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


def _to_record(project_id: int, app_biz_id: str, item: ConversationItem) -> models.ConversationRecord:
    return models.ConversationRecord(
        project_id=project_id,
        app_biz_id=app_biz_id,
        record_id=item.record_id,
        session_id=item.session_id,
        user_biz_id=item.user_biz_id,
        user_nickname=item.user_nickname,
        question=item.question,
        answer=item.answer,
        intent_category=item.intent_category,
        msg_create_time=item.create_time,
        raw=json.dumps(item.raw, ensure_ascii=False) if item.raw else "",
    )


def sync_conversations(
    conv_repo: ConversationRepository,
    project: Project,
    begin: str,
    end: str,
    max_records_per_app: int = 500,
) -> dict[str, Any]:
    """同步项目下所有应用的对话记录。

    返回汇总：{source, app_count, fetched, inserted}。
    任意环节失败安全回退 Mock，保证开箱可用。
    """
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
            else:
                spaces = client.fetch_spaces()
        except Exception:  # noqa: BLE001 - 回退 Mock
            client = None

    if client is None:
        source = "mock"
        spaces = mock.mock_spaces()

    apps = _collect_apps(spaces)

    # 项目级去重：一次性取出已入库的 record_id
    existing = conv_repo.existing_record_ids(project.id)
    fetched = 0
    new_records: list[models.ConversationRecord] = []
    seen_in_batch: set[str] = set()

    for app_biz_id, app_name in apps:
        try:
            if source == "live" and client is not None:
                items = client.fetch_conversations(app_biz_id, begin, end, max_records_per_app)
            else:
                items = mock.mock_conversations(app_biz_id, app_name)
        except Exception:  # noqa: BLE001 - 单个应用失败不影响其它应用
            items = []
        fetched += len(items)
        for item in items:
            rid = item.record_id
            if not rid or rid in existing or rid in seen_in_batch:
                continue
            seen_in_batch.add(rid)
            new_records.append(_to_record(project.id, app_biz_id, item))

    inserted = conv_repo.bulk_insert(new_records)
    return {
        "source": source,
        "app_count": len(apps),
        "fetched": fetched,
        "inserted": inserted,
    }
