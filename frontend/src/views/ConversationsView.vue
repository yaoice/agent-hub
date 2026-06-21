<template>
  <div class="conversations">
    <!-- 工具栏 -->
    <div class="toolbar">
      <div class="toolbar-left">
        <span class="label">项目</span>
        <a-select
          v-model:value="projectId"
          placeholder="选择项目"
          style="width: 260px"
          :disabled="projects.length <= 1"
          @change="onSwitchProject"
        >
          <a-select-option v-for="p in projects" :key="p.id" :value="p.id">
            {{ p.name }}
          </a-select-option>
        </a-select>
      </div>
      <div class="toolbar-right">
        <a-button :loading="loading" @click="reload">
          <template #icon><ReloadOutlined /></template>
          刷新
        </a-button>
        <template v-if="canManage">
          <a-dropdown-button
            type="primary"
            :loading="syncing"
            :disabled="syncing"
            :trigger="['click']"
            @click="onSync(false)"
          >
            <SyncOutlined v-if="!syncing" />
            {{ syncing ? (cancelling ? '终止中…' : (isFull ? '回补中…' : '同步中…')) : '同步对话' }}
            <template #icon><DownOutlined /></template>
            <template #overlay>
              <a-menu @click="onSyncMenuClick">
                <a-menu-item key="full" :disabled="syncing">
                  <CloudSyncOutlined />
                  <span style="margin-left: 6px">全量回补</span>
                </a-menu-item>
              </a-menu>
            </template>
          </a-dropdown-button>
          <a-popconfirm
            v-if="syncing"
            title="确认终止本次同步？已拉取的部分会保留入库。"
            ok-text="终止"
            cancel-text="继续"
            @confirm="onCancel"
          >
            <a-button danger :loading="cancelling">
              <template #icon><StopOutlined /></template>
              终止
            </a-button>
          </a-popconfirm>
          <a-button :disabled="!records.length" @click="onExport">
            <template #icon><DownloadOutlined /></template>
            导出 CSV
          </a-button>
        </template>
      </div>
    </div>

    <!-- 同步进度 -->
    <a-alert
      v-if="syncJob && (syncing || syncJob.status === 'failed')"
      class="sync-progress"
      :type="syncJob.status === 'failed' ? 'error' : 'info'"
      show-icon
    >
      <template #message>
        <template v-if="syncJob.status === 'failed'">
          同步失败：{{ syncJob.error || '未知错误' }}
        </template>
        <template v-else>
          {{ syncJob.incremental ? '增量' : '全量'
          }}{{ cancelling ? '终止中（等待当前应用结束）…' : '同步中' }}：已处理
          {{ syncJob.app_done }}/{{ syncJob.app_total || '?' }} 个应用，累计拉取
          {{ syncJob.fetched }} 条
          <a-progress :percent="syncPercent" status="active" size="small" />
        </template>
      </template>
    </a-alert>

    <template v-if="projects.length">
      <!-- 过滤区 -->
      <a-card :bordered="false" class="block filter-card">
        <div class="filters">
          <a-select
            v-model:value="filters.app_biz_id"
            placeholder="全部应用"
            allow-clear
            show-search
            option-filter-prop="label"
            style="width: 240px"
            @change="onFilterChange"
          >
            <a-select-option
              v-for="a in appOptions"
              :key="a.app_biz_id"
              :value="a.app_biz_id"
              :label="a.app_name || a.app_biz_id"
            >
              {{ a.app_name || a.app_biz_id }}
            </a-select-option>
          </a-select>
          <a-range-picker
            v-model:value="dateRange"
            show-time
            :placeholder="['开始时间', '结束时间']"
            style="width: 360px"
            @change="onFilterChange"
          />
          <a-input
            v-model:value="filters.intent"
            placeholder="意图分类"
            allow-clear
            style="width: 160px"
            @press-enter="onFilterChange"
          />
          <a-input-search
            v-model:value="filters.keyword"
            placeholder="搜索问题 / 回答"
            allow-clear
            style="width: 240px"
            @search="onFilterChange"
          />
          <a-button v-if="hasActiveFilter" @click="resetFilters">重置</a-button>
          <a-dropdown :trigger="['click']" placement="bottomRight">
            <a-button>
              <template #icon><SettingOutlined /></template>
              列设置
            </a-button>
            <template #overlay>
              <div class="col-setting">
                <div class="col-setting-head">
                  <span>显示列</span>
                  <a class="col-reset" @click="resetColumns">恢复默认</a>
                </div>
                <a-checkbox
                  v-for="c in ALL_COLUMNS"
                  :key="c.key"
                  :checked="visibleColumnKeys.includes(c.key)"
                  @change="(e: any) => toggleColumn(c.key, e.target.checked)"
                >
                  {{ c.title }}
                </a-checkbox>
              </div>
            </template>
          </a-dropdown>
        </div>
      </a-card>

      <!-- 统计图表（默认收起，懒加载，随筛选联动） -->
      <a-collapse v-model:activeKey="statsActiveKey" :bordered="false" class="block stats-collapse">
        <a-collapse-panel key="stats" header="统计图表">
          <ConversationStatsPanel
            ref="statsPanelRef"
            :project-id="projectId"
            :query="statsQuery"
            :active="statsActiveKey.includes('stats')"
          />
        </a-collapse-panel>
      </a-collapse>

      <!-- 对话列表 -->
      <a-card :bordered="false" class="block">
        <a-table
          :data-source="records"
          :columns="columns"
          row-key="id"
          size="middle"
          :loading="loading"
          :pagination="pagination"
          @change="onTableChange"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'question' || column.key === 'answer'">
              <a-tooltip :title="record[column.key]">
                <span class="ellipsis-2">{{ record[column.key] || '—' }}</span>
              </a-tooltip>
            </template>
            <template v-else-if="column.key === 'app_name'">
              <a-tooltip :title="record.app_name || record.app_biz_id">
                <span>{{ record.app_name || record.app_biz_id || '—' }}</span>
              </a-tooltip>
            </template>
            <template v-else-if="column.key === 'intent'">
              <a-tooltip :title="record.intent">
                <span>{{ record.intent || '—' }}</span>
              </a-tooltip>
            </template>
            <template v-else-if="column.key === 'intent_category'">
              <a-tag v-if="record.intent_category" color="blue">{{ record.intent_category }}</a-tag>
              <span v-else class="muted">—</span>
            </template>
            <template v-else-if="column.key === 'user'">
              <span>{{ record.user_nickname || record.user_biz_id || '匿名' }}</span>
            </template>
            <template v-else-if="column.key === 'action'">
              <a @click="openDetail(record)">详情</a>
            </template>
          </template>
        </a-table>
      </a-card>
    </template>

    <a-empty v-else description="暂无可见项目，请联系管理员将你加入项目" />

    <!-- 详情抽屉 -->
    <a-drawer
      v-model:open="detailVisible"
      title="对话详情"
      width="560"
      placement="right"
    >
      <template v-if="current">
        <a-descriptions :column="1" bordered size="small">
          <a-descriptions-item label="应用名称">
            {{ current.app_name || '—' }}
          </a-descriptions-item>
          <a-descriptions-item label="应用ID">{{ current.app_biz_id }}</a-descriptions-item>
          <a-descriptions-item label="时间">{{ current.create_time || '—' }}</a-descriptions-item>
          <a-descriptions-item label="用户">
            {{ current.user_nickname || '—' }}
            <span class="muted" v-if="current.user_biz_id">（{{ current.user_biz_id }}）</span>
          </a-descriptions-item>
          <a-descriptions-item label="会话ID">{{ current.session_id || '—' }}</a-descriptions-item>
          <a-descriptions-item label="意图">{{ current.intent || '—' }}</a-descriptions-item>
          <a-descriptions-item label="意图分类">{{ current.intent_category || '—' }}</a-descriptions-item>
        </a-descriptions>

        <div class="qa-block">
          <div class="qa-title">问题</div>
          <div class="qa-content question">{{ current.question || '—' }}</div>
        </div>
        <div class="qa-block">
          <div class="qa-title">回答</div>
          <div class="qa-content answer">{{ current.answer || '—' }}</div>
        </div>
      </template>
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, h, onMounted, onUnmounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message, Modal } from 'ant-design-vue'
import dayjs, { type Dayjs } from 'dayjs'
import {
  ReloadOutlined,
  CloudSyncOutlined,
  SyncOutlined,
  DownOutlined,
  DownloadOutlined,
  SettingOutlined,
  StopOutlined,
} from '@ant-design/icons-vue'
import { conversationApi } from '@/api'
import type {
  ConversationAppOption,
  ConversationItem,
  ConversationQuery,
  ProjectBrief,
  SyncJob,
} from '@/types'
import ConversationStatsPanel from '@/components/ConversationStatsPanel.vue'
import { useAuthStore } from '@/stores/auth'
import { useProjectStore } from '@/stores/project'

