import { onBeforeUnmount, onMounted, shallowRef, watch } from 'vue'
import * as echarts from 'echarts'
import 'echarts-wordcloud'

export function useEChart(optionGetter) {
  const chartRef = shallowRef(null)
  let chart = null
  let observer = null

  const render = () => {
    if (!chartRef.value) return
    if (!chart) {
      chart = echarts.init(chartRef.value)
    }
    chart.setOption(optionGetter(), true)
  }

  onMounted(() => {
    render()
    observer = new ResizeObserver(() => chart?.resize())
    observer.observe(chartRef.value)
  })

  watch(optionGetter, render, { deep: true })

  onBeforeUnmount(() => {
    observer?.disconnect()
    chart?.dispose()
    chart = null
  })

  return {
    chartRef,
    render
  }
}
