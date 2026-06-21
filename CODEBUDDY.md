# CODEBUDDY.md

本文件为 AI 编码助手（CodeBuddy）及开发者在本仓库工作时的指南，沉淀项目结构、运行方式、关键约定与协作规范。修改代码前请先通读本文件。

---

## 1. 项目简介

**Agent Hub（智能体运营中心看板系统）** 是一套前后端分离的 Web 应用，用于聚合腾讯云智能体平台（LKE / 私有化 ADP）等 Provider 的运营指标，以 **项目（Project）** 为中心提供可视化看板。

核心特性：

- **以项目为中心**：凭证、成员、数据快照都挂在 Project 上，看板按项目切换。
- **取数即落库**：手动同步实时拉取并写入快照，看板统一从库读取；真实调用失败自动回退 **Mock**。
- **双层抽象**：Provider 抽象层（接入新数据源）+ 仓储抽象层（SQLite/MySQL 切换）。

| 维度 | 内容 |
| --- | --- |
| 后端 | Python ≥ 3.9 · FastAPI · SQLAlchemy 2.0 · Pydantic v2 · uv 管理依赖 |
| 前端 | Vue 3 · TypeScript · Vite 6 · Pinia · Ant Design Vue 4 · ECharts |
| 数据库 | SQLite（默认）/ MySQL，由仓储抽象层适配 |
| 鉴权 | JWT（python-jose）+ bcrypt + Fernet 密钥加密 |
| 默认账号 | `admin / admin`（仅首次初始化写入） |
| 端口 | 后端 `8011`，前端 `5173`（`/api` 代理到后端） |

---

## 2. 目录结构说明

```text
agent-hub/
├── backend/                    # 后端服务（FastAPI）
│   ├── app/
│   │   ├── main.py             # 入口：挂载路由 + startup 时 init_db()
│   │   ├── config.py           # Settings（env-only），get_settings() 缓存单例
│   │   ├── database.py         # engine / SessionLocal / Base / get_db()
│   │   ├── models.py           # ORM 模型（全部数据表定义）
│   │   ├── schemas.py          # Pydantic DTO（请求/响应）
│   │   ├── security.py         # JWT 签发/校验、bcrypt、Fernet 加解密、脱敏
│   │   ├── deps.py             # 鉴权依赖：get_current_user / require_admin / require_project_*
│   │   ├── seed.py             # 建表 + 默认管理员/Provider/示例项目 + 轻量补列
│   │   ├── routers/            # 路由层（仅做编排与权限，不写业务细节）
│   │   │   ├── auth.py         # /api/auth  登录、me
│   │   │   ├── users.py        # /api/users 用户 CRUD（admin）
│   │   │   ├── projects.py     # /api/projects 项目/成员/同步/对话
│   │   │   ├── providers.py    # /api/providers 类型目录启用禁用
│   │   │   └── dashboard.py    # /api/dashboard 读取最新快照
│   │   ├── services/           # 服务层（业务逻辑）
│   │   │   ├── normalize.py    # Provider 原始数据 → 看板统一结构 + scope 拉取
│   │   │   ├── sync.py         # 看板快照同步（局部/完整）
│   │   │   ├── conversations.py# 对话记录同步（增量/去重/限频）
│   │   │   ├── sync_jobs.py    # 异步对话同步任务执行体
│   │   │   └── dashboard.py    # 看板读取（惰性首同步）
│   │   ├── repositories/       # 仓储抽象层
│   │   │   ├── base.py         # 抽象接口（业务层只依赖它）
│   │   │   ├── sqlalchemy_impl.py # SQLAlchemy 实现
│   │   │   └── __init__.py     # 工厂：按 REPOSITORY_BACKEND 注入 get_*_repository
│   │   └── providers/          # Provider 抽象层
│   │       ├── base.py         # BaseProvider + 数据类（AppItem/SpaceItem/...）
│   │       ├── registry.py     # _REGISTRY 注册表 + BUILTIN_PROVIDERS 目录
│   │       ├── tencent_lke.py  # 腾讯云 LKE 实现（TC3-HMAC-SHA256）
│   │       ├── adp.py          # ADP 相关
│   │       ├── mock.py         # Mock 演示数据
│   │       └── ssrf.py         # 出站 SSRF 防护
│   ├── tests/                  # pytest：conftest / test_api / test_repositories
│   ├── pyproject.toml          # 依赖 + pytest 配置
│   └── .env.example            # 环境变量样例
├── frontend/                   # 前端 SPA（Vue 3）
│   └── src/
│       ├── main.ts             # 应用入口（挂载 Pinia / Router / AntD）
│       ├── App.vue
│       ├── types.ts            # 共享 TS 类型（与后端 schema 对应）
│       ├── api/                # http.ts（axios 实例+拦截器）+ index.ts（按模块封装）
│       ├── stores/             # Pinia：auth.ts（登录态/角色）、project.ts（当前项目）
│       ├── router/index.ts     # 路由表 + 守卫（hash history，adminOnly 守卫）
│       ├── layouts/MainLayout.vue # 侧边栏 + 顶栏 + 内容区
│       ├── components/         # 图表等可复用组件
│       └── views/              # 页面：Login / Dashboard / Conversations / admin/*
├── docs/plans/                 # 设计文档（按日期命名）
├── README.md                   # 面向用户的项目文档
├── CODEBUDDY.md                # 本文件
└── LICENSE
```