const auth = useAuthStore()
const projectStore = useProjectStore()
const route = useRoute()
const router = useRouter()

const loading = ref(false)
const syncing = ref(false)
const cancelling = ref(false)
const syncJob = ref<SyncJob | null>(null)
let pollTimer: number | undefined
const projects = ref<ProjectBrief[]>([])
const projectId = ref<number>()
const records = ref<ConversationItem[]>([])
const total = ref(0)
const appOptions = ref<ConversationAppOption[]>([])

const detailVisible = ref(false)
const current = ref<ConversationItem | null>(null)

const dateRange = ref<[Dayjs, Dayjs] | undefined>()
const filters = reactive({
  app_biz_id: undefined as string | undefined,
  intent: undefined as string | undefined,
  keyword: undefined as string | undefined,
})
const page = reactive({ current: 1, pageSize: 50 })

// 统计图表面板：默认收起，懒加载
const statsActiveKey = ref<string[]>([])
const statsPanelRef = ref<{ reload: () => void } | null>(null)

// 统计用的过滤条件（不含分页），供图表面板联动
const statsQuery = computed<ConversationQuery>(() => {
  const q: ConversationQuery = {}
  if (filters.app_biz_id) q.app_biz_id = filters.app_biz_id
  if (filters.intent) q.intent = filters.intent.trim()
  if (filters.keyword) q.keyword = filters.keyword.trim()
  if (dateRange.value) {
    q.begin = dateRange.value[0].format('YYYY-MM-DD HH:mm:ss')
    q.end = dateRange.value[1].format('YYYY-MM-DD HH:mm:ss')
  }
  return q
})

