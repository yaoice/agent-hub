<template>
  <a-spin :spinning="loading">
    <div class="dashboard">
      <!-- 工具栏 -->
      <div class="toolbar">
        <div class="toolbar-left">
          <span class="label">项目</span>
          <a-select
            v-model:value="projectId"
            placeholder="选择项目"
            style="width: 260px"
            :disabled="projects.length <= 1"
            @change="onSwitch"
          >
            <a-select-option v-for="p in projects" :key="p.id" :value="p.id">
              {{ p.name }}
            </a-select-option>
          </a-select>
          <a-tag v-if="resp" :color="resp.source === 'live' ? 'green' : 'orange'">
            {{ resp.source === 'live' ? '实时数据' : 'Mock 演示数据' }}
          </a-tag>
          <span v-if="resp?.updated_at" class="updated">
            同步于 {{ formatTime(resp.updated_at) }}
          </span>
        </div>
        <a-button :loading="loading" @click="load">
          <template #icon><ReloadOutlined /></template>
          刷新
        </a-button>
      </div>

      <template v-if="resp">
        <!-- 概览指标卡 -->
        <div class="stat-grid">
          <div class="stat-card" v-for="s in stats" :key="s.label" :style="{ '--accent': s.color }">
            <div class="stat-icon"><component :is="s.icon" :style="{ fontSize: '24px' }" /></div>
            <div class="stat-body">
              <div class="stat-value">{{ s.value }}</div>
              <div class="stat-label">{{ s.label }}</div>
            </div>
          </div>
        </div>

        <!-- Token 消耗排行 -->
        <a-card :bordered="false" class="block" title="Token 消耗 Top 排行（近 7 天）">
          <template #extra>
            <a-radio-group v-model:value="tokenDim" size="small" button-style="solid">
              <a-radio-button value="space">按空间</a-radio-button>
              <a-radio-button value="app">按应用</a-radio-button>
              <a-radio-button value="model">按模型</a-radio-button>
            </a-radio-group>
          </template>
          <TokenBarChart v-if="currentTokens.length" :items="currentTokens" :color="tokenColor" />
          <a-empty v-else description="暂无 Token 数据" />
        </a-card>

        <!-- 空间应用盘点 -->
        <a-card :bordered="false" class="block" title="空间应用盘点">
          <template #extra>
            <a-input
              v-model:value="keyword"
              placeholder="搜索空间/应用"
              allow-clear
              style="width: 220px"
            >
              <template #prefix><SearchOutlined /></template>
            </a-input>
          </template>
          <a-table
            :data-source="filteredSpaces"
            :columns="columns"
            row-key="space_id"
            :pagination="false"
            size="middle"
          >
            <template #expandedRowRender="{ record }">
              <div class="apps-wrap">
                <a-tag
                  v-for="app in record.apps"
                  :key="app.name"
                  :color="app.status === '运行中' ? 'green' : 'default'"
                  class="app-tag"
                  :class="{ clickable: app.app_biz_id }"
                  @click="goConversations(app)"
                >
                  {{ app.name }}
                  <span class="app-status">· {{ app.status }}</span>
                </a-tag>
                <span v-if="!record.apps.length" class="muted">该空间暂无应用</span>
              </div>
            </template>
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'app_count'">
                <a-badge
                  :count="record.app_count"
                  :overflow-count="999"
                  :number-style="{ backgroundColor: '#4f6ef7' }"
                />
              </template>
              <template v-else-if="column.key === 'running'">
                <span style="color: #52c41a">{{ record.running }}</span>
              </template>
              <template v-else-if="column.key === 'offline'">
                <span class="muted">{{ record.offline }}</span>
              </template>
              <template v-else-if="column.key === 'ratio'">
                <a-progress
                  :percent="record.app_count ? Math.round((record.running / record.app_count) * 100) : 0"
                  :stroke-width="10"
                />
              </template>
            </template>
          </a-table>
        </a-card>
      </template>

      <a-empty
        v-else-if="!loading"
        :description="emptyText"
      />
    </div>
  </a-spin>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  ReloadOutlined,
  SearchOutlined,
  ApartmentOutlined,
  AppstoreOutlined,
  BarChartOutlined,
  CheckCircleOutlined,
  MinusCircleOutlined,
  FolderOpenOutlined,
} from '@ant-design/icons-vue'
import { dashboardApi } from '@/api'
import type { AppEntry, DashboardResponse, ProjectBrief } from '@/types'
import TokenBarChart from '@/components/TokenBarChart.vue'
import { useAuthStore } from '@/stores/auth'
import { useProjectStore } from '@/stores/project'

