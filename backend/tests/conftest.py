# -*- coding: utf-8 -*-
"""测试夹具：使用独立的临时 SQLite 库，避免影响开发库。"""
import os
import tempfile

import pytest

# 必须在导入 app 之前设置环境变量（config 在导入期读取）
_TMP_DB = os.path.join(tempfile.gettempdir(), "agent_hub_test.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DB}"
os.environ["APP_SECRET"] = "test-secret-please-ignore"
os.environ["DEFAULT_ADMIN_USERNAME"] = "admin"
os.environ["DEFAULT_ADMIN_PASSWORD"] = "admin"
# 默认关闭对话同步限频，便于用例连续同步；限频行为由专门用例显式开启验证
os.environ["CONV_SYNC_MIN_INTERVAL_SECONDS"] = "0"

from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import init_db  # noqa: E402


@pytest.fixture()
def client():
    # 每个用例重建干净的库
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    init_db()
    with TestClient(app) as c:
        yield c


def login(client: TestClient, username: str, password: str) -> str:
    resp = client.post(
        "/api/auth/login",
        data={"username": username, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
