# -*- coding: utf-8 -*-
"""API 集成测试：用户管理、项目、成员、同步、看板可见性。"""
from conftest import auth_headers, login


def test_login_and_me_returns_projects(client):
    token = login(client, "admin", "admin")
    me = client.get("/api/auth/me", headers=auth_headers(token)).json()
    assert me["role"] == "admin"
    # seed 已建一个示例项目，admin 可见
    assert len(me["projects"]) >= 1


def test_create_user_and_cannot_disable_self(client):
    token = login(client, "admin", "admin")
    h = auth_headers(token)

    # 新增普通用户
    resp = client.post(
        "/api/users",
        json={"username": "alice", "password": "secret", "role": "user"},
        headers=h,
    )
    assert resp.status_code == 201, resp.text
    alice_id = resp.json()["id"]

    # admin 不能禁用自己
    me = client.get("/api/auth/me", headers=h).json()
    resp = client.patch(
        f"/api/users/{me['id']}/status", json={"is_active": False}, headers=h
    )
    assert resp.status_code == 400

    # 禁用 alice 后，alice 无法登录
    client.patch(f"/api/users/{alice_id}/status", json={"is_active": False}, headers=h)
    bad = client.post(
        "/api/auth/login",
        data={"username": "alice", "password": "secret"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert bad.status_code == 403


def test_last_admin_protection(client):
    token = login(client, "admin", "admin")
    h = auth_headers(token)
    me = client.get("/api/auth/me", headers=h).json()
    # 仅有一个 admin，禁止降级
    resp = client.put(f"/api/users/{me['id']}", json={"role": "user"}, headers=h)
    assert resp.status_code == 400


def test_project_crud_member_and_visibility(client):
    token = login(client, "admin", "admin")
    h = auth_headers(token)

    # 新增普通用户 bob
    bob_id = client.post(
        "/api/users",
        json={"username": "bob", "password": "secret", "role": "user"},
        headers=h,
    ).json()["id"]

    # 新增项目（选私有化 ADP = tencent_lke）
    resp = client.post(
        "/api/projects",
        json={
            "name": "项目A",
            "provider_type_key": "tencent_lke",
            "host": "aiagent.example.com",
            "region": "1",
            "is_active": True,
            "secret_id": "SID",
            "secret_key": "SKEY",
        },
        headers=h,
    )
    assert resp.status_code == 201, resp.text
    project = resp.json()
    pid = project["id"]
    # 密钥脱敏
    assert "****" in project["secret_key_masked"]

    # bob 还不是成员 -> 看板访问 403
    bob_token = login(client, "bob", "secret")
    bh = auth_headers(bob_token)
    forbidden = client.get(f"/api/dashboard?project_id={pid}", headers=bh)
    assert forbidden.status_code == 403

    # 加 bob 为成员
    add = client.post(
        f"/api/projects/{pid}/members",
        json={"user_id": bob_id, "project_role": "member"},
        headers=h,
    )
    assert add.status_code == 201, add.text

    # bob 现在能看到该项目看板
    ok = client.get(f"/api/dashboard?project_id={pid}", headers=bh)
    assert ok.status_code == 200, ok.text
    assert ok.json()["project_id"] == pid

    # bob 不是项目管理员 -> 无法添加成员
    denied = client.post(
        f"/api/projects/{pid}/members",
        json={"user_id": bob_id, "project_role": "member"},
        headers=bh,
    )
    assert denied.status_code in (400, 403)


def test_sync_falls_back_to_mock(client):
    token = login(client, "admin", "admin")
    h = auth_headers(token)
    pid = client.post(
        "/api/projects",
        json={
            "name": "项目B",
            "provider_type_key": "tencent_lke",
            "host": "aiagent.example.com",
            "region": "1",
            "is_active": True,
            "secret_id": "<SECRET_ID>",
            "secret_key": "<SECRET_KEY>",
        },
        headers=h,
    ).json()["id"]

    resp = client.post(f"/api/projects/{pid}/sync", headers=h)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # 无有效密钥 -> 回退 mock
    assert body["source"] == "mock"

    # 看板能读到刚同步的数据
    dash = client.get(f"/api/dashboard?project_id={pid}", headers=h).json()
    assert dash["data"]["overview"]["total_spaces"] > 0


def test_provider_catalog_enable_disable(client):
    token = login(client, "admin", "admin")
    h = auth_headers(token)
    providers = client.get("/api/providers", headers=h).json()
    keys = {p["type_key"]: p for p in providers}
    assert "tencent_lke" in keys
    assert keys["tencent_lke"]["display_name"] == "私有化 ADP"
    # 公有云 ADP 未实现
    assert keys["adp_public"]["implemented"] is False

    # 未实现类型无法启用
    resp = client.patch("/api/providers/adp_public", json={"enabled": True}, headers=h)
    assert resp.status_code == 400


def _create_mock_project(client, headers, name="对话项目"):
    return client.post(
        "/api/projects",
        json={
            "name": name,
            "provider_type_key": "tencent_lke",
            "host": "aiagent.example.com",
            "region": "1",
            "is_active": True,
            "secret_id": "<SECRET_ID>",
            "secret_key": "<SECRET_KEY>",
        },
        headers=headers,
    ).json()["id"]


def test_sync_conversations_and_dedup(client):
    token = login(client, "admin", "admin")
    h = auth_headers(token)
    pid = _create_mock_project(client, h)

    # 首次同步：无有效密钥 -> mock，应有新增
    resp = client.post(f"/api/projects/{pid}/sync-conversations", json={}, headers=h)
    assert resp.status_code == 200, resp.text
    first = resp.json()
    assert first["source"] == "mock"
    assert first["app_count"] > 0
    assert first["inserted"] > 0

    # 再次同步：record_id 确定性，应全部去重，新增 0
    second = client.post(f"/api/projects/{pid}/sync-conversations", json={}, headers=h).json()
    assert second["inserted"] == 0
    assert second["fetched"] == first["fetched"]

    # 查询入库记录
    page = client.get(f"/api/projects/{pid}/conversations?limit=10", headers=h).json()
    assert page["total"] == first["inserted"]
    assert len(page["items"]) <= 10
    if page["items"]:
        row = page["items"][0]
        assert "question" in row and "answer" in row and "app_biz_id" in row


def test_conversation_filters_and_apps(client):
    token = login(client, "admin", "admin")
    h = auth_headers(token)
    pid = _create_mock_project(client, h, name="对话过滤项目")

    client.post(f"/api/projects/{pid}/sync-conversations", json={}, headers=h)

    # conversation-apps：返回去重后的 app_biz_id 列表
    apps = client.get(f"/api/projects/{pid}/conversation-apps", headers=h).json()
    assert isinstance(apps, list) and len(apps) > 0
    app_id = apps[0]

    # 按应用过滤：所有记录的 app_biz_id 一致
    page = client.get(
        f"/api/projects/{pid}/conversations?app_biz_id={app_id}", headers=h
    ).json()
    assert page["total"] > 0
    assert all(it["app_biz_id"] == app_id for it in page["items"])

    # 关键词过滤（含特殊字符，验证参数绑定不报错且安全）
    injected = client.get(
        f"/api/projects/{pid}/conversations", params={"keyword": "%' OR '1'='1"}, headers=h
    )
    assert injected.status_code == 200

    # 不存在的应用 -> 空结果
    empty = client.get(
        f"/api/projects/{pid}/conversations?app_biz_id=__not_exist__", headers=h
    ).json()
    assert empty["total"] == 0 and empty["items"] == []

    # 时间范围过滤：远未来时间段应无结果
    future = client.get(
        f"/api/projects/{pid}/conversations",
        params={"begin": "2999-01-01 00:00:00"},
        headers=h,
    ).json()
    assert future["total"] == 0


def test_sync_conversations_requires_project_admin(client):
    token = login(client, "admin", "admin")
    h = auth_headers(token)
    pid = _create_mock_project(client, h, name="对话项目B")

    # 普通成员（非项目管理员）无权同步
    bob_id = client.post(
        "/api/users",
        json={"username": "carol", "password": "secret", "role": "user"},
        headers=h,
    ).json()["id"]
    client.post(
        f"/api/projects/{pid}/members",
        json={"user_id": bob_id, "project_role": "member"},
        headers=h,
    )
    bob_h = auth_headers(login(client, "carol", "secret"))
    denied = client.post(f"/api/projects/{pid}/sync-conversations", json={}, headers=bob_h)
    assert denied.status_code == 403
    # 但成员可以查询已入库记录与应用列表
    ok = client.get(f"/api/projects/{pid}/conversations", headers=bob_h)
    assert ok.status_code == 200
    ok_apps = client.get(f"/api/projects/{pid}/conversation-apps", headers=bob_h)
    assert ok_apps.status_code == 200


def test_sync_scopes_selective(client):
    token = login(client, "admin", "admin")
    h = auth_headers(token)
    pid = _create_mock_project(client, h, name="范围项目")

    # 非法范围 / 空范围 -> 400
    assert client.post(f"/api/projects/{pid}/sync", json={"scopes": ["foo"]}, headers=h).status_code == 400
    assert client.post(f"/api/projects/{pid}/sync", json={"scopes": []}, headers=h).status_code == 400

    # 仅同步 token 消耗
    resp = client.post(f"/api/projects/{pid}/sync", json={"scopes": ["token"]}, headers=h)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["scopes"] == ["token"]
    assert "dashboard" in body["details"]
    assert "conversations" not in body["details"]

    # 看板：token_top 有数据，但因未同步应用数量，空间为空
    dash = client.get(f"/api/dashboard?project_id={pid}", headers=h).json()
    assert dash["data"]["overview"]["total_spaces"] == 0
    assert len(dash["data"]["token_top"]["app"]) > 0

    # 再仅同步应用数量，合并后空间补齐、token 仍在
    client.post(f"/api/projects/{pid}/sync", json={"scopes": ["app_count"]}, headers=h)
    dash2 = client.get(f"/api/dashboard?project_id={pid}", headers=h).json()
    assert dash2["data"]["overview"]["total_spaces"] > 0
    assert len(dash2["data"]["token_top"]["app"]) > 0


def test_sync_all_scopes(client):
    token = login(client, "admin", "admin")
    h = auth_headers(token)
    pid = _create_mock_project(client, h, name="全选项目")
    resp = client.post(
        f"/api/projects/{pid}/sync",
        json={"scopes": ["app_count", "conversations", "token"]},
        headers=h,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body["scopes"]) == {"app_count", "conversations", "token"}
    assert "dashboard" in body["details"] and "conversations" in body["details"]
    assert body["details"]["conversations"]["inserted"] > 0


def test_change_password_requires_current_and_confirm(client):
    token = login(client, "admin", "admin")
    h = auth_headers(token)
    alice_id = client.post(
        "/api/users",
        json={"username": "alice", "password": "secret", "role": "user"},
        headers=h,
    ).json()["id"]

    # 缺少原密码 -> 422（schema 校验）
    r1 = client.put(
        f"/api/users/{alice_id}",
        json={"password": "newpass", "confirm_password": "newpass"},
        headers=h,
    )
    assert r1.status_code == 422

    # 两次新密码不一致 -> 422
    r2 = client.put(
        f"/api/users/{alice_id}",
        json={"password": "newpass", "confirm_password": "nope", "current_password": "admin"},
        headers=h,
    )
    assert r2.status_code == 422

    # 原密码错误 -> 400
    r3 = client.put(
        f"/api/users/{alice_id}",
        json={"password": "newpass", "confirm_password": "newpass", "current_password": "wrong"},
        headers=h,
    )
    assert r3.status_code == 400

    # 正确：原密码=管理员本人密码 + 新密码二次确认一致 -> 200
    r4 = client.put(
        f"/api/users/{alice_id}",
        json={"password": "newpass", "confirm_password": "newpass", "current_password": "admin"},
        headers=h,
    )
    assert r4.status_code == 200, r4.text

    # 新密码生效，旧密码失效
    assert login(client, "alice", "newpass")  # 不抛即成功
    old = client.post(
        "/api/auth/login",
        data={"username": "alice", "password": "secret"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert old.status_code == 401

    # 仅改角色、不改密码：无需原密码/确认 -> 200
    r5 = client.put(f"/api/users/{alice_id}", json={"role": "admin"}, headers=h)
    assert r5.status_code == 200