const auth = useAuthStore()
const projectStore = useProjectStore()
const router = useRouter()

const loading = ref(false)
const projects = ref<ProjectBrief[]>([])
const projectId = ref<number>()
const resp = ref<DashboardResponse | null>(null)
const tokenDim = ref<'space' | 'app' | 'model'>('app')
const keyword = ref('')

const emptyText = computed(() =>
  projects.value.length ? '暂无数据' : '暂无可见项目，请联系管理员将你加入项目',
)

const columns = [
  { title: '空间名称', dataIndex: 'space_name', key: 'space_name', minWidth: 200 },
  {
    title: '应用总数',
    key: 'app_count',
    width: 120,
    sorter: (a: any, b: any) => a.app_count - b.app_count,
  },
  { title: '运行中', key: 'running', width: 110 },
  { title: '未上线', key: 'offline', width: 110 },
  { title: '运行占比', key: 'ratio', minWidth: 160 },
]

const stats = computed(() => {
  const o = resp.value?.data.overview
  if (!o) return []
  return [
    { label: '空间总数', value: o.total_spaces, color: '#4f6ef7', icon: ApartmentOutlined },
    { label: '有效空间', value: o.active_spaces, color: '#10b981', icon: FolderOpenOutlined },
    { label: '空壳空间', value: o.empty_spaces, color: '#9ca3af', icon: MinusCircleOutlined },
    { label: '应用总数', value: o.total_apps, color: '#7c3aed', icon: AppstoreOutlined },
    { label: '运行中', value: o.running, color: '#22c55e', icon: CheckCircleOutlined },
    { label: '未上线', value: o.offline, color: '#f59e0b', icon: BarChartOutlined },
  ]
})

const currentTokens = computed(() => resp.value?.data.token_top[tokenDim.value] || [])
const tokenColor = computed(
  () => ({ space: '#4f6ef7', app: '#7c3aed', model: '#10b981' })[tokenDim.value],
)

const filteredSpaces = computed(() => {
  const list = resp.value?.data.spaces || []
  const kw = keyword.value.trim().toLowerCase()
  if (!kw) return list
  return list.filter(
    (s) =>
      s.space_name.toLowerCase().includes(kw) ||
      s.apps.some((a) => a.name.toLowerCase().includes(kw)),
  )
})

function formatTime(t: string) {
  return new Date(t + (t.endsWith('Z') ? '' : 'Z')).toLocaleString('zh-CN')
}

function onSwitch() {
  projectStore.setCurrent(projectId.value)
  load()
}

function goConversations(app: AppEntry) {
  if (!app.app_biz_id) return
  projectStore.setCurrent(projectId.value)
  router.push({ name: 'conversations', query: { app_biz_id: app.app_biz_id } })
}

async function load() {
  if (!projects.value.length) {
    resp.value = null
    return
  }
  loading.value = true
  try {
    resp.value = await dashboardApi.fetch(projectId.value)
    projectId.value = resp.value.project_id
    projectStore.setCurrent(projectId.value)
  } catch {
    resp.value = null
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  // 确保有最新的可见项目
  if (!auth.user) await auth.fetchMe()
  projects.value = auth.visibleProjects
  // 优先使用上次选中的项目
  const stored = projectStore.currentProjectId
  if (stored && projects.value.some((p) => p.id === stored)) {
    projectId.value = stored
  } else if (projects.value.length) {
    projectId.value = projects.value[0].id
  }
  await load()
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
.toolbar-left {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.label {
  color: #5a6072;
  font-weight: 600;
}
.updated {
  color: #9aa0ad;
  font-size: 13px;
}
.muted {
  color: #8a909d;
}
.stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 16px;
  margin-bottom: 18px;
}
.stat-card {
  display: flex;
  align-items: center;
  gap: 14px;
  background: #fff;
  border-radius: 12px;
  padding: 18px 20px;
  box-shadow: 0 2px 10px rgba(31, 41, 64, 0.05);
  border-left: 4px solid var(--accent);
}
.stat-icon {
  width: 46px;
  height: 46px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--accent);
  background: color-mix(in srgb, var(--accent) 14%, #fff);
}
.stat-value {
  font-size: 26px;
  font-weight: 700;
  line-height: 1.1;
}
.stat-label {
  color: #8a909d;
  font-size: 13px;
  margin-top: 4px;
}
.block {
  margin-bottom: 18px;
  border-radius: 12px;
}
.apps-wrap {
  padding: 8px 4px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.app-tag {
  margin: 0;
}
.app-tag.clickable {
  cursor: pointer;
}
.app-tag.clickable:hover {
  opacity: 0.8;
}
.app-status {
  opacity: 0.7;
}
</style>
