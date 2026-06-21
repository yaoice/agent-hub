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
          <a-dropdown-button type="primary" :loading="syncing" @click="onSync(false)">
            <template #icon><CloudSyncOutlined /></template>
            {{ syncing ? '同步中…' : '同步对话' }}
            <template #overlay>
              <a-menu @click="onSync(true)">
                <a-menu-item key="full" :disabled="syncing">全量回补</a-menu-item>
              </a-menu>
            </template>
          </a-dropdown-button>
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
          {{ syncJob.incremental ? '增量' : '全量' }}同步中：已处理
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
            style="width: 220px"
            @change="onFilterChange"
          >
            <a-select-option v-for="a in appOptions" :key="a" :value="a">{{ a }}</a-select-option>
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
          <a-descriptions-item label="应用">{{ current.app_biz_id }}</a-descriptions-item>
          <a-descriptions-item label="时间">{{ current.create_time || '—' }}</a-descriptions-item>
          <a-descriptions-item label="用户">
            {{ current.user_nickname || '—' }}
            <span class="muted" v-if="current.user_biz_id">（{{ current.user_biz_id }}）</span>
          </a-descriptions-item>
          <a-descriptions-item label="会话ID">{{ current.session_id || '—' }}</a-descriptions-item>
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
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import dayjs, { type Dayjs } from 'dayjs'
import {
  ReloadOutlined,
  CloudSyncOutlined,
  DownloadOutlined,
} from '@ant-design/icons-vue'
import { conversationApi } from '@/api'
import type { ConversationItem, ConversationQuery, ProjectBrief, SyncJob } from '@/types'
import ConversationStatsPanel from '@/components/ConversationStatsPanel.vue'
import { useAuthStore } from '@/stores/auth'
import { useProjectStore } from '@/stores/project'

const auth = useAuthStore()
const projectStore = useProjectStore()
const route = useRoute()
const router = useRouter()

const loading = ref(false)
const syncing = ref(false)
const syncJob = ref<SyncJob | null>(null)
let pollTimer: number | undefined
const projects = ref<ProjectBrief[]>([])
const projectId = ref<number>()
const records = ref<ConversationItem[]>([])
const total = ref(0)
const appOptions = ref<string[]>([])

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

// 同步进度百分比（按已处理应用数估算）
const syncPercent = computed(() => {
  const j = syncJob.value
  if (!j || !j.app_total) return 0
  return Math.min(100, Math.round((j.app_done / j.app_total) * 100))
})

const columns = [
  { title: '时间', dataIndex: 'create_time', key: 'create_time', width: 170 },
  { title: '应用', dataIndex: 'app_biz_id', key: 'app_biz_id', width: 140, ellipsis: true },
  { title: '用户', key: 'user', width: 130, ellipsis: true },
  { title: '问题', key: 'question', minWidth: 220 },
  { title: '回答', key: 'answer', minWidth: 220 },
  { title: '意图分类', key: 'intent_category', width: 120 },
  { title: '操作', key: 'action', width: 70, fixed: 'right' },
]

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
  if (job.status === 'success') {
    message.success(job.message || '同步完成')
    await loadApps()
    await load()
    if (statsActiveKey.value.includes('stats')) statsPanelRef.value?.reload()
  } else if (job.status === 'failed') {
    message.error(job.error || '同步失败')
  }
}

async function pollJob(jobId: number) {
  const pid = projectId.value
  if (!pid) return
  const tick = async () => {
    try {
      const job = await conversationApi.getSyncJob(pid, jobId)
      syncJob.value = job
      if (job.status === 'success' || job.status === 'failed') {
        await onSyncJobDone(job)
      }
    } catch {
      stopPoll()
      syncing.value = false
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

// 进入页面或切换项目时，恢复仍在进行中的同步任务进度
async function resumeLatestJob() {
  stopPoll()
  syncJob.value = null
  syncing.value = false
  if (!projectId.value || !canManage.value) return
  try {
    const job = await conversationApi.latestSyncJob(projectId.value)
    if (job && (job.status === 'pending' || job.status === 'running')) {
      syncJob.value = job
      syncing.value = true
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
  const head = ['时间', '应用', '用户昵称', '用户ID', '会话ID', '意图分类', '问题', '回答']
  const rows = records.value.map((r) => [
    r.create_time,
    r.app_biz_id,
    r.user_nickname,
    r.user_biz_id,
    r.session_id,
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
  if (!auth.user) await auth.fetchMe()
  projects.value = auth.visibleProjects

  // 下钻进入：URL 带 app_biz_id 时预置过滤
  const appQ = route.query.app_biz_id
  if (typeof appQ === 'string' && appQ) filters.app_biz_id = appQ

  const stored = projectStore.currentProjectId
  if (stored && projects.value.some((p) => p.id === stored)) {
    projectId.value = stored
  } else if (projects.value.length) {
    projectId.value = projects.value[0].id
  }
  projectStore.setCurrent(projectId.value)

  await Promise.all([loadApps(), load()])
  resumeLatestJob()

  // 清理 URL query，避免刷新后过滤被反复带入
  if (route.query.app_biz_id) {
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
