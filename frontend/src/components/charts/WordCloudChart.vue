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

const palette = ['#2563eb', '#0891b2', '#16a34a', '#f97316', '#dc2626', '#7c3aed', '#334155']

const option = computed(() => ({
  tooltip: {},
  series: [
    {
      type: 'wordCloud',
      shape: 'circle',
      left: 'center',
      top: 'center',
      width: '92%',
      height: '92%',
      sizeRange: [16, 50],
      rotationRange: [-30, 30],
      gridSize: 10,
      textStyle: {
        color: () => palette[Math.floor(Math.random() * palette.length)]
      },
      emphasis: {
        focus: 'self',
        textStyle: {
          shadowBlur: 8,
          shadowColor: 'rgba(15, 23, 42, 0.2)'
        }
      },
      data: props.data
    }
  ]
}))

const { chartRef } = useEChart(() => option.value)
</script>
