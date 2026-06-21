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
    def existing_record_ids(self, project_id: int, since: Optional[str] = None) -> set[str]:
        """返回该项目已入库的 record_id 集合，用于去重。

        since 非空时仅返回 msg_create_time >= since 的记录，配合增量同步缩小内存占用。
        """

    @abc.abstractmethod
    def latest_msg_create_time(self, project_id: int) -> Optional[str]:
        """返回该项目已入库对话的最大 msg_create_time（增量同步的水位线）。"""

    @abc.abstractmethod
    def bulk_insert(self, records: list[models.ConversationRecord]) -> int:
        """幂等批量插入并返回实际新增条数（依赖唯一约束跳过重复）。"""

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
    def list_app_options(self, project_id: int) -> list[tuple[str, str]]:
        """返回该项目有对话记录的 (app_biz_id, app_name) 去重列表（供过滤下拉）。"""

    @abc.abstractmethod
    def trend_by_day(
        self,
        project_id: int,
        app_biz_id: Optional[str] = None,
        begin: Optional[str] = None,
        end: Optional[str] = None,
        keyword: Optional[str] = None,
        intent: Optional[str] = None,
    ) -> list[tuple[str, int]]:
        """按天聚合对话量，返回 [(date, count)]，按日期升序。"""

    @abc.abstractmethod
    def intent_distribution(
        self,
        project_id: int,
        app_biz_id: Optional[str] = None,
        begin: Optional[str] = None,
        end: Optional[str] = None,
        keyword: Optional[str] = None,
        intent: Optional[str] = None,
    ) -> list[tuple[str, int]]:
        """按意图分类聚合，返回 [(intent, count)]，按 count 降序。"""


class SyncJobRepository(abc.ABC):
    @abc.abstractmethod
    def create(self, project_id: int, scope: str, incremental: bool) -> models.SyncJob:
        """创建一条 pending 状态的同步任务。"""

    @abc.abstractmethod
    def get(self, job_id: int) -> Optional[models.SyncJob]:
        """按 id 获取任务。"""

    @abc.abstractmethod
    def get_for_project(self, project_id: int, job_id: int) -> Optional[models.SyncJob]:
        """按项目归属获取任务（带 project 校验）。"""

    @abc.abstractmethod
    def latest_for_project(self, project_id: int, scope: str) -> Optional[models.SyncJob]:
        """返回该项目指定范围的最近一条任务。"""

    @abc.abstractmethod
    def has_active(self, project_id: int, scope: str) -> bool:
        """是否存在 pending/running 的同步任务（用于并发互斥）。"""

    @abc.abstractmethod
    def mark_running(self, job_id: int) -> None: ...

    @abc.abstractmethod
    def update_progress(self, job_id: int, app_done: int, app_total: int, fetched: int) -> None: ...

    @abc.abstractmethod
    def mark_success(
        self,
        job_id: int,
        *,
        source: str,
        app_total: int,
        fetched: int,
        inserted: int,
        message: str,
    ) -> None: ...

    @abc.abstractmethod
    def mark_failed(self, job_id: int, error: str) -> None: ...

    @abc.abstractmethod
    def request_cancel(self, project_id: int, job_id: int) -> bool:
        """请求终止任务：仅当任务处于 pending/running 时置为 cancelling，返回是否成功。"""

    @abc.abstractmethod
    def is_cancelling(self, job_id: int) -> bool:
        """实时读取任务是否已被请求终止（供后台任务协作式检查）。"""

    @abc.abstractmethod
    def mark_cancelled(self, job_id: int, message: str) -> None:
        """将任务标记为已终止（cancelled）。"""

    @abc.abstractmethod
    def fail_active_jobs(self, error: str) -> int:
        """把所有 pending/running/cancelling 的任务标记为失败，返回处理条数。

        用于服务启动时清理上次进程残留的“僵尸任务”（进程重启后后台任务已不存在）。
        """
