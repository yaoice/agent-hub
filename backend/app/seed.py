# -*- coding: utf-8 -*-
"""初始化：建表 + 写入默认管理员、Provider 类型目录与一个示例项目。

dev 环境如遇旧库结构（旧 Provider 含凭证），请删除 backend/agent_hub.db 后重启重建。
"""
from sqlalchemy.orm import Session

from .config import settings
from .database import Base, SessionLocal, engine
from .models import Project, Provider, ProjectMember, User
from .providers.registry import BUILTIN_PROVIDERS
from .security import encrypt_secret, hash_password


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
    finally:
        db.close()
