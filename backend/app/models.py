# -*- coding: utf-8 -*-
"""数据模型：用户、Provider 类型目录、项目、项目成员、看板指标快照。

设计要点（见 docs/plans/2026-06-21-admin-panel-projects-design.md）：
- Provider 仅为「类型目录」，不再持有凭证。
- 凭证（SECRET_ID/SECRET_KEY/HOST/region）挂在 Project 上。
- 用户经 ProjectMember 多对多关联项目，带项目级角色。
- 每次同步向 MetricSnapshot 追加一条历史快照。
- 类型选择通用，避免 SQLite 特有特性，便于切换 MySQL。
"""
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    # 全局角色：admin / user
    role: Mapped[str] = mapped_column(String(16), default="user", nullable=False)
    # 是否启用；禁用后无法登录、已签发 token 立即失效
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    memberships: Mapped[list["ProjectMember"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Provider(Base):
    """Provider 类型目录（无凭证）。

    type_key 为后端代码注册的实现标识；display_name 为前端展示名。
    implemented=False 表示尚未实现（前端置灰、不可启用）。
    """

    __tablename__ = "providers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    type_key: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(64), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    implemented: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    description: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Project(Base):
    """项目：选择一个 Provider 类型，并持有自己的访问凭证与成员。"""

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    # 引用 Provider.type_key
    provider_type_key: Mapped[str] = mapped_column(String(32), nullable=False)
    host: Mapped[str] = mapped_column(String(255), nullable=False)
    secret_id: Mapped[str] = mapped_column(String(255), nullable=False)
    # 加密存储（Fernet 密文）
    secret_key_enc: Mapped[str] = mapped_column(Text, nullable=False)
    region: Mapped[str] = mapped_column(String(32), default="1")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # 对话记录最近一次成功同步时间（UTC），用于手动同步的最小间隔限频与增量起点
    last_conv_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, default=None
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    members: Mapped[list["ProjectMember"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    snapshots: Mapped[list["MetricSnapshot"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class ProjectMember(Base):
    """项目成员关系（多对多）+ 项目级角色。"""

    __tablename__ = "project_members"
    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uq_project_user"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    # 项目级角色：project_admin / member
    project_role: Mapped[str] = mapped_column(String(16), default="member", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    project: Mapped["Project"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship(back_populates="memberships")


class MetricSnapshot(Base):
    """看板指标快照：每次同步追加一条带时间戳记录（保留历史）。"""

    __tablename__ = "metric_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    metric_type: Mapped[str] = mapped_column(String(32), default="dashboard", nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    # 数据来源：live / mock
    source: Mapped[str] = mapped_column(String(16), default="live")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )

    project: Mapped["Project"] = relationship(back_populates="snapshots")


class ConversationRecord(Base):
    """对话记录明细：按 (project, app) 维度逐条入库，支持去重与分页查询。"""

    __tablename__ = "conversation_records"
    __table_args__ = (
        UniqueConstraint("project_id", "record_id", name="uq_conv_record"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    app_biz_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    # 来源记录唯一标识（API 主键或合成哈希），用于幂等去重
    record_id: Mapped[str] = mapped_column(String(128), nullable=False)
    session_id: Mapped[str] = mapped_column(String(128), default="")
    user_biz_id: Mapped[str] = mapped_column(String(128), default="")
    user_nickname: Mapped[str] = mapped_column(String(128), default="")
    question: Mapped[str] = mapped_column(Text, default="")
    answer: Mapped[str] = mapped_column(Text, default="")
    intent_category: Mapped[str] = mapped_column(String(128), default="")
    # 对话发生时间（保留接口返回的原始字符串）
    msg_create_time: Mapped[str] = mapped_column(String(32), default="", index=True)
    raw: Mapped[str] = mapped_column(Text, default="")
    synced_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    project: Mapped["Project"] = relationship()


class SyncJob(Base):
    """异步同步任务：记录一次后台同步的进度与结果，供前端轮询。"""

    __tablename__ = "sync_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    # 任务范围（当前仅 conversations）
    scope: Mapped[str] = mapped_column(String(32), default="conversations", nullable=False)
    # 状态：pending / running / success / failed
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True, nullable=False)
    incremental: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # 进度：已处理应用 / 应用总数；以及累计拉取与新增入库
    app_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    app_done: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    fetched: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    inserted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    source: Mapped[str] = mapped_column(String(16), default="")  # live / mock
    message: Mapped[str] = mapped_column(Text, default="")
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)

    project: Mapped["Project"] = relationship()
