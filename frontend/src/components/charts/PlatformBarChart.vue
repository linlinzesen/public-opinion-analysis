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
  color: ['#0891b2'],
  tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
  grid: { top: 24, left: 48, right: 24, bottom: 42 },
  xAxis: {
    type: 'category',
    data: props.data.map((item) => item.platform),
    axisLabel: { interval: 0 }
  },
  yAxis: {
    type: 'value',
    splitLine: { lineStyle: { color: '#edf2f7' } }
  },
  series: [
    {
      name: '声量',
      type: 'bar',
      barWidth: 28,
      itemStyle: { borderRadius: [4, 4, 0, 0] },
      data: props.data.map((item) => item.count)
    }
  ]
}))

const { chartRef } = useEChart(() => option.value)
</script>
