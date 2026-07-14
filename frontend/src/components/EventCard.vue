<template>
  <article class="event-card" @click="$emit('open', event.id)">
    <div class="event-card__top">
      <el-tag :type="riskType" effect="dark">{{ event.riskLevel }}风险</el-tag>
      <span class="event-card__source">{{ event.source }}</span>
    </div>
    <h3>{{ event.title }}</h3>
    <p>{{ event.summary }}</p>
    <div class="event-card__tags">
      <el-tag v-for="word in event.keywords" :key="word" size="small" round>{{ word }}</el-tag>
    </div>
    <div class="event-card__footer">
      <span><el-icon><Clock /></el-icon>{{ event.occurTime }}</span>
      <strong><el-icon><TrendCharts /></el-icon>{{ event.heat }}</strong>
    </div>
  </article>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  event: {
    type: Object,
    required: true
  }
})

defineEmits(['open'])

const riskType = computed(() => {
  const map = {
    '高': 'danger',
    '中': 'warning',
    '低': 'success'
  }
  return map[props.event.riskLevel] || 'info'
})
</script>