// 全局 admin 或当前项目的 project_admin 可同步/导出
const canManage = computed(() => {
  if (auth.isAdmin) return true
  const p = projects.value.find((x) => x.id === projectId.value)
  return p?.project_role === 'project_admin'
})

const hasActiveFilter = computed(
  () => !!(filters.app_biz_id || filters.intent || filters.keyword || dateRange.value),
)

// 当前进行中的同步是否为全量回补（incremental === false），用于按钮 loading 区分
const isFull = computed(() => syncJob.value?.incremental === false)

// 同步进度百分比（按已处理应用数估算）
const syncPercent = computed(() => {
  const j = syncJob.value
  if (!j || !j.app_total) return 0
  return Math.min(100, Math.round((j.app_done / j.app_total) * 100))
})

// 全部可选列（展示顺序即此处顺序）
const ALL_COLUMNS = [
  { title: '时间', dataIndex: 'create_time', key: 'create_time', width: 170 },
  { title: '应用名称', key: 'app_name', width: 180, ellipsis: true },
  { title: '应用ID', dataIndex: 'app_biz_id', key: 'app_biz_id', width: 160, ellipsis: true },
  { title: '用户', key: 'user', width: 130, ellipsis: true },
  { title: '问题', key: 'question', minWidth: 220 },
  { title: '回答', key: 'answer', minWidth: 220 },
  { title: '意图', key: 'intent', width: 200, ellipsis: true },
  { title: '意图分类', key: 'intent_category', width: 120 },
  { title: '操作', key: 'action', width: 70, fixed: 'right' },
]
const DEFAULT_COLUMN_KEYS = [
  'create_time',
  'app_name',
  'question',
  'answer',
  'intent',
  'intent_category',
  'action',
]
const COLUMN_STORE_KEY = 'conv_visible_columns'

// 用户选择展示的列（持久化到 localStorage）
const visibleColumnKeys = ref<string[]>(loadVisibleColumns())

function loadVisibleColumns(): string[] {
  try {
    const raw = localStorage.getItem(COLUMN_STORE_KEY)
    if (raw) {
      const arr = JSON.parse(raw)
      if (Array.isArray(arr) && arr.length) return arr
    }
  } catch {
    /* 忽略解析失败 */
  }
  return [...DEFAULT_COLUMN_KEYS]
}

function toggleColumn(key: string, checked: boolean) {
  const set = new Set(visibleColumnKeys.value)
  if (checked) set.add(key)
  else set.delete(key)
  // 按 ALL_COLUMNS 原顺序保存，保证展示顺序稳定
  visibleColumnKeys.value = ALL_COLUMNS.filter((c) => set.has(c.key)).map((c) => c.key)
  localStorage.setItem(COLUMN_STORE_KEY, JSON.stringify(visibleColumnKeys.value))
}

function resetColumns() {
  visibleColumnKeys.value = [...DEFAULT_COLUMN_KEYS]
  localStorage.setItem(COLUMN_STORE_KEY, JSON.stringify(visibleColumnKeys.value))
}

// 实际渲染的列：按选择过滤，保持 ALL_COLUMNS 顺序
const columns = computed(() => ALL_COLUMNS.filter((c) => visibleColumnKeys.value.includes(c.key)))

