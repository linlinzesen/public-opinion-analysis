<template>
  <div class="page-stack">
    <PageHeader
      eyebrow="实时总览"
      title="系统首页"
      description="集中呈现今日舆情态势、重点风险事件和平台传播趋势。"
    >
      <template #actions>
        <el-button type="primary" :icon="Refresh" :loading="loading" @click="loadPage">刷新数据</el-button>
      </template>
    </PageHeader>

    <section class="stat-grid">
      <div v-for="item in statCards" :key="item.label" class="stat-card">
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
        <small>{{ item.hint }}</small>
      </div>
    </section>

    <div class="two-column">
      <ChartPanel title="全网热度走势" subtitle="近 7 日热度指数与发文量变化">
        <TrendLineChart :data="trend" />
      </ChartPanel>
      <ChartPanel title="重点风险事件" subtitle="按风险等级和热度综合排序">
        <div class="compact-list">
          <button v-for="event in topEvents" :key="event.id" class="compact-event" @click="router.push(`/events/${event.id}`)">
            <span :class="['risk-dot', `risk-dot--${event.riskLevel}`]"></span>
            <span>{{ event.title }}</span>
            <strong>{{ event.heat }}</strong>
          </button>
        </div>
      </ChartPanel>
    </div>

    <ChartPanel title="智能体助手" subtitle="基于当前舆情态势提供快速分析与建议">
      <div class="ai-home-card">
        <div class="ai-home-card__hero">
          <div>
            <p class="ai-home-card__eyebrow">AI 分析助手</p>
            <h3>把事件问答、趋势判断和报告生成直接带到首页</h3>
          </div>
          <el-button type="primary" @click="router.push('/events')">进入事件详情</el-button>
        </div>
        <div class="ai-home-card__body">
          <div class="ai-chat-shell">
            <div class="ai-chat-shell__header">
              <div class="ai-chat-shell__avatar">AI</div>
              <div>
                <strong>舆情智能体</strong>
                <p>你可以直接提问，或者点击下方建议词。</p>
              </div>
            </div>
            <div class="ai-chat-messages">
              <div v-for="message in chatMessages" :key="message.id" :class="['ai-chat-bubble', `ai-chat-bubble--${message.role}`]">
                <span class="ai-chat-bubble__icon">{{ message.role === 'assistant' ? '🤖' : '你' }}</span>
                <p>{{ message.content }}</p>
              </div>
            </div>
            <div class="ai-prompt-chips">
              <button v-for="preset in promptPresets" :key="preset" class="prompt-chip" @click="question = preset">
                {{ preset }}
              </button>
            </div>
            <el-input v-model="question" type="textarea" :rows="3" placeholder="例如：当前最值得关注的风险是什么？" />
            <div class="assistant-actions">
              <el-button type="primary" :loading="asking" @click="submitQuestion">问 AI</el-button>
              <el-button :loading="predicting" @click="loadPrediction">预测趋势</el-button>
            </div>
          </div>
        </div>
      </div>
    </ChartPanel>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import PageHeader from '../components/PageHeader.vue'
import ChartPanel from '../components/ChartPanel.vue'
import TrendLineChart from '../components/charts/TrendLineChart.vue'
import { getEventTrendApi, getEventsApi, getOverviewStatsApi } from '../api/opinion'
import { askEventQuestion, predictEventTrend } from '../api/llm'

const router = useRouter()
const loading = ref(false)
const stats = ref({})
const trend = ref([])
const events = ref([])
const question = ref('')
const answer = ref('')
const asking = ref(false)
const predicting = ref(false)
const predictionSummary = ref('')
const chatMessages = ref([
  {
    id: Date.now(),
    role: 'assistant',
    content: '我可以帮你快速判断当前舆情风险、总结关键事件并预测短期趋势。'
  }
])
const promptPresets = ['当前最值得关注的风险是什么？', '哪些事件最可能在短期内发酵？', '请帮我总结今日舆情结论。']

