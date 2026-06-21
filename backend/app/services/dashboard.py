# -*- coding: utf-8 -*-
"""看板读取服务：从库中读取项目最新快照。"""
from __future__ import annotations

import json
from typing import Any

from ..models import Project
from ..repositories.base import MetricRepository
from .normalize import METRIC_TYPE
from .sync import sync_project


def get_dashboard(metric_repo: MetricRepository, project: Project) -> dict[str, Any]:
    """读取项目最新快照。若尚无任何快照，则惰性同步一次再返回。"""
    latest = metric_repo.get_latest(project.id, METRIC_TYPE)
    if latest is None:
        # 首次访问：自动同步一次，保证看板开箱即用
        latest, _ = sync_project(metric_repo, project)
    return {
        "source": latest.source,
        "updated_at": latest.created_at,
        "data": json.loads(latest.payload),
    }
