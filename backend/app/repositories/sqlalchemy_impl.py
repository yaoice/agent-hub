# -*- coding: utf-8 -*-
"""仓储接口的 SQLAlchemy 实现。

仅使用通用 SQL 语义（参数绑定 + 标准类型），可直接用于 SQLite 与 MySQL。
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import models
from . import base


class SqlAlchemyUserRepository(base.UserRepository):
    def __init__(self, db: Session):
        self.db = db

    def get(self, user_id: int) -> Optional[models.User]:
        return self.db.get(models.User, user_id)

    def get_by_username(self, username: str) -> Optional[models.User]:
        return self.db.scalar(select(models.User).where(models.User.username == username))

    def list(self, search: Optional[str] = None) -> list[models.User]:
        stmt = select(models.User)
        if search:
            like = f"%{search.strip()}%"
            stmt = stmt.where(models.User.username.like(like))
        stmt = stmt.order_by(models.User.id)
        return list(self.db.scalars(stmt).all())

    def add(self, username: str, password_hash: str, role: str) -> models.User:
        user = models.User(username=username, password_hash=password_hash, role=role)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def save(self, user: models.User) -> models.User:
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def delete(self, user: models.User) -> None:
        self.db.delete(user)
        self.db.commit()

    def count_admins(self, active_only: bool = True) -> int:
        stmt = select(func.count()).select_from(models.User).where(models.User.role == "admin")
        if active_only:
            stmt = stmt.where(models.User.is_active.is_(True))
        return int(self.db.scalar(stmt) or 0)


class SqlAlchemyProjectRepository(base.ProjectRepository):
    def __init__(self, db: Session):
        self.db = db

    def get(self, project_id: int) -> Optional[models.Project]:
        return self.db.get(models.Project, project_id)

    def get_by_name(self, name: str) -> Optional[models.Project]:
        return self.db.scalar(select(models.Project).where(models.Project.name == name))

    def list_all(self) -> list[models.Project]:
        return list(self.db.scalars(select(models.Project).order_by(models.Project.id)).all())

    def list_for_user(self, user_id: int) -> list[models.Project]:
        stmt = (
            select(models.Project)
            .join(models.ProjectMember, models.ProjectMember.project_id == models.Project.id)
            .where(models.ProjectMember.user_id == user_id)
            .order_by(models.Project.id)
        )
        return list(self.db.scalars(stmt).all())

    def add(self, project: models.Project) -> models.Project:
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)
        return project

    def save(self, project: models.Project) -> models.Project:
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)
        return project

    def delete(self, project: models.Project) -> None:
        self.db.delete(project)
        self.db.commit()


class SqlAlchemyProjectMemberRepository(base.ProjectMemberRepository):
    def __init__(self, db: Session):
        self.db = db

    def get(self, project_id: int, user_id: int) -> Optional[models.ProjectMember]:
        return self.db.scalar(
            select(models.ProjectMember).where(
                models.ProjectMember.project_id == project_id,
                models.ProjectMember.user_id == user_id,
            )
        )

    def list_by_project(self, project_id: int) -> list[models.ProjectMember]:
        return list(
            self.db.scalars(
                select(models.ProjectMember)
                .where(models.ProjectMember.project_id == project_id)
                .order_by(models.ProjectMember.id)
            ).all()
        )

    def list_by_user(self, user_id: int) -> list[models.ProjectMember]:
        return list(
            self.db.scalars(
                select(models.ProjectMember).where(models.ProjectMember.user_id == user_id)
            ).all()
        )

    def add(self, project_id: int, user_id: int, project_role: str) -> models.ProjectMember:
        member = models.ProjectMember(
            project_id=project_id, user_id=user_id, project_role=project_role
        )
        self.db.add(member)
        self.db.commit()
        self.db.refresh(member)
        return member

    def save(self, member: models.ProjectMember) -> models.ProjectMember:
        self.db.add(member)
        self.db.commit()
        self.db.refresh(member)
        return member

    def delete(self, member: models.ProjectMember) -> None:
        self.db.delete(member)
        self.db.commit()


class SqlAlchemyMetricRepository(base.MetricRepository):
    def __init__(self, db: Session):
        self.db = db

    def add_snapshot(
        self, project_id: int, metric_type: str, payload: str, source: str
    ) -> models.MetricSnapshot:
        snap = models.MetricSnapshot(
            project_id=project_id, metric_type=metric_type, payload=payload, source=source
        )
        self.db.add(snap)
        self.db.commit()
        self.db.refresh(snap)
        return snap

    def get_latest(
        self, project_id: int, metric_type: str = "dashboard"
    ) -> Optional[models.MetricSnapshot]:
        return self.db.scalar(
            select(models.MetricSnapshot)
            .where(
                models.MetricSnapshot.project_id == project_id,
                models.MetricSnapshot.metric_type == metric_type,
            )
            .order_by(models.MetricSnapshot.created_at.desc(), models.MetricSnapshot.id.desc())
            .limit(1)
        )

    def list_history(
        self, project_id: int, metric_type: str = "dashboard", limit: int = 30
    ) -> list[models.MetricSnapshot]:
        return list(
            self.db.scalars(
                select(models.MetricSnapshot)
                .where(
                    models.MetricSnapshot.project_id == project_id,
                    models.MetricSnapshot.metric_type == metric_type,
                )
                .order_by(models.MetricSnapshot.created_at.desc(), models.MetricSnapshot.id.desc())
                .limit(limit)
            ).all()
        )


class SqlAlchemyProviderRepository(base.ProviderRepository):
    def __init__(self, db: Session):
        self.db = db

    def list_all(self) -> list[models.Provider]:
        return list(self.db.scalars(select(models.Provider).order_by(models.Provider.id)).all())

    def get_by_key(self, type_key: str) -> Optional[models.Provider]:
        return self.db.scalar(select(models.Provider).where(models.Provider.type_key == type_key))

    def save(self, provider: models.Provider) -> models.Provider:
        self.db.add(provider)
        self.db.commit()
        self.db.refresh(provider)
        return provider


class SqlAlchemyConversationRepository(base.ConversationRepository):
    def __init__(self, db: Session):
        self.db = db

    def existing_record_ids(self, project_id: int, since: Optional[str] = None) -> set[str]:
        stmt = select(models.ConversationRecord.record_id).where(
            models.ConversationRecord.project_id == project_id
        )
        if since:
            # 增量场景仅取水位线之后的记录，避免把项目全量 record_id 载入内存
            stmt = stmt.where(models.ConversationRecord.msg_create_time >= since)
        rows = self.db.scalars(stmt).all()
        return set(rows)

    def latest_msg_create_time(self, project_id: int) -> Optional[str]:
        value = self.db.scalar(
            select(func.max(models.ConversationRecord.msg_create_time)).where(
                models.ConversationRecord.project_id == project_id,
                models.ConversationRecord.msg_create_time != "",
            )
        )
        return value or None

    def bulk_insert(self, records: list[models.ConversationRecord]) -> int:
        if not records:
            return 0
        # 正常路径：批量插入。冲突（并发/重复 record_id）时回退逐条幂等插入。
        try:
            self.db.add_all(records)
            self.db.commit()
            return len(records)
        except IntegrityError:
            self.db.rollback()

        inserted = 0
        for rec in records:
            try:
                with self.db.begin_nested():
                    self.db.add(rec)
                    self.db.flush()
                inserted += 1
            except IntegrityError:
                # 命中唯一约束 uq_conv_record，视为已存在，跳过
                continue
        self.db.commit()
        return inserted

    def _apply_filters(
        self,
        stmt,
        app_biz_id: Optional[str],
        begin: Optional[str],
        end: Optional[str],
        keyword: Optional[str],
        intent: Optional[str],
    ):
        """统一拼装过滤条件。

        - 字符串均走参数绑定（SQLAlchemy 表达式），避免 SQL 注入。
        - msg_create_time 为 "YYYY-MM-DD HH:MM:SS" 字符串，按字典序比较等价于时间序。
        """
        C = models.ConversationRecord
        if app_biz_id:
            stmt = stmt.where(C.app_biz_id == app_biz_id)
        if begin:
            stmt = stmt.where(C.msg_create_time >= begin)
        if end:
            stmt = stmt.where(C.msg_create_time <= end)
        if intent:
            stmt = stmt.where(C.intent_category == intent)
        if keyword:
            kw = keyword.strip()
            if kw:
                like = f"%{kw}%"
                stmt = stmt.where(or_(C.question.like(like), C.answer.like(like)))
        return stmt

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
    ) -> list[models.ConversationRecord]:
        stmt = select(models.ConversationRecord).where(
            models.ConversationRecord.project_id == project_id
        )
        stmt = self._apply_filters(stmt, app_biz_id, begin, end, keyword, intent)
        stmt = (
            stmt.order_by(
                models.ConversationRecord.msg_create_time.desc(),
                models.ConversationRecord.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.scalars(stmt).all())

    def count(
        self,
        project_id: int,
        app_biz_id: Optional[str] = None,
        begin: Optional[str] = None,
        end: Optional[str] = None,
        keyword: Optional[str] = None,
        intent: Optional[str] = None,
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(models.ConversationRecord)
            .where(models.ConversationRecord.project_id == project_id)
        )
        stmt = self._apply_filters(stmt, app_biz_id, begin, end, keyword, intent)
        return int(self.db.scalar(stmt) or 0)

    def list_app_options(self, project_id: int) -> list[tuple[str, str]]:
        C = models.ConversationRecord
        # 同一 app_biz_id 可能存在历史空 app_name 与新值，取非空名称的最大值兜底
        rows = self.db.execute(
            select(C.app_biz_id, func.max(C.app_name))
            .where(C.project_id == project_id)
            .group_by(C.app_biz_id)
            .order_by(C.app_biz_id)
        ).all()
        return [(aid, name or "") for aid, name in rows if aid]

    def trend_by_day(
        self,
        project_id: int,
        app_biz_id: Optional[str] = None,
        begin: Optional[str] = None,
        end: Optional[str] = None,
        keyword: Optional[str] = None,
        intent: Optional[str] = None,
    ) -> list[tuple[str, int]]:
        C = models.ConversationRecord
        # msg_create_time 为 "YYYY-MM-DD HH:MM:SS"，截前 10 位即日期（SQLite/MySQL 通用 substr）
        day = func.substr(C.msg_create_time, 1, 10)
        stmt = (
            select(day.label("day"), func.count().label("cnt"))
            .where(C.project_id == project_id, C.msg_create_time != "")
        )
        stmt = self._apply_filters(stmt, app_biz_id, begin, end, keyword, intent)
        stmt = stmt.group_by(day).order_by(day.asc())
        return [(row.day, int(row.cnt)) for row in self.db.execute(stmt).all()]

    def intent_distribution(
        self,
        project_id: int,
        app_biz_id: Optional[str] = None,
        begin: Optional[str] = None,
        end: Optional[str] = None,
        keyword: Optional[str] = None,
        intent: Optional[str] = None,
    ) -> list[tuple[str, int]]:
        C = models.ConversationRecord
        stmt = select(C.intent_category.label("intent"), func.count().label("cnt")).where(
            C.project_id == project_id
        )
        stmt = self._apply_filters(stmt, app_biz_id, begin, end, keyword, intent)
        stmt = stmt.group_by(C.intent_category).order_by(func.count().desc())
        return [
            ((row.intent or "未分类"), int(row.cnt))
            for row in self.db.execute(stmt).all()
        ]


class SqlAlchemySyncJobRepository(base.SyncJobRepository):
    def __init__(self, db: Session):
        self.db = db

    def create(self, project_id: int, scope: str, incremental: bool) -> models.SyncJob:
        job = models.SyncJob(project_id=project_id, scope=scope, incremental=incremental)
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def get(self, job_id: int) -> Optional[models.SyncJob]:
        return self.db.get(models.SyncJob, job_id)

    def get_for_project(self, project_id: int, job_id: int) -> Optional[models.SyncJob]:
        job = self.db.get(models.SyncJob, job_id)
        if job is None or job.project_id != project_id:
            return None
        return job

    def latest_for_project(self, project_id: int, scope: str) -> Optional[models.SyncJob]:
        return self.db.scalar(
            select(models.SyncJob)
            .where(models.SyncJob.project_id == project_id, models.SyncJob.scope == scope)
            .order_by(models.SyncJob.id.desc())
            .limit(1)
        )

    def has_active(self, project_id: int, scope: str) -> bool:
        count = self.db.scalar(
            select(func.count())
            .select_from(models.SyncJob)
            .where(
                models.SyncJob.project_id == project_id,
                models.SyncJob.scope == scope,
                models.SyncJob.status.in_(("pending", "running", "cancelling")),
            )
        )
        return bool(count)

    def mark_running(self, job_id: int) -> None:
        job = self.db.get(models.SyncJob, job_id)
        if job is None:
            return
        job.status = "running"
        self.db.commit()

    def update_progress(self, job_id: int, app_done: int, app_total: int, fetched: int) -> None:
        job = self.db.get(models.SyncJob, job_id)
        if job is None:
            return
        job.app_done = app_done
        job.app_total = app_total
        job.fetched = fetched
        self.db.commit()

    def mark_success(
        self,
        job_id: int,
        *,
        source: str,
        app_total: int,
        fetched: int,
        inserted: int,
        message: str,
    ) -> None:
        job = self.db.get(models.SyncJob, job_id)
        if job is None:
            return
        job.status = "success"
        job.source = source
        job.app_total = app_total
        job.app_done = app_total
        job.fetched = fetched
        job.inserted = inserted
        job.message = message
        job.finished_at = datetime.utcnow()
        self.db.commit()

    def mark_failed(self, job_id: int, error: str) -> None:
        job = self.db.get(models.SyncJob, job_id)
        if job is None:
            return
        job.status = "failed"
        job.error = error[:2000]
        job.finished_at = datetime.utcnow()
        self.db.commit()

    def request_cancel(self, project_id: int, job_id: int) -> bool:
        job = self.db.get(models.SyncJob, job_id)
        if job is None or job.project_id != project_id:
            return False
        if job.status not in ("pending", "running"):
            return False
        job.status = "cancelling"
        self.db.commit()
        return True

    def is_cancelling(self, job_id: int) -> bool:
        # 用独立标量查询读取最新状态（避免身份映射缓存），供后台任务每个应用检查一次
        status = self.db.scalar(
            select(models.SyncJob.status).where(models.SyncJob.id == job_id)
        )
        return status == "cancelling"

    def mark_cancelled(self, job_id: int, message: str) -> None:
        job = self.db.get(models.SyncJob, job_id)
        if job is None:
            return
        job.status = "cancelled"
        job.message = message
        job.finished_at = datetime.utcnow()
        self.db.commit()

    def fail_active_jobs(self, error: str) -> int:
        res = self.db.execute(
            update(models.SyncJob)
            .where(models.SyncJob.status.in_(("pending", "running", "cancelling")))
            .values(status="failed", error=error[:2000], finished_at=datetime.utcnow())
        )
        self.db.commit()
        return res.rowcount or 0
