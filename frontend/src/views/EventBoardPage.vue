<template>
  <div class="page-stack">
    <PageHeader
      eyebrow="事件发现"
      title="舆情事件看板"
      description="按更新时间或热度指数查看热点事件，快速进入详情研判。"
    />

    <section class="toolbar">
      <el-input
        v-model="query.keyword"
        clearable
        placeholder="搜索事件标题、摘要或关键词"
        :prefix-icon="Search"
        @keyup.enter="loadEvents"
        @clear="loadEvents"
      />
      <el-select v-model="query.riskLevel" clearable placeholder="风险等级" @change="loadEvents">
        <el-option label="高风险" value="高" />
        <el-option label="中风险" value="中" />
        <el-option label="低风险" value="低" />
      </el-select>
      <el-segmented v-model="query.sortBy" :options="sortOptions" @change="loadEvents" />
      <el-button type="primary" :icon="Refresh" :loading="loading" @click="loadEvents">刷新</el-button>
    </section>

    <section v-loading="loading" class="event-grid">
      <EventCard v-for="event in events" :key="event.id" :event="event" @open="openEvent" />
      <el-empty v-if="!events.length && !loading" description="暂无匹配事件" />
    </section>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Refresh, Search } from '@element-plus/icons-vue'
import PageHeader from '../components/PageHeader.vue'
import EventCard from '../components/EventCard.vue'
import { getEventsApi } from '../api/opinion'

const router = useRouter()
const loading = ref(false)
const events = ref([])

const query = reactive({
  keyword: '',
  riskLevel: '',
  sortBy: 'time'
})

const sortOptions = [
  { label: '时间排序', value: 'time' },
  { label: '热度排序', value: 'heat' }
]

async function loadEvents() {
  loading.value = true
  try {
    const result = await getEventsApi(query)
    events.value = result.records
  } finally {
    loading.value = false
  }
}

function openEvent(id) {
  router.push(`/events/${id}`)
}

onMounted(loadEvents)
</script>
