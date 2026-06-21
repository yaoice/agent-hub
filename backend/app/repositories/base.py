# -*- coding: utf-8 -*-
"""仓储抽象接口（Repository Pattern）。

业务层（services/routers）只依赖这些抽象接口，不直接依赖具体 ORM 实现，
从而在更换底层存储（如 SQLite -> MySQL，或非关系实现）时对业务代码无侵入。

当前提供 SQLAlchemy 实现（见 sqlalchemy_impl.py）。
"""
from __future__ import annotations

import abc
from typing import Optional

from .. import models


class UserRepository(abc.ABC):
    @abc.abstractmethod
    def get(self, user_id: int) -> Optional[models.User]: ...

    @abc.abstractmethod
    def get_by_username(self, username: str) -> Optional[models.User]: ...

    @abc.abstractmethod
    def list(self, search: Optional[str] = None) -> list[models.User]: ...

    @abc.abstractmethod
    def add(self, username: str, password_hash: str, role: str) -> models.User: ...

    @abc.abstractmethod
    def save(self, user: models.User) -> models.User: ...

    @abc.abstractmethod
    def delete(self, user: models.User) -> None: ...

    @abc.abstractmethod
    def count_admins(self, active_only: bool = True) -> int: ...


class ProjectRepository(abc.ABC):
    @abc.abstractmethod
    def get(self, project_id: int) -> Optional[models.Project]: ...

    @abc.abstractmethod
    def get_by_name(self, name: str) -> Optional[models.Project]: ...

    @abc.abstractmethod
    def list_all(self) -> list[models.Project]: ...

    @abc.abstractmethod
    def list_for_user(self, user_id: int) -> list[models.Project]: ...

    @abc.abstractmethod
    def add(self, project: models.Project) -> models.Project: ...

    @abc.abstractmethod
    def save(self, project: models.Project) -> models.Project: ...

    @abc.abstractmethod
    def delete(self, project: models.Project) -> None: ...


class ProjectMemberRepository(abc.ABC):
    @abc.abstractmethod
    def get(self, project_id: int, user_id: int) -> Optional[models.ProjectMember]: ...

    @abc.abstractmethod
    def list_by_project(self, project_id: int) -> list[models.ProjectMember]: ...

    @abc.abstractmethod
    def list_by_user(self, user_id: int) -> list[models.ProjectMember]: ...

    @abc.abstractmethod
    def add(self, project_id: int, user_id: int, project_role: str) -> models.ProjectMember: ...

    @abc.abstractmethod
    def save(self, member: models.ProjectMember) -> models.ProjectMember: ...

    @abc.abstractmethod
    def delete(self, member: models.ProjectMember) -> None: ...


class MetricRepository(abc.ABC):
    @abc.abstractmethod
    def add_snapshot(
        self, project_id: int, metric_type: str, payload: str, source: str
    ) -> models.MetricSnapshot: ...

    @abc.abstractmethod
    def get_latest(
        self, project_id: int, metric_type: str = "dashboard"
    ) -> Optional[models.MetricSnapshot]: ...

    @abc.abstractmethod
    def list_history(
        self, project_id: int, metric_type: str = "dashboard", limit: int = 30
    ) -> list[models.MetricSnapshot]: ...


class ProviderRepository(abc.ABC):
    @abc.abstractmethod
    def list_all(self) -> list[models.Provider]: ...

    @abc.abstractmethod
    def get_by_key(self, type_key: str) -> Optional[models.Provider]: ...

    @abc.abstractmethod
    def save(self, provider: models.Provider) -> models.Provider: ...


class ConversationRepository(abc.ABC):
    @abc.abstractmethod
    def existing_record_ids(self, project_id: int) -> set[str]:
        """返回该项目已入库的所有 record_id，用于去重。"""

    @abc.abstractmethod
    def bulk_insert(self, records: list[models.ConversationRecord]) -> int:
        """批量插入并返回成功插入的条数。"""

    @abc.abstractmethod
    def list_records(
        self,
        project_id: int,
        app_biz_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        begin: Optional[str] = None,
        end: Optional[str] = None,
        keyword: Optional[str] = None,
        intent: Optional[str] = None,
    ) -> list[models.ConversationRecord]: ...

    @abc.abstractmethod
    def count(
        self,
        project_id: int,
        app_biz_id: Optional[str] = None,
        begin: Optional[str] = None,
        end: Optional[str] = None,
        keyword: Optional[str] = None,
        intent: Optional[str] = None,
    ) -> int: ...

    @abc.abstractmethod
    def list_app_ids(self, project_id: int) -> list[str]:
        """返回该项目有对话记录的 app_biz_id 去重列表（供过滤下拉）。"""
