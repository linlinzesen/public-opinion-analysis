<template>
  <div ref="chartRef" class="chart"></div>
</template>

<script setup>
import { computed } from 'vue'
import { useEChart } from './useEChart'

const props = defineProps({
  data: {
    type: Array,
    default: () => []
  }
})

const option = computed(() => ({
  color: ['#2563eb', '#f97316'],
  tooltip: { trigger: 'axis' },
  legend: { top: 0, data: ['热度指数', '发文量'] },
  grid: { top: 48, left: 42, right: 24, bottom: 32 },
  xAxis: {
    type: 'category',
    boundaryGap: false,
    data: props.data.map((item) => item.time)
  },
  yAxis: [
    { type: 'value', name: '热度', splitLine: { lineStyle: { color: '#edf2f7' } } },
    { type: 'value', name: '发文量', splitLine: { show: false } }
  ],
  series: [
    {
      name: '热度指数',
      type: 'line',
      smooth: true,
      symbolSize: 8,
      areaStyle: { opacity: 0.12 },
      data: props.data.map((item) => item.heat)
    },
    {
      name: '发文量',
      type: 'line',
      yAxisIndex: 1,
      smooth: true,
      symbolSize: 8,
      data: props.data.map((item) => item.posts)
    }
  ]
}))

const { chartRef } = useEChart(() => option.value)
</script>
