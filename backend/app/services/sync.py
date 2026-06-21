# -*- coding: utf-8 -*-
"""项目数据同步：拉取 Provider 数据并追加一条历史快照。"""
from __future__ import annotations

import json
from typing import Any

from ..models import Project
from ..repositories.base import MetricRepository
from .normalize import (
    DASHBOARD_SCOPES,
    METRIC_TYPE,
    build_payload,
    empty_dashboard,
    fetch_dashboard_parts,
)


def sync_project(metric_repo: MetricRepository, project: Project):
    """完整同步一个项目的看板数据（应用数量 + Token）并落库。返回 (snapshot, source)。"""
    force_mock = not project.is_active
    data, source = build_payload(project, force_mock=force_mock)
    snapshot = metric_repo.add_snapshot(
        project.id, METRIC_TYPE, json.dumps(data, ensure_ascii=False), source
    )
    return snapshot, source


def sync_dashboard(metric_repo: MetricRepository, project: Project, scopes: set[str]):
    """按 scope 局部同步看板数据。

    仅拉取被请求 scope（app_count / token）对应的部分，与项目最新快照合并后
    追加一条新快照，保证看板数据始终完整。返回 (snapshot, source)。
    """
    scopes = {s for s in scopes if s in DASHBOARD_SCOPES}
    if not scopes:
        return None, "live"

    force_mock = not project.is_active
    parts, source = fetch_dashboard_parts(project, scopes, force_mock=force_mock)

    # 以最新快照为基底，仅覆盖本次拉取的部分（未选部分沿用历史）
    latest = metric_repo.get_latest(project.id, METRIC_TYPE)
    base: dict[str, Any] = json.loads(latest.payload) if latest else empty_dashboard()
    base.update(parts)

    snapshot = metric_repo.add_snapshot(
        project.id, METRIC_TYPE, json.dumps(base, ensure_ascii=False), source
    )
    return snapshot, source
