<template>
  <v-chart class="chart" :option="option" autoresize />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { use } from 'echarts/core'
import { BarChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import type { TokenItem } from '@/types'

use([BarChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const props = defineProps<{ items: TokenItem[]; color: string }>()

function fmt(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K'
  return String(n)
}

const option = computed(() => {
  const data = [...props.items].reverse()
  return {
    grid: { left: 8, right: 60, top: 10, bottom: 10, containLabel: true },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (p: any) => {
        const it = p[0]
        return `${it.name}<br/>Token：${it.value.toLocaleString()}`
      },
    },
    xAxis: { type: 'value', axisLabel: { formatter: (v: number) => fmt(v) }, splitLine: { lineStyle: { color: '#f0f2f7' } } },
    yAxis: {
      type: 'category',
      data: data.map((d) => d.name),
      axisLabel: { color: '#5a6072' },
    },
    series: [
      {
        type: 'bar',
        data: data.map((d) => d.value),
        barWidth: '55%',
        itemStyle: { color: props.color, borderRadius: [0, 4, 4, 0] },
        label: { show: true, position: 'right', formatter: (p: any) => fmt(p.value), color: '#909399' },
      },
    ],
  }
})
</script>

<style scoped>
.chart {
  height: 320px;
  width: 100%;
}
</style>