---

## 3. 快速启动与运行指南

### 3.1 后端

```bash
cd backend
uv sync                         # 创建 .venv 并安装依赖（按 uv.lock）
cp .env.example .env            # 生产环境务必修改 APP_SECRET
rm -f agent_hub.db              # 升级/重置时删除旧库（dev）
uv run uvicorn app.main:app --reload --port 8011
```

- 接口文档：`http://localhost:8011/docs`
- 健康检查：`GET http://localhost:8011/api/health`
- 首次启动自动建表 + 写入默认管理员、Provider 目录与示例项目。

### 3.2 前端

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173 ，/api 已代理到 8011
npm run build      # vue-tsc 类型检查 + vite 生产构建
```

### 3.3 测试

```bash
cd backend
uv run --with pytest --with httpx pytest tests -q
```

### 3.4 切换 MySQL

```bash
uv add pymysql
# .env 中：
DATABASE_URL=mysql+pymysql://user:password@127.0.0.1:3306/agent_hub?charset=utf8mb4
```

---

## 4. 核心功能模块介绍

### 4.1 认证与鉴权
- `security.py` 负责 JWT 签发/校验、bcrypt 哈希、Fernet 加解密；`deps.py` 提供依赖：
  - `get_current_user`：解析 token，**禁用用户即时失效**。
  - `require_admin`：全局管理员。
  - `require_project_access`：项目可见性（admin 全可见 / 普通用户须为成员）。
  - `require_project_admin`：项目写权限（admin 或 project_admin）。

### 4.2 项目与同步（核心）
- 项目持有加密凭证与成员；同步分两类：
  - **看板同步**（`sync.py` + `normalize.py`）：按 scope（`app_count` / `token`）局部拉取，与最新快照合并后追加新 `MetricSnapshot`。
  - **对话同步**（`conversations.py`）：遍历项目下所有应用拉取 `DescribeMsgLogList`，按 `record_id` 项目级去重入库；默认增量，受最小间隔限频（429）。
- **异步任务**（`sync_jobs.py` + `SyncJob` 表）：后台执行写回进度，前端轮询。
- **Mock 回退**：无有效凭证或调用异常时回退 `mock.py`，`source` 标记为 `mock`。

### 4.3 看板与对话查询
- `dashboard.py`（router/service）：按 `project_id` 读取最新快照；未传则取用户可见的首个项目。
- 对话查询：列表分页 + 应用下拉 + 统计（按天趋势 / 意图分布）。

### 4.4 Provider 抽象层
- `BaseProvider` 定义 `fetch_spaces` / `fetch_token_top` / `fetch_conversations`；`registry.py` 维护 `_REGISTRY`（实现类）与 `BUILTIN_PROVIDERS`（目录元数据）。
- 所有出站请求经 `ssrf.assert_safe_host` 校验，异常抛 `ProviderError`。

### 4.5 仓储抽象层
- 业务层只依赖 `repositories/base.py` 接口，经工厂 `get_*_repository(db)` 注入实现；新增后端只需在 `_BACKENDS` 登记并切换 `REPOSITORY_BACKEND`。

### 4.6 前端
- `api/index.ts` 按模块（auth/user/provider/project/dashboard/conversation）封装；`http.ts` 统一注入 token、处理 401。
- `stores/auth.ts` 持有登录态与角色；`stores/project.ts` 持有当前选中项目。
- 路由守卫拦截未登录与非管理员访问 `adminOnly` 页面。

---

## 5. 开发规范

### 5.1 通用
- **语言**：代码注释与文档使用中文；标识符使用英文。
- **提交前**：后端跑通 `pytest`，前端 `npm run build` 通过类型检查。
- **最小改动**：聚焦目标，避免无关重构；遵循既有分层与命名风格。

### 5.2 后端
- **分层职责**：router 只做编排 + 权限校验；业务逻辑放 service；数据访问走 repository，**不在 router/service 直接写裸 ORM 查询**（除既有约定外）。
- **鉴权**：写操作必须挂 `require_admin` / `require_project_admin`；读操作挂 `require_project_access`。
- **DTO**：对外输入输出统一用 `schemas.py` 的 Pydantic 模型，避免直接返回 ORM。
- **配置**：新增配置加到 `config.Settings` 并补充 `.env.example`，**严禁硬编码密钥**（env-only）。
- **安全红线**：
  - SQL 一律参数绑定（SQLAlchemy），禁止字符串拼接。
  - 出站请求必须经过 `assert_safe_host`（SSRF）。
  - 凭证落库必须 Fernet 加密，返回必须 `mask_secret` 脱敏。
  - 反序列化使用安全方式；不信任外部输入。
- **异常与回退**：Provider 调用失败应捕获并回退 Mock，保证看板始终可用；不要让单个应用失败影响整体同步。

### 5.3 前端
- API 调用统一经 `api/` 封装，不在组件内直接 `axios`。
- 类型定义集中在 `types.ts`，与后端 schema 保持一致。
- 复用 Ant Design Vue 组件与既有样式变量（如 `--ah-primary`）。

### 5.4 数据库变更
- 修改 `models.py` 后，dev 环境可删除 `agent_hub.db` 重建；如需兼容旧库，在 `seed.py::_ensure_schema` 增加向后兼容的 `ADD COLUMN`（SQLite/MySQL 通用语义）。

---

## 6. 贡献指南

### 6.1 分支与提交
- 从 `main` 切功能分支：`feat/xxx`、`fix/xxx`、`docs/xxx`、`refactor/xxx`。
- Commit message 建议遵循 Conventional Commits：
  ```
  feat(projects): 支持按范围增量同步对话记录
  fix(auth): 禁用用户后立即失效 token
  docs: 重构 README 并补充架构图
  ```
- **未经用户明确要求，不要执行提交（commit）操作。**

### 6.2 PR 要求
- 描述清楚变更动机与影响范围；涉及接口变更需同步更新 README 的「API 概览」。
- 附带必要测试；后端新增/修改逻辑应补充 `tests/` 用例。
- 通过本地校验：`pytest`（后端）+ `npm run build`（前端）。

### 6.3 接入新 Provider 的标准流程
1. `providers/` 新建类继承 `BaseProvider`，实现 `fetch_spaces` / `fetch_token_top`（按需 `fetch_conversations`），出站经 `assert_safe_host`。
2. 在 `registry.py` 的 `_REGISTRY` 注册实现，并在 `BUILTIN_PROVIDERS` 增加 `type_key / display_name / implemented`。
3. 重启后端，「Provider 管理」展示并可启用，项目创建表单即可选择。
4. 补充对应单测。

### 6.4 新增存储后端
1. 在 `repositories/` 实现 `base.py` 中全部抽象接口。
2. 在 `repositories/__init__.py` 的 `_BACKENDS` 登记。
3. 通过 `REPOSITORY_BACKEND` 切换，业务代码无需改动。

---

## 7. 关键约定速查

| 主题 | 约定 |
| --- | --- |
| 后端端口 | `8011`（uvicorn `--port 8011`） |
| 前端端口 | `5173`，`/api` 代理到 `8011` |
| 默认管理员 | `admin / admin`（仅首次初始化） |
| 数据来源标记 | `source`：`live`（真实）/ `mock`（回退） |
| 同步范围 | `app_count` / `token` / `conversations` |
| 全局角色 | `admin` / `user` |
| 项目角色 | `project_admin` / `member` |
| 密钥处理 | Fernet 加密落库 + 返回脱敏 |
| SSRF 默认 | 拒绝内网（`9./10./11./21./30.` 等），`ALLOW_INTERNAL_HOSTS` 放开 |
