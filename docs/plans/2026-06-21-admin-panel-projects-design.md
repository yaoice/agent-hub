# 管理面板重构：用户管理 / 项目管理 / Provider 管理 设计文档

日期：2026-06-21
状态：已确认，进入实现

## 1. 背景与目标

将原先的「Provider 配置」演进为以**项目（Project）**为中心的运营看板体系：

- 管理员面板包含三个模块：**用户管理 / 项目管理 / Provider 管理**。
- 运营看板与用户面板展示的实际是**项目**数据，支持按项目切换。
- 项目数据由「手动同步」拉取并落库，看板/用户面板统一从库读取。
- 存储层抽象，支持 SQLite，后续可切换 MySQL。

## 2. 核心决策（已确认）

| # | 决策 |
| --- | --- |
| 凭证归属 | 方案A：Provider 仅为类型目录，不存凭证；`SECRET_ID/KEY/HOST/region` 挂在 **Project** 上 |
| 数据存储 | 保留**历史快照**：每次同步插一条带时间戳记录，看板默认读最新 |
| 抽象层 | **Repository 接口 + 可配置 `DATABASE_URL`**，并提供 MySQL 切换文档 |
| 角色 | 全局 `admin/user` + **项目级角色** `project_admin/member`（项目管理员可管理本项目成员） |
| Provider 管理 | **只读目录 + 启用/禁用开关**；私有化 ADP=tencent_lke（可用），公有云 ADP 未实现→置灰且不可启用 |
| 旧库处理 | 直接删除 `agent_hub.db` 重建（dev 环境，数据可弃），seed/README 说明 |

## 3. 数据模型

```
User          : id, username, password_hash, role(admin/user),
                is_active(禁用), created_at
Provider      : id, type_key(如 tencent_lke), display_name(私有化ADP),
                enabled, implemented, description           # 类型目录, 无凭证
Project       : id, name, provider_type_key(引用Provider.type_key),
                host, secret_id, secret_key_enc, region,
                is_active, created_at, updated_at           # 凭证挂这里
ProjectMember : id, project_id, user_id,
                project_role(project_admin/member)          # 多对多+项目角色
MetricSnapshot: id, project_id, metric_type(dashboard),
                payload(Text/JSON), source(live/mock), created_at  # 历史快照
```

关系：
- `Project.provider_type_key` 引用 `Provider.type_key`，并录入自己的凭证。
- `User` 经 `ProjectMember` 多对多关联多个 `Project`，每条带项目角色。
- 每次同步向 `MetricSnapshot` 插一条；看板读该项目最新一条。

可见性：
- `admin`：进管理面板，默认可见全部项目。
- `user`：仅可见自己作为成员的项目；多项目支持切换。
- `project_admin`：可管理本项目成员。

## 4. 后端架构

```
app/
  models.py
  schemas.py
  repositories/
    base.py            # 抽象接口: User/Project/ProjectMember/Metric Repository
    sqlalchemy_impl.py # SQLAlchemy 实现 (sqlite/mysql 通用)
    __init__.py        # 工厂: 按配置返回实现
  services/
    sync.py            # 项目同步: build provider -> 归一化 -> 写快照(失败回退 mock)
    dashboard.py       # 读取项目最新快照
    provider_catalog.py
  routers/
    auth.py users.py projects.py providers.py dashboard.py
  providers/           # 复用现有 base/registry/tencent_lke/adp/mock/ssrf
  deps.py              # require_admin / require_project_access / require_project_admin
```

存储抽象层：
- `repositories/base.py` 用 `abc.ABC` 定义接口（如 `MetricRepository.add_snapshot / get_latest / list_history`）。
- 业务层仅依赖抽象接口，经工厂注入实现。
- MySQL：模型避免 SQLite 特有特性，`payload` 用 `Text` 存 JSON；切换只改 `DATABASE_URL=mysql+pymysql://...`，可选安装 `pymysql`。

## 5. API 端点

认证：
- `POST /api/auth/login`、`GET /api/auth/me`（返回可见项目列表）

用户管理（admin）`/api/users`：
- `GET /` 列表（分页/搜索）、`GET /{id}` 详情、`POST /` 新增、`PUT /{id}` 编辑、`PATCH /{id}/status` 禁用/启用
- 禁用即时失效；不可禁用/删除自身；最后一个 admin 不可降级/禁用

项目管理 `/api/projects`：
- `GET /`（admin 全部 / user 所属）、`POST /`、`PUT /{id}`、`DELETE /{id}`
- `GET /{id}/members`、`POST /{id}/members`、`DELETE /{id}/members/{uid}`
- `POST /{id}/sync` 手动同步写快照
- 写权限：admin 或该项目 project_admin；凭证返回脱敏

Provider 目录 `/api/providers`：
- `GET /` 列表、`PATCH /{key}` 启用/禁用（implemented=false 不可启用）

看板 `/api/dashboard`：
- `GET /?project_id=` 读最新快照；校验当前用户对该项目可见，否则 403

## 6. 前端结构

路由：`/login`、`/dashboard`、`/admin/users`、`/admin/projects`、`/admin/providers`（后三者 adminOnly）。

视图：
- `DashboardView.vue`：顶部项目切换器，数据来自快照，显示同步时间/source。
- `admin/UsersView.vue`：列表 + 详情 + 新增/编辑 + 禁用开关 + 角色选择。
- `admin/ProjectsView.vue`：列表 + 新增/编辑(选 Provider+录凭证) + 成员管理 + 同步按钮。
- `admin/ProvidersView.vue`：只读目录 + 启用/禁用，公有云 ADP 置灰。

状态：`stores/auth.ts`（可见项目/当前项目）、`stores/project.ts`。
Provider 展示统一用 `display_name`（tencent_lke→私有化 ADP），项目表单下拉只列 `enabled && implemented`。

## 7. 安全

- 凭证 Fernet 加密落库、接口脱敏。
- SSRF：host 走现有校验，默认禁内网，`ALLOW_INTERNAL_HOSTS` 可放开。
- 鉴权：`require_admin` / `require_project_access` / `require_project_admin`。
- 禁用用户即时失效；不可操作自身；最后一个 admin 受保护。
- SQL 全部参数绑定。

## 8. 初始化 seed（重建）

- 默认 admin/admin。
- Provider 目录：`tencent_lke`(私有化ADP, enabled, implemented) + `adp_public`(公有云ADP, implemented=false)。
- 示例项目（无有效密钥→同步回退 mock），admin 设为成员。
- 启动前删除旧 `agent_hub.db`（README 注明）。

## 9. 测试

- 后端 pytest：仓储 snapshot 增/查最新；权限（越权 403、禁用 401）；同步 mock 回退；用户禁用规则。
- 冒烟：admin 建项目→加成员→同步→user 登录可见。

## 10. 实现阶段

1. 数据模型 + 仓储抽象层 + seed 重建
2. 用户管理 API + 鉴权增强
3. 项目管理 + 成员 + 同步 + 看板按项目
4. Provider 目录 API
5. 前端：管理面板三页 + 看板项目切换器
6. README/文档 + 冒烟测试