const pagination = computed(() => ({
  current: page.current,
  pageSize: page.pageSize,
  total: total.value,
  showSizeChanger: true,
  pageSizeOptions: ['20', '50', '100', '200'],
  showTotal: (t: number) => `共 ${t} 条`,
}))

function buildQuery(): ConversationQuery {
  const q: ConversationQuery = {
    limit: page.pageSize,
    offset: (page.current - 1) * page.pageSize,
  }
  if (filters.app_biz_id) q.app_biz_id = filters.app_biz_id
  if (filters.intent) q.intent = filters.intent.trim()
  if (filters.keyword) q.keyword = filters.keyword.trim()
  if (dateRange.value) {
    q.begin = dateRange.value[0].format('YYYY-MM-DD HH:mm:ss')
    q.end = dateRange.value[1].format('YYYY-MM-DD HH:mm:ss')
  }
  return q
}

async function load() {
  if (!projectId.value) {
    records.value = []
    total.value = 0
    return
  }
  loading.value = true
  try {
    const resp = await conversationApi.list(projectId.value, buildQuery())
    records.value = resp.items
    total.value = resp.total
  } catch {
    records.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

async function loadApps() {
  if (!projectId.value) {
    appOptions.value = []
    return
  }
  try {
    appOptions.value = await conversationApi.apps(projectId.value)
  } catch {
    appOptions.value = []
  }
}

function reload() {
  load()
  if (statsActiveKey.value.includes('stats')) statsPanelRef.value?.reload()
}

function onFilterChange() {
  page.current = 1
  load()
}

function resetFilters() {
  filters.app_biz_id = undefined
  filters.intent = undefined
  filters.keyword = undefined
  dateRange.value = undefined
  onFilterChange()
}

function onTableChange(pg: { current?: number; pageSize?: number }) {
  page.current = pg.current || 1
  page.pageSize = pg.pageSize || 50
  load()
}

function onSwitchProject() {
  projectStore.setCurrent(projectId.value)
  page.current = 1
  filters.app_biz_id = undefined
  loadApps()
  load()
  resumeLatestJob()
}

function openDetail(record: ConversationItem) {
  current.value = record
  detailVisible.value = true
}

function stopPoll() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = undefined
  }
}

async function onSyncJobDone(job: SyncJob) {
  stopPoll()
  syncing.value = false
  cancelling.value = false
  if (job.status === 'success') {
    message.success(job.message || '同步完成')
    await loadApps()
    await load()
    if (statsActiveKey.value.includes('stats')) statsPanelRef.value?.reload()
  } else if (job.status === 'cancelled') {
    message.info(job.message || '已终止同步')
    await loadApps()
    await load()
    if (statsActiveKey.value.includes('stats')) statsPanelRef.value?.reload()
  } else if (job.status === 'failed') {
    message.error(job.error || '同步失败')
  }
}

const JOB_DONE_STATUSES = ['success', 'failed', 'cancelled']
const JOB_ACTIVE_STATUSES = ['pending', 'running', 'cancelling']

async function pollJob(jobId: number) {
  const pid = projectId.value
  if (!pid) return
  const tick = async () => {
    try {
      const job = await conversationApi.getSyncJob(pid, jobId)
      syncJob.value = job
      if (job.status === 'cancelling') cancelling.value = true
      if (JOB_DONE_STATUSES.includes(job.status)) {
        await onSyncJobDone(job)
      }
    } catch {
      stopPoll()
      syncing.value = false
      cancelling.value = false
    }
  }
  await tick()
  if (syncing.value && !pollTimer) {
    pollTimer = window.setInterval(tick, 1500)
  }
}

async function onSync(full = false) {
  if (!projectId.value || syncing.value) return
  syncing.value = true
  cancelling.value = false
  syncJob.value = null
  try {
    const job = await conversationApi.startSyncJob(projectId.value, { full })
    syncJob.value = job
    await pollJob(job.id)
  } catch {
    // 429（限频）/409（已有任务进行中）等由全局拦截器提示
    syncing.value = false
  }
}

// 拆分按钮下拉菜单点击：全量回补走二次确认（重操作）
function onSyncMenuClick({ key }: { key: string }) {
  if (key !== 'full' || syncing.value) return
  Modal.confirm({
    title: '全量回补对话',
    icon: h(CloudSyncOutlined, { style: { color: 'var(--ah-primary, #2f6bff)' } }),
    content:
      '将按时间范围重新拉取该项目下全部对话并去重入库，耗时较长，期间可随时点击「终止」。',
    okText: '开始回补',
    cancelText: '取消',
    centered: true,
    onOk: () => onSync(true),
  })
}

