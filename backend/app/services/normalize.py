# -*- coding: utf-8 -*-
"""指标归一化：将 Provider 原始数据转换为看板使用的统一结构。

支持按同步范围（scope）局部拉取：
- "app_count"：空间/应用盘点（ListSpace + ListApp）-> overview + spaces
- "token"   ：Token 消耗排行（DescribeTopModelToken）-> token_top

同步（sync）与连通性测试共用本模块；任意环节失败回退 Mock 演示数据。
"""
from __future__ import annotations

import logging
from typing import Any

from ..models import Project
from ..providers import mock
from ..providers.base import ProviderError, SpaceItem, TokenItem
from ..providers.registry import build_provider
from ..security import decrypt_secret

logger = logging.getLogger(__name__)

STATUS_LABEL = {1: "未上线", 2: "运行中"}
TOKEN_DIMENSIONS = {1: "space", 2: "app", 3: "model"}
METRIC_TYPE = "dashboard"

# 看板同步范围标识
SCOPE_APP_COUNT = "app_count"
SCOPE_TOKEN = "token"
DASHBOARD_SCOPES = {SCOPE_APP_COUNT, SCOPE_TOKEN}


def _spaces_to_dict(spaces: list[SpaceItem]) -> dict[str, Any]:
    space_rows = []
    total_apps = running = offline = 0
    for sp in spaces:
        sp_running = sum(1 for a in sp.apps if a.status_code == 2)
        sp_offline = sum(1 for a in sp.apps if a.status_code == 1)
        total_apps += len(sp.apps)
        running += sp_running
        offline += sp_offline
        space_rows.append(
            {
                "space_id": sp.space_id,
                "space_name": sp.space_name,
                "app_count": len(sp.apps),
                "running": sp_running,
                "offline": sp_offline,
                "apps": [
                    {
                        "name": a.name,
                        "status": STATUS_LABEL.get(a.status_code, "未知"),
                        "app_biz_id": a.app_biz_id,
                    }
                    for a in sp.apps
                ],
            }
        )
    space_rows.sort(key=lambda x: x["app_count"], reverse=True)
    active = sum(1 for s in space_rows if s["app_count"] > 0)
    overview = {
        "total_spaces": len(space_rows),
        "active_spaces": active,
        "empty_spaces": len(space_rows) - active,
        "total_apps": total_apps,
        "running": running,
        "offline": offline,
    }
    return {"overview": overview, "spaces": space_rows}


def _tokens_to_dict(items: list[TokenItem]) -> list[dict[str, Any]]:
    return [{"name": it.name, "value": it.value, "percentage": it.percentage} for it in items]


def _mock_app_count() -> dict[str, Any]:
    return _spaces_to_dict(mock.mock_spaces())


def _mock_token_top() -> dict[str, Any]:
    return {
        "token_top": {
            name: _tokens_to_dict(mock.mock_token_top(dim))
            for dim, name in TOKEN_DIMENSIONS.items()
        }
    }


def empty_dashboard() -> dict[str, Any]:
    """看板数据骨架，用于无历史快照时的合并基底。"""
    return {
        "overview": {
            "total_spaces": 0,
            "active_spaces": 0,
            "empty_spaces": 0,
            "total_apps": 0,
            "running": 0,
            "offline": 0,
        },
        "spaces": [],
        "token_top": {"space": [], "app": [], "model": []},
    }


def fetch_dashboard_parts(
    project: Project, scopes: set[str], force_mock: bool = False
) -> tuple[dict[str, Any], str, list[str]]:
    """按 scope 拉取看板数据的对应部分。

    返回 (partial_data, source, errors)。partial_data 仅包含被请求 scope 对应的键：
      - app_count -> {"overview", "spaces"}
      - token     -> {"token_top"}
    source 为 "live"（全部请求部分均真实拉取成功）或 "mock"（有任意部分回退）。
    errors 为回退到 Mock 的原因列表（live 时为空），用于向用户清晰反馈失败原因。
    """
    scopes = {s for s in scopes if s in DASHBOARD_SCOPES}
    if not scopes:
        return {}, "live", []

    parts: dict[str, Any] = {}
    used_mock = False
    client = None
    errors: list[str] = []

    if force_mock:
        errors.append("项目已停用，展示 Mock 演示数据")
    else:
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
                errors.append("未配置有效的 SECRET_ID / SECRET_KEY")
        except Exception as exc:  # noqa: BLE001
            client = None
            errors.append(f"初始化 Provider 失败：{exc}")

    # 应用数量（空间/应用盘点）
    if SCOPE_APP_COUNT in scopes:
        fetched = None
        if client is not None:
            try:
                fetched = _spaces_to_dict(client.fetch_spaces())
            except Exception as exc:  # noqa: BLE001
                fetched = None
                errors.append(f"应用数量拉取失败：{exc}")
        if fetched is None:
            fetched = _mock_app_count()
            used_mock = True
        parts.update(fetched)

    # Token 消耗
    if SCOPE_TOKEN in scopes:
        token_top = None
        if client is not None:
            try:
                token_top = {
                    name: _tokens_to_dict(client.fetch_token_top(dim))
                    for dim, name in TOKEN_DIMENSIONS.items()
                }
            except Exception as exc:  # noqa: BLE001
                token_top = None
                errors.append(f"Token 消耗拉取失败：{exc}")
        if token_top is None:
            parts.update(_mock_token_top())
            used_mock = True
        else:
            parts["token_top"] = token_top

    source = "mock" if (used_mock or client is None) else "live"
    if errors:
        logger.warning(
            "项目[%s] 看板同步回退 Mock（scopes=%s）：%s",
            project.id,
            sorted(scopes),
            "；".join(errors),
        )
    return parts, source, errors


def build_payload(project: Project, force_mock: bool = False) -> tuple[dict[str, Any], str]:
    """构建完整看板数据（应用数量 + Token），用于首次惰性同步等场景。"""
    parts, source, _ = fetch_dashboard_parts(project, DASHBOARD_SCOPES, force_mock=force_mock)
    data = empty_dashboard()
    data.update(parts)
    return data, source
