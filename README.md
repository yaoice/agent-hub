# 智能体运营中心 · Web 看板系统（Agent Hub）

聚合腾讯云智能体平台（LKE）等 Provider 的运营指标，以**项目（Project）**为中心提供可视化数据面板。
数据来源于 `scripts/` 中的三个脚本能力：

| 能力 | 对应接口 | 看板呈现 |
| --- | --- | --- |
| 空间盘点 | `ListSpace` | 空间总数 / 有效空间 / 空壳空间 |
| 应用盘点 | `ListApp` | 应用总数、运行中 / 未上线、各空间应用明细 |
| Token 消耗 | `DescribeTopModelToken` | 按空间 / 应用 / 模型 的 Token Top 排行图 |

## 技术栈

- **前端**：Vue 3 + TypeScript + Vite + Pinia + Ant Design Vue + ECharts
- **后端**：Python + FastAPI + SQLAlchemy + 仓储抽象层（SQLite / MySQL）
- **鉴权**：JWT（bcrypt 密码哈希）
- **取数**：项目「手动同步」实时拉取并写入数据库快照；运营看板与用户面板统一从库读取，真实调用失败自动回退内置 **Mock 演示数据**

## 核心概念

- **Provider（类型目录）**：内置 Provider 类型，仅做启用/禁用，不存凭证。
  - 私有化 ADP（`tencent_lke`）：已实现，默认启用。
  - 公有云 ADP（`adp_public`）：尚未实现，前端置灰、不可启用。
- **Project（项目）**：选择一个 Provider 类型并录入自己的 `SECRET_ID/SECRET_KEY/HOST/region`，分配成员，手动同步数据。看板按项目切换展示。
- **User（用户）** 与 **项目成员**：
  - 全局角色：`admin`（可进管理面板、默认可见全部项目）/ `user`（仅可见所属项目）。
  - 项目级角色：`project_admin`（可管理本项目成员）/ `member`。
  - 用户属于多个项目时，看板顶部支持项目切换。

## 功能面板

- **登录系统**：内置默认管理员 **admin / admin**。
- **运营看板**：按项目切换的空间/应用盘点 + Token 消耗排行可视化，数据来自最新同步快照。
- **管理员面板**：
  - **用户管理**：列表/搜索、详情（含所属项目）、新增、编辑、角色分配、禁用/启用。
  - **项目管理**：项目 CRUD（选 Provider + 录凭证）、成员管理、**手动同步**（点击同步弹窗按范围勾选：应用数量 / 应用对话记录 / token消耗，支持全选，按勾选动态生成请求）。
  - **Provider 管理**：内置类型目录的启用/禁用（未实现项置灰）。

## 安全设计

- 项目密钥使用 Fernet 对称加密**落库**，接口返回一律**脱敏**。
- 所有 SQL 通过 SQLAlchemy 参数绑定，杜绝注入。
- **SSRF 防护**：项目 HOST 默认禁止解析到内网/私有地址（含 9./10./11./21./30. 等网段），如确需内网网关，设 `ALLOW_INTERNAL_HOSTS=true`。
- **越权防护**：看板/项目读取校验项目可见性；项目写/成员管理需 `admin` 或 `project_admin`。
- 禁用用户即时失效（已签发 token 也无法使用）；不可禁用自身；系统保留至少一名启用的管理员。
- 应用密钥、管理员初始口令等敏感项均走环境变量（env-only）。

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

### 2. 前端

```bash
cd frontend
npm install
npm run dev        # 默认 http://localhost:5173 ，已将 /api 代理至后端 8011
```

### 3. 登录使用

浏览器打开前端地址，使用 **admin / admin** 登录：
- 「运营看板」：选择项目查看空间/应用盘点与 Token 排行。
- 「用户管理 / 项目管理 / Provider 管理」（管理员）：维护用户、配置项目并手动同步数据。

## 测试

```bash
cd backend
uv run --with pytest --with httpx pytest tests -q
```

## 对话记录同步（DescribeMsgLogList）

`providers/tencent_lke.py` 的 `fetch_conversations(app_biz_id, begin, end, max_records)` 基于 `DescribeMsgLogList` 接口拉取指定应用的对话记录（内部自动分页）。项目同步对话时会遍历该项目下所有空间的所有应用逐个拉取，并以 `record_id` 在项目维度去重后写入 `conversation_records` 表。

```
POST /api/projects/{id}/sync-conversations   # 项目管理员；body 可选 {begin,end,max_records_per_app}，默认最近 7 天
GET  /api/projects/{id}/conversations         # 项目成员可见；?app_biz_id=&limit=&offset= 分页查询
```

> 未配置有效密钥或真实调用失败时，对话同步同样回退 Mock 演示数据。

## 按范围同步（统一 /sync）

项目「同步」按钮支持按范围勾选，前端按勾选动态生成 `scopes` 调用统一端点：

```
POST /api/projects/{id}/sync
body: {
  "scopes": ["app_count", "token", "conversations"],  // 三者子集；留空默认 [app_count, token]
  "conv_begin": null, "conv_end": null,               // 对话范围可选，默认最近 7 天
  "max_records_per_app": 500
}
```

- `app_count`（应用数量）与 `token`（token消耗）为看板数据，按 scope **局部拉取**并与最新快照合并，未勾选部分沿用历史，保证看板始终完整。
- `conversations`（应用对话记录）遍历应用拉取并去重入库。
- 返回 `{ok, source, message, scopes, details}`，`details` 含各部分同步明细。

## 目录结构

```
agent-hub/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI 入口
│   │   ├── config.py          # 配置（env-only，含 REPOSITORY_BACKEND）
│   │   ├── database.py        # 数据库会话
│   │   ├── models.py          # User / Provider / Project / ProjectMember / MetricSnapshot / ConversationRecord
│   │   ├── schemas.py         # Pydantic 模型
│   │   ├── security.py        # JWT / bcrypt / Fernet
│   │   ├── deps.py            # 鉴权依赖（admin / project_access / project_admin）
│   │   ├── seed.py            # 建库 + 默认数据
│   │   ├── repositories/      # 仓储抽象层（base + sqlalchemy_impl + 工厂）
│   │   ├── services/          # normalize / sync / dashboard / conversations
│   │   ├── routers/           # auth / users / projects / providers / dashboard
│   │   └── providers/         # Provider 抽象层（base/registry/tencent_lke/mock/ssrf）
│   └── tests/                 # pytest 用例
├── frontend/
│   └── src/
│       ├── api/               # axios 封装
│       ├── stores/            # Pinia（auth / project）
│       ├── router/            # 路由 + 守卫
│       ├── layouts/           # 主布局（含管理面板子菜单）
│       ├── components/        # 图表组件
│       └── views/             # 登录 / 看板 / admin（用户/项目/Provider）
├── docs/plans/                # 设计文档
└── scripts/                   # 原始业务脚本
```

## 接入新的 Provider

1. 在 `backend/app/providers/` 新建类，继承 `BaseProvider`，实现 `fetch_spaces()` 与 `fetch_token_top()`。
2. 在 `providers/registry.py` 的 `_REGISTRY` 注册实现类，并在 `BUILTIN_PROVIDERS` 增加目录元数据（`type_key` / `display_name` / `implemented`）。
3. 重启后端，「Provider 管理」会展示该类型，启用后即可在项目创建表单中选择。
