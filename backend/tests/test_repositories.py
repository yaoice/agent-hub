# -*- coding: utf-8 -*-
"""仓储层单元测试：快照追加与读取最新。"""
import os
import tempfile

os.environ.setdefault(
    "DATABASE_URL", f"sqlite:///{os.path.join(tempfile.gettempdir(), 'agent_hub_test.db')}"
)
os.environ.setdefault("APP_SECRET", "test-secret-please-ignore")

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.models import Project  # noqa: E402
from app.repositories import get_metric_repository  # noqa: E402
from app.security import encrypt_secret  # noqa: E402


def _fresh_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    return SessionLocal()


def test_metric_snapshot_history_and_latest():
    db = _fresh_db()
    try:
        project = Project(
            name="p1",
            provider_type_key="tencent_lke",
            host="example.com",
            secret_id="x",
            secret_key_enc=encrypt_secret("y"),
        )
        db.add(project)
        db.commit()
        db.refresh(project)

        repo = get_metric_repository(db)
        repo.add_snapshot(project.id, "dashboard", '{"v": 1}', "mock")
        latest = repo.add_snapshot(project.id, "dashboard", '{"v": 2}', "live")

        # 最新一条应为第二次写入
        got = repo.get_latest(project.id, "dashboard")
        assert got is not None
        assert got.id == latest.id
        assert got.source == "live"

        # 历史保留两条
        history = repo.list_history(project.id, "dashboard", limit=10)
        assert len(history) == 2
    finally:
        db.close()
