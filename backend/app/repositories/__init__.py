# -*- coding: utf-8 -*-
"""仓储工厂：按配置返回对应后端的仓储实现。

业务层通过 get_*_repository(db) 获取抽象接口实例，未来新增其它存储实现时，
只需在此登记并通过 REPOSITORY_BACKEND 配置切换，业务代码无需改动。
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..config import settings
from .base import (
    ConversationRepository,
    MetricRepository,
    ProjectMemberRepository,
    ProjectRepository,
    ProviderRepository,
    UserRepository,
)
from .sqlalchemy_impl import (
    SqlAlchemyConversationRepository,
    SqlAlchemyMetricRepository,
    SqlAlchemyProjectMemberRepository,
    SqlAlchemyProjectRepository,
    SqlAlchemyProviderRepository,
    SqlAlchemyUserRepository,
)

# 已登记的后端实现集合。新增存储后端时在此追加一项即可。
_BACKENDS = {
    "sqlalchemy": {
        "user": SqlAlchemyUserRepository,
        "project": SqlAlchemyProjectRepository,
        "project_member": SqlAlchemyProjectMemberRepository,
        "metric": SqlAlchemyMetricRepository,
        "provider": SqlAlchemyProviderRepository,
        "conversation": SqlAlchemyConversationRepository,
    },
}


def _impls() -> dict:
    backend = settings.repository_backend
    if backend not in _BACKENDS:
        raise ValueError(f"未知的 REPOSITORY_BACKEND: {backend}")
    return _BACKENDS[backend]


def get_user_repository(db: Session) -> UserRepository:
    return _impls()["user"](db)


def get_project_repository(db: Session) -> ProjectRepository:
    return _impls()["project"](db)


def get_project_member_repository(db: Session) -> ProjectMemberRepository:
    return _impls()["project_member"](db)


def get_metric_repository(db: Session) -> MetricRepository:
    return _impls()["metric"](db)


def get_provider_repository(db: Session) -> ProviderRepository:
    return _impls()["provider"](db)


def get_conversation_repository(db: Session) -> ConversationRepository:
    return _impls()["conversation"](db)


__all__ = [
    "UserRepository",
    "ProjectRepository",
    "ProjectMemberRepository",
    "MetricRepository",
    "ProviderRepository",
    "ConversationRepository",
    "get_user_repository",
    "get_project_repository",
    "get_project_member_repository",
    "get_metric_repository",
    "get_provider_repository",
    "get_conversation_repository",
]