async function onCancel() {
  const pid = projectId.value
  const job = syncJob.value
  if (!pid || !job || cancelling.value) return
  cancelling.value = true
  try {
    await conversationApi.cancelSyncJob(pid, job.id)
    message.info('已请求终止，等待当前应用结束后停止')
  } catch {
    // 409（任务已结束）等由全局拦截器提示
    cancelling.value = false
  }
}

// 进入页面或切换项目时，恢复仍在进行中的同步任务进度
async function resumeLatestJob() {
  stopPoll()
  syncJob.value = null
  syncing.value = false
  cancelling.value = false
  if (!projectId.value || !canManage.value) return
  try {
    const job = await conversationApi.latestSyncJob(projectId.value)
    if (job && JOB_ACTIVE_STATUSES.includes(job.status)) {
      syncJob.value = job
      syncing.value = true
      if (job.status === 'cancelling') cancelling.value = true
      await pollJob(job.id)
    }
  } catch {
    /* 忽略恢复失败 */
  }
}

function csvEscape(v: string): string {
  const s = (v ?? '').toString()
  if (/[",\n]/.test(s)) return '"' + s.replace(/"/g, '""') + '"'
  return s
}

function onExport() {
  const head = [
    '时间',
    '应用名称',
    '应用ID',
    '用户昵称',
    '用户ID',
    '会话ID',
    '意图',
    '意图分类',
    '问题',
    '回答',
  ]
  const rows = records.value.map((r) => [
    r.create_time,
    r.app_name || r.app_biz_id,
    r.app_biz_id,
    r.user_nickname,
    r.user_biz_id,
    r.session_id,
    r.intent,
    r.intent_category,
    r.question,
    r.answer,
  ])
  const csv =
    '\uFEFF' + [head, ...rows].map((row) => row.map(csvEscape).join(',')).join('\n')
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `conversations_${projectId.value}_${dayjs().format('YYYYMMDD_HHmmss')}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

onMounted(async () => {
  // 每次进入页面都刷新可见项目，确保新建/变更的项目即时出现在下拉中
  await auth.fetchMe()
  projects.value = auth.visibleProjects

  // 下钻进入：URL 带 app_biz_id 时预置过滤；带 app_name 时用于无记录应用的显示
  const appQ = route.query.app_biz_id
  const appNameQ = route.query.app_name
  if (typeof appQ === 'string' && appQ) filters.app_biz_id = appQ

  const stored = projectStore.currentProjectId
  if (stored && projects.value.some((p) => p.id === stored)) {
    projectId.value = stored
  } else if (projects.value.length) {
    projectId.value = projects.value[0].id
  }
  projectStore.setCurrent(projectId.value)

  await Promise.all([loadApps(), load()])

  // 该应用没有对话记录时不在选项列表里，补一个临时项，避免过滤框只显示一串应用 ID
  if (
    typeof appQ === 'string' &&
    appQ &&
    typeof appNameQ === 'string' &&
    appNameQ &&
    !appOptions.value.some((a) => a.app_biz_id === appQ)
  ) {
    appOptions.value = [{ app_biz_id: appQ, app_name: appNameQ }, ...appOptions.value]
  }

  resumeLatestJob()

  // 清理 URL query，避免刷新后过滤被反复带入
  if (route.query.app_biz_id || route.query.app_name) {
    router.replace({ query: {} })
  }
})

onUnmounted(() => {
  stopPoll()
})
</script>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 18px;
}
.toolbar-left,
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.label {
  color: #5a6072;
  font-weight: 600;
}
.muted {
  color: #8a909d;
}
.block {
  margin-bottom: 18px;
  border-radius: 12px;
}
.sync-progress {
  margin-bottom: 18px;
  border-radius: 12px;
}
.filter-card :deep(.ant-card-body) {
  padding: 16px;
}
.filters {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.col-setting {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px 16px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.12);
  min-width: 140px;
}
.col-setting-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 2px;
  color: #5a6072;
  font-weight: 600;
}
.col-reset {
  font-weight: 400;
  font-size: 12px;
}
.col-setting :deep(.ant-checkbox-wrapper) {
  margin-left: 0;
}
.ellipsis-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.qa-block {
  margin-top: 18px;
}
.qa-title {
  font-weight: 600;
  margin-bottom: 6px;
  color: #5a6072;
}
.qa-content {
  white-space: pre-wrap;
  word-break: break-word;
  padding: 12px 14px;
  border-radius: 8px;
  line-height: 1.6;
}
.qa-content.question {
  background: #f2f5ff;
}
.qa-content.answer {
  background: #f6f7f9;
}
</style>
