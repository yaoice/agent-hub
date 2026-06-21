# 应用对话记录：运营面板展示设计文档

日期：2026-06-21
状态：已确认，进入实现

## 1. 背景与目标

后端已具备对话记录的**存储与同步**能力，但前端缺少浏览入口：

- 模型 `ConversationRecord` 已落库（问题/回答、意图分类、用户信息、会话、发生时间、raw）。
- 同步链路已就绪：`POST /projects/{id}/sync`（scope=`conversations`）与 `POST /projects/{id}/sync-conversations`。
- 查询接口 `GET /projects/{id}/conversations` 已存在，但仅支持 `app_biz_id` + 分页。
- 「项目管理」里「应用对话记录」只是一个**同步范围选项**，数据进库后**无任何页面可看**。

目标：为对话记录提供一个**统一的浏览/查看入口**，同时满足"日常运营浏览"与"按应用下钻"两种使用方式。

## 2. 核心决策（已确认）

| # | 决策 |
| --- | --- |
| 入口定位 | 新增一级菜单 **`对话记录`**，与「运营看板」平级 |
| 可见范围 | **全员可见**（按各自可见项目过滤），不加 `adminOnly` |
| 权限分级 | 普通成员**只读**；管理员额外可**同步 / 导出**（按钮级区分） |
| 下钻联动 | 「运营看板 → 空间应用盘点」点击应用 → 跳转 `/conversations?app_biz_id=xxx` 带过滤 |
| 单一数据源 | 浏览与下钻最终落到**同一页面**，避免在看板内塞大表格 |
| 导出方案 | 先用**前端 CSV**导出当前过滤结果（零后端改动），量大再演进 |

## 3. 菜单与路由

- 左侧导航在 `运营看板` 下方新增 `对话记录`（图标 `MessageOutlined` / `CommentOutlined`）。
- 路由：`/conversations`，`meta.title = '对话记录'`，**不设 `adminOnly`**。
- 复用 `projectStore.currentProjectId`，与看板共享项目选择，切项目联动刷新。
- 下钻：应用标签点击 → `router.push('/conversations?app_biz_id=' + appBizId)`，页面读取 query 自动选中应用过滤。

## 4. 页面布局（竖向三段式，复用看板卡片风格）

1. **顶部工具栏**
   - 左：项目下拉 + 数据来源标签（live/mock）+ 上次同步时间
   - 右：`刷新`；管理员额外 `同步对话`、`导出`
2. **过滤区**（一行紧凑筛选）
   - 应用 `app_biz_id`（下拉，来自当前项目有记录的应用；下钻自动选中）
   - 时间范围（按 `msg_create_time`）
   - 关键词（搜 question/answer）
   - 意图分类 `intent_category`（下拉）
3. **对话列表**（`a-table` 分页）
   - 列：时间、应用、用户（昵称/biz_id）、问题（截断+tooltip）、回答（截断+tooltip）、意图分类、会话ID
   - 点击行 → 右侧 `a-drawer` 展示完整问答、用户信息、会话、`raw`（折叠 JSON）

## 5. 数据流与接口

### 读取（浏览，全员）
```
/conversations 页
  → GET /projects/{id}/conversations?app_biz_id=&begin=&end=&keyword=&intent=&limit=&offset=
  → router.list_conversations（require_project_access，成员可读）
  → ConversationRepository.list_records / count
  → ConversationPage { total, items[] }
```

**增量改动**（扩展，不破坏现有结构）：
- `ConversationRepository.list_records` / `count`：新增可选参数 `begin`、`end`、`keyword`、`intent`。
  - `keyword`：`LIKE` 匹配 question/answer，**参数绑定**防注入。
  - `msg_create_time` 为字符串，`YYYY-MM-DD HH:MM:SS` 按字典序比较即可。
- `routers.list_conversations`：上述条件作为 `Query` 参数透传。
- 新增 `GET /projects/{id}/conversation-apps`：返回有对话记录的 `app_biz_id` 去重列表（供过滤下拉），或复用看板快照中的 apps。

### 写入（同步，仅 admin）
- 复用 `POST /projects/{id}/sync-conversations`（`require_project_admin`），前端管理员才显示按钮。

### 导出（仅 admin）
- 前端将当前过滤结果分页拉全后导出 CSV，零后端改动；量大再考虑后端流式导出。

### 前端 api / types
- `api/index.ts` 新增 `conversationApi.list(projectId, params)`、`conversationApi.apps(projectId)`。
- `types.ts` 新增 `ConversationItem`、`ConversationPage`。

## 6. 异常处理与边界

- 无可见项目：复用看板空态文案。
- 表为空：`a-empty` 提示"暂无对话记录，请联系管理员先同步"。
- 下钻 `app_biz_id` 无记录：列表空态，过滤器保留该值并可清除。
- 长文本：列表截断 + tooltip，完整内容入抽屉；`raw` 折叠展示。
- 关键词：`LIKE` 走参数绑定（防 SQLi）；空白忽略。
- 分页：默认 `limit=50`，上限钳制 ≤200。
- 权限：成员请求 admin-only 同步接口返回 403，前端按钮不展示（双重保险）。
- 时间过滤：begin/end 非法时后端忽略或 422，前端用日期组件规避。

## 7. 测试

- **后端**：`list_records` 各过滤条件单测（keyword 注入用例、空结果、分页边界）；权限测试（成员可读、非成员 403、同步需 project_admin）。
- **前端**：页面加载 / 切项目 / 下钻带参 / 空态 / 抽屉打开的基本交互验证。

## 8. 改动清单（实现参考）

后端：
- `repositories/base.py`、`repositories/sqlalchemy_impl.py`：扩展 `list_records` / `count` 过滤参数。
- `routers/projects.py`：`list_conversations` 增加 Query 参数；新增 `conversation-apps` 接口。

前端：
- `router/index.ts`：新增 `/conversations` 路由。
- `layouts/MainLayout.vue`：新增「对话记录」菜单项。
- `views/ConversationsView.vue`（新建）：工具栏 + 过滤区 + 列表 + 详情抽屉。
- `views/DashboardView.vue`：应用标签点击下钻跳转。
- `api/index.ts`、`types.ts`：新增对话相关 api 与类型。
