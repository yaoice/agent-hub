# -*- coding: utf-8 -*-
"""初始化：建表 + 写入默认管理员、Provider 类型目录与一个示例项目。

dev 环境如遇旧库结构（旧 Provider 含凭证），请删除 backend/agent_hub.db 后重启重建。
"""
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from .config import settings
from .database import Base, SessionLocal, engine
from .models import Project, Provider, ProjectMember, User
from .providers.registry import BUILTIN_PROVIDERS
from .repositories import get_sync_job_repository
from .security import encrypt_secret, hash_password


def _ensure_schema() -> None:
    """轻量补列：为已存在的旧库追加新增字段，避免必须删库重建。

    仅做向后兼容的 ADD COLUMN（SQLite/MySQL 通用），不改动既有数据。
    """
    inspector = inspect(engine)
    if "projects" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("projects")}
    if "last_conv_synced_at" not in columns:
        with engine.begin() as conn:
            conn.execute(
                text("ALTER TABLE projects ADD COLUMN last_conv_synced_at DATETIME")
            )

    # 对话记录表：补充 app_name / intent 列（旧库兼容）
    if "conversation_records" in inspector.get_table_names():
        conv_cols = {col["name"] for col in inspector.get_columns("conversation_records")}
        with engine.begin() as conn:
            if "app_name" not in conv_cols:
                conn.execute(
                    text("ALTER TABLE conversation_records ADD COLUMN app_name VARCHAR(256) DEFAULT ''")
                )
            if "intent" not in conv_cols:
                conn.execute(
                    text("ALTER TABLE conversation_records ADD COLUMN intent VARCHAR(256) DEFAULT ''")
                )


def _seed_providers(db: Session) -> None:
    """写入/补齐内置 Provider 类型目录（按 type_key 幂等）。"""
    existing = {p.type_key for p in db.query(Provider).all()}
    for item in BUILTIN_PROVIDERS:
        if item["type_key"] in existing:
            continue
        db.add(
            Provider(
                type_key=item["type_key"],
                display_name=item["display_name"],
                # 已实现的默认启用；未实现的默认禁用
                enabled=item["implemented"],
                implemented=item["implemented"],
                description=item["description"],
            )
        )
    db.commit()


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _ensure_schema()
    db: Session = SessionLocal()
    try:
        # 默认管理员
        admin = (
            db.query(User).filter(User.username == settings.default_admin_username).first()
        )
        if not admin:
            admin = User(
                username=settings.default_admin_username,
                password_hash=hash_password(settings.default_admin_password),
                role="admin",
                is_active=True,
            )
            db.add(admin)
            db.commit()
            db.refresh(admin)

        # Provider 类型目录
        _seed_providers(db)

        # 示例项目（无有效密钥 -> 同步自动回退 Mock 演示数据），并把 admin 设为项目管理员
        if db.query(Project).count() == 0:
            project = Project(
                name="智能体示例项目",
                provider_type_key="tencent_lke",
                host="aiagent.example.com",
                region="1",
                is_active=True,
                secret_id="<SECRET_ID>",
                secret_key_enc=encrypt_secret("<SECRET_KEY>"),
            )
            db.add(project)
            db.commit()
            db.refresh(project)
            db.add(
                ProjectMember(
                    project_id=project.id, user_id=admin.id, project_role="project_admin"
                )
            )
            db.commit()

        # 清理上次进程残留的“僵尸”同步任务：进程重启后后台任务已不存在，
        # 仍处于 pending/running/cancelling 的任务永远不会结束，会阻塞后续同步并卡死前端进度。
        n = get_sync_job_repository(db).fail_active_jobs("服务重启，任务已中断")
        if n:
            import logging

            logging.getLogger("app.seed").warning("启动清理 %s 个残留同步任务", n)
    finally:
        db.close()
