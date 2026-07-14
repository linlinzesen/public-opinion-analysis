<template>
  <div ref="chartRef" class="chart"></div>
</template>

<script setup>
import { computed } from 'vue'
import { useEChart } from './useEChart'

const props = defineProps({
  historyData: {
    type: Array,
    default: () => []
  },
  predictionData: {
    type: Array,
    default: () => []
  }
})

const option = computed(() => ({
  color: ['#c47e5d', '#e6a23c'],
  tooltip: { trigger: 'axis' },
  legend: { top: 0, data: ['历史热度', '预测热度'] },
  grid: { top: 44, left: 40, right: 24, bottom: 32 },
  xAxis: {
    type: 'time',
    axisLabel: {
      formatter: (value) => {
        const date = new Date(value)
        return `${date.getMonth() + 1}-${date.getDate()} ${date.getHours()}点`
      }
    }
  },
  yAxis: {
    type: 'value',
    min: 0,
    splitLine: { lineStyle: { color: '#f5e7db' } }
  },
  series: [
    {
      name: '历史热度',
      type: 'line',
      smooth: true,
      symbolSize: 6,
      data: (props.historyData || []).map((item) => [item.time, item.value])
    },
    {
      name: '预测热度',
      type: 'line',
      smooth: true,
      symbolSize: 6,
      lineStyle: { type: 'dashed' },
      data: (props.predictionData || []).map((item) => [item.time, item.value])
    }
  ]
}))

const { chartRef } = useEChart(() => option.value)
</script>