const statCards = computed(() => [
  { label: '监测事件', value: stats.value.eventTotal || 0, hint: `今日新增 ${stats.value.todayIncrement || 0}` },
  { label: '热点事件', value: stats.value.hotEventTotal || 0, hint: '高热度持续跟踪' },
  { label: '高风险事件', value: stats.value.highRiskTotal || 0, hint: '需优先研判' },
  { label: '监测平台', value: stats.value.platformTotal || 0, hint: '覆盖多信息源' },
  { label: '情感指数', value: stats.value.avgEmotionScore || 0, hint: '综合情绪评分' }
])

const topEvents = computed(() => events.value.slice(0, 6))

async function loadPage() {
  loading.value = true
  try {
    const [statsData, trendData, eventsData] = await Promise.all([
      getOverviewStatsApi(),
      getEventTrendApi('overview'),
      getEventsApi({ sortBy: 'heat' })
    ])
    stats.value = statsData
    trend.value = trendData
    events.value = eventsData.records
  } finally {
    loading.value = false
  }
}

function addMessage(role, content) {
  chatMessages.value.push({ id: Date.now() + Math.random(), role, content })
}

async function submitQuestion() {
  const content = question.value.trim()
  if (!content) {
    ElMessage.warning('请输入问题')
    return
  }
  addMessage('user', content)
  asking.value = true
  try {
    // 用首页真实数据构建上下文
    const topEventsSummary = events.value.slice(0, 5).map((e, i) =>
      `${i + 1}. ${e.title}（热度${e.heat}，风险${e.riskLevel}，来源${e.source}）`
    ).join('；')
    const sentimentSummary = `正面${stats.value.avgEmotionScore || 0}分`
    const statsSummary = `共监测${stats.value.eventTotal || 0}个事件，热点${stats.value.hotEventTotal || 0}个，高风险${stats.value.highRiskTotal || 0}个`

    const eventPayload = {
      title: '系统首页舆情总览',
      summary: `${statsSummary}。Top事件：${topEventsSummary}。情感指数：${sentimentSummary}。`,
      keywords: events.value.slice(0, 5).flatMap(e => e.keywords || []).slice(0, 10),
      sentiment_distribution: {
        positive: Math.round((stats.value.avgEmotionScore || 50) * 0.4),
        neutral: 35,
        negative: Math.round(100 - (stats.value.avgEmotionScore || 50) * 0.4 - 35)
      },
      trend_data: trend.value,
      platform_distribution: { 微博: 35, B站: 30, 今日头条: 20, 新闻: 15 }
    }
    const data = await askEventQuestion(eventPayload, content)
    answer.value = data.answer || '暂无回答'
    addMessage('assistant', answer.value)
    question.value = ''
  } catch (error) {
    const message = error?.response?.data?.error || error?.message || '请求失败'
    addMessage('assistant', `请求失败：${message}`)
    ElMessage.error(message)
  } finally {
    asking.value = false
  }
}

async function loadPrediction() {
  predicting.value = true
  try {
    const data = await predictEventTrend(trend.value)
    const trendLabel = data.trend || data.prediction || '平稳'
    const changeRatio = data.change_ratio ?? data.changeRatio ?? 0
    const percent = Number(changeRatio) * 100
    if (data.success || data.trend || data.predictions?.length) {
      predictionSummary.value = `趋势判断：${trendLabel}，变化率约 ${percent.toFixed(1)}%`
      addMessage('assistant', predictionSummary.value)
      ElMessage.success('趋势预测已生成')
      return
    }
    const message = data.error || '预测失败'
    addMessage('assistant', `预测失败：${message}`)
    ElMessage.warning(message)
  } catch (error) {
    const message = error?.response?.data?.error || error?.message || '预测请求失败'
    addMessage('assistant', `预测失败：${message}`)
    ElMessage.error(message)
  } finally {
    predicting.value = false
  }
}

onMounted(loadPage)
</script>
