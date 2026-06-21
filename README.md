# Agent Hub · 智能体运营中心看板系统

> 聚合腾讯云智能体平台（私有化 ADP）等 Provider 的运营指标，以 **项目（Project）** 为中心，提供空间盘点、应用盘点、Token 消耗与对话记录的可视化数据面板。

<p align="left">
  <img alt="backend" src="https://img.shields.io/badge/Backend-FastAPI-009688?logo=fastapi&logoColor=white">
  <img alt="frontend" src="https://img.shields.io/badge/Frontend-Vue3%20+%20TS-42b883?logo=vuedotjs&logoColor=white">
  <img alt="db" src="https://img.shields.io/badge/DB-SQLite%20%7C%20MySQL-003B57?logo=sqlite&logoColor=white">
  <img alt="auth" src="https://img.shields.io/badge/Auth-JWT%20+%20bcrypt-orange">
  <img alt="license" src="https://img.shields.io/badge/License-See%20LICENSE-blue">
</p>

---

## 目录

- [Agent Hub · 智能体运营中心看板系统](#agent-hub--智能体运营中心看板系统)
  - [目录](#目录)
  - [项目简介](#项目简介)
  - [核心能力](#核心能力)
  - [系统架构](#系统架构)
    - [整体架构图](#整体架构图)
    - [后端模块依赖关系图](#后端模块依赖关系图)
    - [数据同步流程](#数据同步流程)
    - [数据模型关系图](#数据模型关系图)
  - [技术栈](#技术栈)
  - [核心概念](#核心概念)
  - [功能模块](#功能模块)
  - [快速开始](#快速开始)
    - [1. 后端](#1-后端)
    - [2. 前端](#2-前端)
    - [3. 登录使用](#3-登录使用)
  - [API 概览](#api-概览)
  - [数据同步机制](#数据同步机制)
    - [按范围统一同步看板（`/sync`）](#按范围统一同步看板sync)
    - [对话记录同步（独立异步任务）](#对话记录同步独立异步任务)
    - [异步任务模式与终止](#异步任务模式与终止)
  - [安全设计](#安全设计)
  - [存储抽象层与 MySQL 切换](#存储抽象层与-mysql-切换)
  - [配置项（环境变量）](#配置项环境变量)
  - [目录结构](#目录结构)
  - [测试](#测试)
  - [扩展：接入新的 Provider](#扩展接入新的-provider)

---

## 项目简介

Agent Hub 是一套面向智能体运营场景的 **Web 看板系统**。它将不同 Provider（如私有化 ADP）的运营数据统一归一化，按项目维度落库为历史快照，并以可视化面板对外呈现。

设计上遵循三条主线：

1. **以项目为中心**：凭证、成员、数据快照都挂在项目（Project）上，看板按项目切换展示。
2. **取数与展示解耦**：项目「手动同步」实时拉取并写入数据库快照，看板统一从库读取；真实调用失败时自动回退内置 **Mock 演示数据**，保证开箱即用。
3. **可扩展、可替换**：Provider 抽象层支持接入新数据源；仓储抽象层支持在 SQLite / MySQL 之间无缝切换。

---

## 核心能力

数据能力源自腾讯云智能体平台的四个接口，归一化后映射到看板：

| 能力 | 对应接口 | 看板呈现 |
| --- | --- | --- |
| 空间盘点 | `ListSpace` | 空间总数 / 有效空间 / 空壳空间 |
| 应用盘点 | `ListApp` | 应用总数、运行中 / 未上线、各空间应用明细 |
| Token 消耗 | `DescribeTopModelToken` | 按空间 / 应用 / 模型的 Token Top 排行图 |
| 对话记录 | `DescribeMsgLogList` | 对话明细列表（含应用名称、意图）+ 按天趋势 + 意图分布统计 |

---

## 系统架构

### 整体架构图

采用前后端分离的分层架构：浏览器端 SPA 通过 `/api` 访问后端 REST 服务，后端经由「路由层 → 服务层 → 仓储层 / Provider 层」处理请求，最终落地到数据库与外部云接口。

```mermaid
flowchart TB
    subgraph Client["前端 SPA（Vue 3 + TS + Vite）"]
        V1["视图 Views<br/>登录 / 看板 / 对话 / 管理面板"]
        ST["状态 Stores<br/>auth · project (Pinia)"]
        API["API 封装<br/>axios + 拦截器"]
        V1 --> ST --> API
    end

    subgraph Backend["后端服务（FastAPI）"]
        direction TB
        R["路由层 Routers<br/>auth · users · projects · providers · dashboard"]
        DEP["鉴权依赖 deps<br/>admin / project_access / project_admin"]
        SVC["服务层 Services<br/>normalize · sync · conversations · sync_jobs · dashboard"]
        REPO["仓储抽象层 Repositories<br/>base + sqlalchemy_impl + 工厂"]
        PRD["Provider 抽象层<br/>base · registry · tencent_lke · mock · ssrf"]
        R --> DEP --> SVC
        SVC --> REPO
        SVC --> PRD
    end

    subgraph Store["持久化"]
        DB[("数据库<br/>SQLite / MySQL")]
    end

    Cloud["私有化 ADP<br/>(ListSpace/ListApp/Token/MsgLog)"]

    API -->|"HTTP /api/*  (JWT Bearer)"| R
    REPO --> DB
    PRD -->|"TC3-HMAC-SHA256 · SSRF 校验"| Cloud
    PRD -.->|真实调用失败回退| Mock["内置 Mock 演示数据"]
```

### 后端模块依赖关系图

后端遵循单向依赖：上层依赖抽象接口，具体实现由工厂注入，业务层不感知存储与数据源细节。

```mermaid
flowchart LR
    main["main.py<br/>FastAPI 入口"] --> routers
    main --> seed["seed.py<br/>建表 + 默认数据"]

    routers["routers/*"] --> deps["deps.py<br/>鉴权"]
    routers --> services["services/*"]
    routers --> schemas["schemas.py<br/>Pydantic DTO"]
    routers --> security["security.py<br/>JWT/bcrypt/Fernet"]

    services --> repositories["repositories<br/>抽象接口 + 工厂"]
    services --> providers["providers/*"]
    services --> normalize["normalize.py<br/>指标归一化"]

    repositories --> models["models.py<br/>ORM 模型"]
    repositories --> database["database.py<br/>会话/引擎"]

    providers --> ssrf["ssrf.py<br/>SSRF 防护"]
    providers --> registry["registry.py<br/>类型注册表"]

    config["config.py<br/>env-only 配置"] -.-> services
    config -.-> security
    config -.-> repositories
```

### 数据同步流程

以「项目按范围手动同步看板数据」为例，展示从前端触发到落库、回退 Mock 的完整链路（对话记录同步已独立为异步任务，见下方说明）：

```mermaid
sequenceDiagram
    participant U as 管理员（前端）
    participant R as Router /projects/{id}/sync
    participant G as 权限校验
    participant S as Service 层（sync_dashboard）
    participant P as Provider（LKE）
    participant M as Mock 数据
    participant DB as 数据库

    U->>R: POST /sync { scopes: [app_count, token] }
    R->>G: require_project_admin
    G-->>R: 通过（否则 403）
    R->>S: sync_dashboard（按 scope 局部拉取）
    S->>P: 解密凭证后实时拉取
    alt 调用成功
        P-->>S: 真实数据 (source=live)
    else 无凭证 / 调用失败
        S->>M: 回退 Mock（记录回退原因）
        M-->>S: 演示数据 (source=mock)
    end
    S->>DB: 与最新快照合并后追加新快照
    S-->>R: 汇总 { source, details, errors }
    R-->>U: SyncResult（含 live/mock 标记与回退原因）
```

> **对话记录同步**已从 `/sync` 拆出，统一走「对话记录」页的 **异步任务模式**（`conversation-sync-jobs`）：后台执行、写回进度，前端轮询展示进度条，并支持 **协作式终止**（`/cancel`）。

### 数据模型关系图

```mermaid
erDiagram
    USER ||--o{ PROJECT_MEMBER : "归属"
    PROJECT ||--o{ PROJECT_MEMBER : "包含成员"
    PROJECT ||--o{ METRIC_SNAPSHOT : "历史快照"
    PROJECT ||--o{ CONVERSATION_RECORD : "对话明细"
    PROJECT ||--o{ SYNC_JOB : "同步任务"
    PROVIDER ||..o{ PROJECT : "type_key 引用"

    USER {
        int id PK
        string username
        string role "admin / user"
        bool is_active
    }
    PROVIDER {
        string type_key PK
        string display_name
        bool enabled
        bool implemented
    }
    PROJECT {
        int id PK
        string name
        string provider_type_key
        string host
        string secret_id
        string secret_key_enc "Fernet 密文"
    }
    PROJECT_MEMBER {
        int project_id FK
        int user_id FK
        string project_role "project_admin / member"
    }
    METRIC_SNAPSHOT {
        int project_id FK
        string payload "JSON"
        string source "live / mock"
    }
    CONVERSATION_RECORD {
        int project_id FK
        string app_biz_id
        string app_name "应用名称"
        string record_id "去重键"
        string intent "意图"
        string intent_category "意图分类"
    }
    SYNC_JOB {
        int project_id FK
        string status "pending/running/cancelling/success/failed/cancelled"
        int app_done
        int inserted
    }
```

---

## 技术栈

| 层次 | 选型 |
| --- | --- |
| 前端 | Vue 3 · TypeScript · Vite 6 · Pinia · Ant Design Vue 4 · ECharts（vue-echarts） |
| 后端 | Python ≥ 3.9 · FastAPI · SQLAlchemy 2.0 · Pydantic v2 · pydantic-settings |
| 鉴权 | JWT（python-jose）· bcrypt 密码哈希（passlib） |
| 加密 | Fernet 对称加密（cryptography）落库项目密钥 |
| 存储 | 仓储抽象层（`REPOSITORY_BACKEND`）· SQLite（默认）/ MySQL |
| 依赖管理 | 后端 [uv](https://docs.astral.sh/uv/)（`pyproject.toml` + `uv.lock`）；前端 npm |

---

## 核心概念

- **Provider（类型目录）**：内置 Provider 类型，仅做启用/禁用，**不存储凭证**。
  - 私有化 ADP（`tencent_lke`）：已实现，默认启用。
  - 公有云 ADP（`adp_public`）：尚未实现，前端置灰、不可启用。
- **Project（项目）**：选择一个 Provider 类型并录入自己的 `SECRET_ID / SECRET_KEY / HOST / region`，分配成员，手动同步数据。看板按项目切换展示。
- **User（用户）与项目成员**：
  - 全局角色：`admin`（可进管理面板、默认可见全部项目）/ `user`（仅可见所属项目）。
  - 项目级角色：`project_admin`（可管理本项目成员与同步）/ `member`。
  - 用户可属于多个项目，看板顶部支持项目切换。

---

## 功能模块

- **登录系统**：内置默认管理员 **admin / admin**（仅首次初始化写入，生产务必修改）。
- **运营看板**：按项目切换的空间/应用盘点 + Token 消耗排行可视化，数据来自最新同步快照；应用明细支持关键词搜索与 CSV 导出。
- **对话记录**：分页查询对话明细（含应用名称、意图，支持按应用 / 时间 / 关键词 / 意图过滤），提供按天趋势与意图分布图表；同步以**异步任务**进行，进度条实时展示且可**随时终止**（已拉取部分保留入库）。
- **管理员面板**：
  - **用户管理**：列表/搜索、详情（含所属项目）、新增、编辑、角色分配、禁用/启用。
  - **项目管理**：项目 CRUD（选 Provider + 录凭证）、成员管理、**手动同步看板数据**（按范围勾选：应用数量 / Token 消耗，支持全选；对话记录同步已独立到「对话记录」页）。
  - **Provider 管理**：内置类型目录的启用/禁用（未实现项置灰）。

---

## 快速开始

> ⚠️ **从旧版本升级**：数据模型已重构（Provider 不再存凭证，新增项目/成员/快照表）。
> dev 环境请先删除旧库再启动：`rm -f backend/agent_hub.db`。

### 1. 后端

依赖由 [uv](https://docs.astral.sh/uv/) 管理（`pyproject.toml` + `uv.lock`）。

```bash
cd backend
uv sync                         # 创建 .venv 并按 uv.lock 安装依赖
cp .env.example .env            # 生产环境务必修改 APP_SECRET
rm -f agent_hub.db              # 如存在旧版本数据库，先删除重建
uv run uvicorn app.main:app --reload --port 8011
```

> 未安装 uv：`curl -LsSf https://astral.sh/uv/install.sh | sh`

首次启动会自动建表，并写入默认管理员（admin/admin）、Provider 类型目录与一个示例项目（无有效密钥 → 同步回退 Mock）。
接口文档随服务启动可见：`http://localhost:8011/docs`。

### 2. 前端

```bash
cd frontend
npm install
npm run dev        # 默认 http://localhost:5173 ，已将 /api 代理至后端 8011
```

### 3. 登录使用

浏览器打开前端地址，使用 **admin / admin** 登录：

- 「运营看板」：选择项目查看空间/应用盘点与 Token 排行。
- 「对话记录」：查询对话明细与统计图表。
- 「用户管理 / 项目管理 / Provider 管理」（管理员）：维护用户、配置项目并手动同步数据。

---

## API 概览

所有接口以 `/api` 为前缀，除登录外均需携带 `Authorization: Bearer <token>`。

| 模块 | 方法 & 路径 | 说明 | 权限 |
| --- | --- | --- | --- |
| 健康检查 | `GET /api/health` | 存活探测 | 公开 |
| 认证 | `POST /api/auth/login` | 登录获取 JWT | 公开 |
| 认证 | `GET /api/auth/me` | 当前用户（含可见项目） | 登录 |
| 用户 | `GET/POST /api/users`、`GET/PUT /api/users/{id}`、`PATCH /api/users/{id}/status` | 用户 CRUD / 角色 / 禁用 | admin |
| 项目 | `GET/POST /api/projects`、`GET/PUT/DELETE /api/projects/{id}` | 项目 CRUD | 读：成员；写：admin |
| 成员 | `GET/POST /api/projects/{id}/members`、`DELETE .../members/{uid}` | 成员管理 | project_admin |
| 同步 | `POST /api/projects/{id}/sync` | 按范围（`app_count` / `token`）同步看板数据 | project_admin |
| 对话同步 | `POST /api/projects/{id}/sync-conversations` | 同步对话记录（同步） | project_admin |
| 对话异步任务 | `POST/GET /api/projects/{id}/conversation-sync-jobs[/latest|/{job_id}]`、`POST .../{job_id}/cancel` | 后台同步 + 进度轮询 + 终止 | project_admin / 成员 |
| 对话查询 | `GET /api/projects/{id}/conversations`、`.../conversation-apps`（返回应用 ID + 名称）、`.../conversation-stats` | 列表 / 应用下拉 / 统计 | 成员 |
| Provider | `GET /api/providers`、`PATCH /api/providers/{type_key}` | 类型目录 / 启用禁用 | 读：登录；写：admin |
| 看板 | `GET /api/dashboard?project_id=` | 读取最新快照 | 成员 |

---

## 数据同步机制

### 按范围统一同步看板（`/sync`）

项目「同步」按钮支持按范围勾选，前端按勾选动态生成 `scopes` 调用统一端点（仅看板数据，**不含对话记录**）：

```jsonc
POST /api/projects/{id}/sync
{
  "scopes": ["app_count", "token"]   // 二者子集；留空默认 [app_count, token]
}
```

- `app_count`（应用数量）与 `token`（Token 消耗）按 scope **局部拉取**，与最新快照合并，未勾选部分沿用历史，保证看板始终完整。
- 返回 `{ ok, source, message, scopes, details }`，`details` 含各部分同步明细；回退 Mock 时 `message` 会附带**具体回退原因**（如「Token 消耗拉取失败：…」）。

### 对话记录同步（独立异步任务）

对话记录同步已从 `/sync` 拆出，统一在「对话记录」页发起，遍历项目下所有应用拉取并以 `record_id` 在项目维度 **去重入库**（一并落库 `app_name` / `intent`）。

- 默认时间范围 **最近 30 天**；支持自定义起止时间。
- 默认 **增量模式**：以已入库的最大 `msg_create_time` 作为本次起点，仅拉取新增量；`full=true` 时按时间范围全量回补。
- **最小同步间隔限频**（`CONV_SYNC_MIN_INTERVAL_SECONDS`，默认 300s）：过于频繁返回 `429`。
- **应用间限速**（`CONV_SYNC_APP_DELAY_MS`）：相邻应用拉取间隔，避免触发云端 QPS 限制。

### 异步任务模式与终止

`POST /api/projects/{id}/conversation-sync-jobs` 启动后台任务并立即返回任务对象，前端轮询 `.../{job_id}` 获取进度（`app_done / app_total / fetched / inserted`）。同一项目同时仅允许一个进行中的对话同步任务（冲突返回 `409`）。

- **协作式终止**：`POST .../{job_id}/cancel` 将任务置为 `cancelling`，后台在处理下一个应用前停止，标记为 `cancelled`，**已拉取部分保留入库**。
- **僵尸任务清理**：服务启动时会把上次进程残留的 `pending/running/cancelling` 任务标记为失败，避免进度条永久卡死。
- 任务状态：`pending` / `running` / `cancelling` / `success` / `failed` / `cancelled`。

---

## 安全设计

- **凭证加密落库**：项目 `secret_key` 使用 Fernet 对称加密存储，接口返回一律 **脱敏**（`mask_secret`）。
- **SQL 注入防护**：所有 SQL 通过 SQLAlchemy 参数绑定，杜绝注入。
- **SSRF 防护**：项目 HOST 经 `normalize_host` 归一化（兼容带/不带协议与端口的写法），默认禁止解析到内网/私有地址（含 `9./10./11./21./30.` 等网段），确需内网网关时设 `ALLOW_INTERNAL_HOSTS=true`。
- **越权防护**：看板/项目读取校验项目可见性；项目写、成员管理与同步需 `admin` 或 `project_admin`。
- **账号即时失效**：禁用用户后已签发 token 立即失效；不可禁用自身；系统保留至少一名启用的管理员。
- **敏感配置 env-only**：`APP_SECRET`、管理员初始口令、数据库连接等均走环境变量。

---

## 存储抽象层与 MySQL 切换

业务层只依赖 `app/repositories/base.py` 中的仓储接口，具体实现由 `app/repositories/__init__.py` 工厂按 `REPOSITORY_BACKEND` 注入（内置 `sqlalchemy`）。模型仅使用通用 SQL 语义，可直接用于 SQLite 与 MySQL。

切换 MySQL：

```bash
# 1) 安装驱动
uv add pymysql            # 或 pip install pymysql
# 2) 修改 .env
DATABASE_URL=mysql+pymysql://user:password@127.0.0.1:3306/agent_hub?charset=utf8mb4
```

首次启动会自动建表与写入初始数据。

---

## 配置项（环境变量）

后端配置集中于 `backend/app/config.py`，通过 `.env` 注入（参见 `.env.example`）：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `APP_SECRET` | `please-change-me...` | JWT 签名 + Provider 密钥加密派生密钥，**生产必改** |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `720` | JWT 过期时间（分钟） |
| `DEFAULT_ADMIN_USERNAME` / `DEFAULT_ADMIN_PASSWORD` | `admin` / `admin` | 默认管理员（仅首次初始化生效） |
| `DATABASE_URL` | `sqlite:///./agent_hub.db` | 数据库连接串 |
| `REPOSITORY_BACKEND` | `sqlalchemy` | 仓储后端实现 |
| `ALLOW_INTERNAL_HOSTS` | `false` | 是否允许访问内网/私有地址（SSRF） |
| `CONV_SYNC_MIN_INTERVAL_SECONDS` | `300` | 对话同步最小间隔（秒），0 不限制 |
| `CONV_SYNC_APP_DELAY_MS` | `100` | 对话同步相邻应用拉取限速（毫秒） |
| `CONV_STORE_RAW` | `false` | 是否落库对话原始报文（排障用） |
| `LOG_LEVEL` | `INFO` | 日志级别（`DEBUG/INFO/WARNING/ERROR`），排障设 `DEBUG` |
| `PROVIDER_DEBUG` | `false` | 是否打印 Provider 出站请求详情（接口名/HOST/耗时） |

前端环境变量（`frontend/.env.example`，复制为 `.env` / `.env.local` 后生效）：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `VITE_API_TIMEOUT` | `60000` | API 请求超时（毫秒），慢接口可调大 |

---

## 目录结构

```text
agent-hub/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI 入口（挂载路由 + 启动建库）
│   │   ├── logging_conf.py     # 统一日志初始化（按 LOG_LEVEL 输出）
│   │   ├── config.py          # 配置（env-only，含 REPOSITORY_BACKEND）
│   │   ├── database.py        # 引擎 / 会话 / Base
│   │   ├── models.py          # User / Provider / Project / ProjectMember / MetricSnapshot / ConversationRecord / SyncJob
│   │   ├── schemas.py         # Pydantic 请求/响应模型
│   │   ├── security.py        # JWT / bcrypt / Fernet / 脱敏
│   │   ├── deps.py            # 鉴权依赖（admin / project_access / project_admin）
│   │   ├── seed.py            # 建库 + 默认数据 + 轻量补列
│   │   ├── repositories/      # 仓储抽象层（base + sqlalchemy_impl + 工厂）
│   │   ├── services/          # normalize / sync / conversations / sync_jobs / dashboard
│   │   ├── routers/           # auth / users / projects / providers / dashboard
│   │   └── providers/         # Provider 抽象层（base/registry/tencent_lke/adp/mock/ssrf）
│   ├── tests/                 # pytest 用例（API + 仓储）
│   ├── pyproject.toml         # 依赖与工具配置
│   └── .env.example           # 环境变量样例
├── frontend/
│   ├── src/
│       ├── api/               # axios 封装（http + index）
│       ├── stores/            # Pinia（auth / project）
│       ├── router/            # 路由 + 守卫（hash history）
│       ├── layouts/           # 主布局（含管理面板子菜单）
│       ├── components/        # 图表等组件
│       ├── views/             # 登录 / 看板 / 对话 / admin（用户/项目/Provider）
│       └── types.ts           # 共享 TS 类型
│   └── .env.example           # 前端环境变量样例（VITE_API_TIMEOUT）
├── docs/plans/                # 设计文档
├── README.md
└── LICENSE
```

---

## 测试

```bash
cd backend
uv run --with pytest --with httpx pytest tests -q
```

测试覆盖 API 行为（鉴权、项目/成员、同步回退）与仓储实现两部分（`tests/test_api.py`、`tests/test_repositories.py`）。

---

## 扩展：接入新的 Provider

1. 在 `backend/app/providers/` 新建类，继承 `BaseProvider`，实现 `fetch_spaces()` 与 `fetch_token_top()`（如需对话同步，覆写 `fetch_conversations()`）。
2. 在 `providers/registry.py` 的 `_REGISTRY` 注册实现类，并在 `BUILTIN_PROVIDERS` 增加目录元数据（`type_key` / `display_name` / `implemented`）。
3. 重启后端，「Provider 管理」会展示该类型，启用后即可在项目创建表单中选择。

> 真实调用应通过 `ssrf.assert_safe_host` 做出站校验，并在异常时抛出 `ProviderError`，由服务层统一回退 Mock。
