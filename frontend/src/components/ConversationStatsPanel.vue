<template>
  <a-spin :spinning="loading">
    <div class="stats-panel">
      <div class="chart-col">
        <div class="chart-title">对话量趋势（按天）</div>
        <v-chart v-if="trend.length" class="chart" :option="trendOption" autoresize />
        <a-empty v-else description="当前条件下暂无数据" />
      </div>
      <div class="chart-col">
        <div class="chart-title">
          意图分布
          <span v-if="query.intent" class="hint">· 已按意图「{{ query.intent }}」过滤</span>
        </div>
        <v-chart v-if="intents.length" class="chart" :option="intentOption" autoresize />
        <a-empty v-else description="当前条件下暂无数据" />
      </div>
    </div>
  </a-spin>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { use } from 'echarts/core'
import { LineChart, PieChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import { conversationApi } from '@/api'
import type { ConversationQuery, IntentSlice, TrendPoint } from '@/types'

use([LineChart, PieChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const props = defineProps<{
  projectId?: number
  query: ConversationQuery
  active: boolean
}>()

const loading = ref(false)
const loaded = ref(false)
const trend = ref<TrendPoint[]>([])
const intents = ref<IntentSlice[]>([])

const PIE_COLORS = [
  '#4f6ef7',
  '#7c3aed',
  '#10b981',
  '#f59e0b',
  '#ef4444',
  '#06b6d4',
  '#ec4899',
  '#84cc16',
  '#9ca3af',
]

async function load() {
  if (!props.projectId) {
    trend.value = []
    intents.value = []
    return
  }
  loading.value = true
  try {
    const resp = await conversationApi.stats(props.projectId, props.query)
    trend.value = resp.trend
    intents.value = collapseIntents(resp.intents)
    loaded.value = true
  } catch {
    trend.value = []
    intents.value = []
  } finally {
    loading.value = false
  }
}

// 前 8 类 + 其余归「其他」，避免饼图碎片化
function collapseIntents(list: IntentSlice[]): IntentSlice[] {
  if (list.length <= 9) return list
  const top = list.slice(0, 8)
  const rest = list.slice(8).reduce((s, i) => s + i.count, 0)
  return [...top, { name: '其他', count: rest }]
}

const trendOption = computed(() => ({
  grid: { left: 8, right: 16, top: 20, bottom: 8, containLabel: true },
  tooltip: { trigger: 'axis' },
  xAxis: {
    type: 'category',
    data: trend.value.map((p) => p.date),
    boundaryGap: false,
    axisLabel: { color: '#5a6072' },
  },
  yAxis: {
    type: 'value',
    minInterval: 1,
    splitLine: { lineStyle: { color: '#f0f2f7' } },
  },
  series: [
    {
      type: 'line',
      smooth: true,
      symbolSize: 6,
      data: trend.value.map((p) => p.count),
      itemStyle: { color: '#4f6ef7' },
      lineStyle: { width: 2 },
      areaStyle: {
        color: {
          type: 'linear',
          x: 0,
          y: 0,
          x2: 0,
          y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(79,110,247,0.25)' },
            { offset: 1, color: 'rgba(79,110,247,0.02)' },
          ],
        },
      },
    },
  ],
}))

const intentOption = computed(() => ({
  tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
  legend: { type: 'scroll', bottom: 0, textStyle: { color: '#5a6072' } },
  series: [
    {
      type: 'pie',
      radius: ['42%', '68%'],
      center: ['50%', '46%'],
      avoidLabelOverlap: true,
      itemStyle: { borderColor: '#fff', borderWidth: 2 },
      label: { show: false },
      data: intents.value.map((it, i) => ({
        name: it.name,
        value: it.count,
        itemStyle: { color: PIE_COLORS[i % PIE_COLORS.length] },
      })),
    },
  ],
}))

// 懒加载：首次展开才加载；展开状态下筛选变化重新加载
watch(
  () => props.active,
  (act) => {
    if (act && !loaded.value) load()
  },
  { immediate: true },
)
watch(
  () => props.query,
  () => {
    if (props.active) load()
  },
  { deep: true },
)

defineExpose({ reload: load })
</script>

<style scoped>
.stats-panel {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
@media (max-width: 900px) {
  .stats-panel {
    grid-template-columns: 1fr;
  }
}
.chart-col {
  min-height: 280px;
}
.chart-title {
  font-weight: 600;
  color: #5a6072;
  margin-bottom: 8px;
}
.hint {
  font-weight: 400;
  font-size: 12px;
  color: #9aa0ad;
}
.chart {
  height: 260px;
  width: 100%;
}
</style>
