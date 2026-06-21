# 对话记录：趋势 / 意图分布统计图表设计文档

日期：2026-06-21
状态：已确认，进入实现

## 1. 背景与目标

在「对话记录」页（`ConversationsView.vue`）增加两个统计小图表：

- **对话量趋势**（按天折线）
- **意图分布**（环形饼图）

目标：在浏览明细的同时，提供该筛选范围下的整体趋势与意图占比洞察。

## 2. 核心决策（已确认）

| # | 决策 |
| --- | --- |
| 数据联动 | **全联动**：图表随当前筛选（应用/时间/关键词/意图）一起统计 |
| 位置 | 过滤区下方、列表上方的 **可折叠面板**（默认收起） |
| 加载策略 | **懒加载**：收起不请求；展开时才拉取；展开状态下筛选变化重新拉取 |
| 聚合位置 | **后端 SQL 聚合**，单独接口，不塞进列表响应 |
| 图表类型 | 趋势=折线（按天）；意图=环形饼图（前 8 类 + 其他） |
| 意图过滤边界 | 指定 intent 时饼图只剩该类，加轻提示，不特殊排除（符合全联动） |

## 3. 后端聚合接口

```
GET /projects/{id}/conversation-stats
    ?app_biz_id=&begin=&end=&keyword=&intent=
→ require_project_access（成员可读，与列表一致）
→ ConversationStats {
    trend:   [{ date: "2026-06-20", count: 12 }, ...],   // 按日期升序
    intents: [{ name: "售后咨询", count: 30 }, ...],      // 按 count 降序
    total:   123
  }
```

聚合实现（`ConversationRepository` 新增方法，复用 `_apply_filters`）：
- `trend_by_day`：`GROUP BY substr(msg_create_time, 1, 10)`，`COUNT(*)`，按日期排序；忽略空 `msg_create_time`。
- `intent_distribution`：`GROUP BY intent_category`，`COUNT(*)` 降序；空意图聚为「未分类」。
- 字符串过滤均走参数绑定（防 SQLi）；`substr` 为 SQLite/MySQL 通用函数。

前端 api：`conversationApi.stats(projectId, query)`；类型 `ConversationStats` / `TrendPoint` / `IntentSlice`。

## 4. 前端组件

新建 `ConversationStatsPanel.vue`：
- 基于 `vue-echarts`，按需 `use([LineChart, PieChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])`。
- Props：`projectId: number`、`query: ConversationQuery`、`active: boolean`（面板是否展开）。
- 行为：`active` 变 true 时若未加载则加载；`active` 为 true 时 `query` 变化重新加载；父页「刷新」通过 query 引用变化或显式方法触发。
- 趋势折线：x=日期、y=对话量，平滑 + 面积渐变。
- 意图饼图：doughnut，前 8 类 + 其余归「其他」，图例展示。

父页 `ConversationsView.vue`：
- 过滤区下方加 `a-collapse`（key=`stats`），`v-model:activeKey` 控制展开。
- 把当前过滤条件（不含分页）作为 `query` 传入面板。

## 5. 边界处理

- 加载中：面板 `a-spin`。
- 空数据：趋势/意图各自 `a-empty`（"当前条件下暂无数据"）。
- 单日数据：折线单点正常显示。
- 意图被过滤：饼图上方轻提示"已按意图『xxx』过滤"。
- 请求失败：清空图表数据，不影响下方列表。

## 6. 测试

- 后端：`conversation-stats` 过滤后 trend/intents 计数正确；空意图归「未分类」；keyword 注入用例；成员可读、非成员 403。
- 前端：`vue-tsc` 通过；懒加载（收起不请求、展开请求）与筛选联动刷新验证。

## 7. 改动清单

后端：
- `repositories/base.py`、`repositories/sqlalchemy_impl.py`：新增 `trend_by_day`、`intent_distribution`。
- `schemas.py`：新增 `TrendPoint`、`IntentSlice`、`ConversationStats`。
- `routers/projects.py`：新增 `GET /conversation-stats`。
- `tests/test_api.py`：新增统计接口测试。

前端：
- `types.ts`：新增统计相关类型。
- `api/index.ts`：新增 `conversationApi.stats`。
- `components/ConversationStatsPanel.vue`（新建）。
- `views/ConversationsView.vue`：嵌入可折叠统计面板。
