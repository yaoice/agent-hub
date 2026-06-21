# -*- coding: utf-8 -*-
"""仓储接口的 SQLAlchemy 实现。

仅使用通用 SQL 语义（参数绑定 + 标准类型），可直接用于 SQLite 与 MySQL。
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import func, or_, select
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

    def existing_record_ids(self, project_id: int) -> set[str]:
        rows = self.db.scalars(
            select(models.ConversationRecord.record_id).where(
                models.ConversationRecord.project_id == project_id
            )
        ).all()
        return set(rows)

    def bulk_insert(self, records: list[models.ConversationRecord]) -> int:
        if not records:
            return 0
        self.db.add_all(records)
        self.db.commit()
        return len(records)

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

    def list_app_ids(self, project_id: int) -> list[str]:
        rows = self.db.scalars(
            select(models.ConversationRecord.app_biz_id)
            .where(models.ConversationRecord.project_id == project_id)
            .distinct()
            .order_by(models.ConversationRecord.app_biz_id)
        ).all()
        return [r for r in rows if r]

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
