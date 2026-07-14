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
  color: ['#16a34a', '#64748b', '#dc2626'],
  tooltip: { trigger: 'item', formatter: '{b}: {d}%' },
  legend: { bottom: 0 },
  series: [
    {
      name: '情感倾向',
      type: 'pie',
      radius: ['46%', '70%'],
      center: ['50%', '44%'],
      avoidLabelOverlap: true,
      label: { formatter: '{b}\n{d}%' },
      data: props.data
    }
  ]
}))

const { chartRef } = useEChart(() => option.value)
</script>
