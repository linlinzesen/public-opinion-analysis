<template>
  <div class="page-stack">
    <PageHeader
      :eyebrow="event?.id || '事件详情'"
      :title="event?.title || '事件详情'"
      :description="event?.summary || ''"
    >
      <template #actions>
        <el-button :icon="Back" @click="router.back()">返回</el-button>
        <el-button type="primary" :icon="Document" :loading="reportLoading" @click="createReport">生成报告</el-button>
      </template>
    </PageHeader>

    <section v-if="event" class="detail-summary">
      <div>
        <span>风险等级</span>
        <strong>{{ event.riskLevel }}</strong>
      </div>
      <div>
        <span>情感倾向</span>
        <strong>{{ event.sentiment }}</strong>
      </div>
      <div>
        <span>热度指数</span>
        <strong>{{ event.heat }}</strong>
      </div>
      <div>
        <span>首发平台</span>
        <strong>{{ event.source }}</strong>
      </div>
      <div>
        <span>发生时间</span>
        <strong>{{ event.occurTime }}</strong>
      </div>
    </section>

    <ChartPanel title="事件发展趋势" subtitle="展示事件热度与发文量的时间变化">
      <TrendLineChart :data="trend" />
    </ChartPanel>

    <div class="two-column">
      <ChartPanel title="群众情感倾向分布">
        <SentimentPieChart :data="sentiment" />
      </ChartPanel>
      <ChartPanel title="平台分布">
        <PlatformBarChart :data="platforms" />
      </ChartPanel>
    </div>

    <div class="two-column">
      <ChartPanel title="高频词云">
        <WordCloudChart :data="words" />
      </ChartPanel>
      <ChartPanel title="智能分析助手" min-height="360px">
        <div class="assistant-stack">
          <div class="assistant-preview">
            <el-tag :type="predictionTrend === '上升' ? 'danger' : predictionTrend === '下降' ? 'success' : 'info'">
              {{ predictionTrend || '待预测' }}
            </el-tag>
            <span>未来 24 小时传播趋势</span>
          </div>
          <el-input
            v-model="question"
            type="textarea"
            :rows="3"
            placeholder="例如：当前事件的主要风险是什么？"
          />
          <div class="assistant-actions">
            <el-button type="primary" :loading="asking" @click="submitQuestion">问 AI</el-button>
            <el-button :loading="predicting" @click="loadPrediction">预测趋势</el-button>
          </div>
          <div v-if="answer" class="assistant-answer">
            <h4>智能回答</h4>
            <p>{{ answer }}</p>
          </div>
          <div v-if="predictionSummary" class="assistant-answer">
            <h4>预测结果</h4>
            <p>{{ predictionSummary }}</p>
          </div>
        </div>
      </ChartPanel>
    </div>

    <ChartPanel title="未来 24 小时传播预测" subtitle="基于历史热度趋势做线性回归预测">
      <PredictionLineChart :history-data="trend" :prediction-data="predictions" />
    </ChartPanel>

    <ChartPanel title="自动生成舆情分析报告" min-height="360px">
      <div v-if="reportText" class="report-box">
        <div class="report-box__content" v-html="renderMarkdown(reportText)"></div>
      </div>
      <el-empty v-else description="点击生成报告查看结构化分析结果" />
      <div class="assistant-actions" style="margin-top: 16px;">
        <el-button type="primary" :loading="reportLoading" @click="createReport">生成报告</el-button>
      </div>
    </ChartPanel>

    <ChartPanel title="传播路径追踪" subtitle="事件溯源与关键传播节点分析" min-height="360px">
      <div v-if="propagation?.success !== false" v-loading="propLoading">
        <div v-if="propagation?.origin" class="propagation-section">
          <h4>初始爆料</h4>
          <p><strong>{{ propagation.origin.user_name }}</strong>（{{ propagation.origin.platform }}）于 {{ propagation.origin.time }}</p>
          <p class="propagation-preview">{{ propagation.origin.content_preview?.slice(0, 150) || '暂无内容' }}</p>
        </div>
        <div v-if="propagation?.timeline?.length" class="propagation-section">
          <h4>关键传播节点</h4>
          <el-timeline>
            <el-timeline-item
              v-for="(item, idx) in propagation.timeline"
              :key="idx"
              :timestamp="item.time"
              :color="idx === 0 ? '#409EFF' : '#E6A23C'"
            >
              <strong>{{ item.stage }}</strong> — {{ item.actor }}
            </el-timeline-item>
          </el-timeline>
        </div>
        <div v-if="propagation?.summary" class="propagation-summary">
          <el-tag type="info">覆盖平台: {{ propagation.summary.total_platforms }}</el-tag>
          <el-tag type="warning">关键节点: {{ propagation.summary.total_amplifiers }}</el-tag>
          <el-tag :type="propagation.summary.has_media_intervention ? 'danger' : 'info'">
            {{ propagation.summary.has_media_intervention ? '已有官媒介入' : '暂无官媒介入' }}
          </el-tag>
          <el-tag>传播深度: {{ propagation.summary.propagation_depth }} 层</el-tag>
        </div>
      </div>
      <el-empty v-else description="传播路径数据未加载" />
    </ChartPanel>

    <div class="two-column">
      <ChartPanel title="信息可信度检测" subtitle="虚假文本识别与置信度评估">
        <div v-if="credibility?.summary">
          <div class="credibility-stats">
            <div class="credibility-card">
              <span>平均可信度</span>
              <strong>{{ credibility.summary.avg_credibility }}</strong>
            </div>
            <div class="credibility-card">
              <span>可信比例</span>
              <strong>{{ credibility.summary.trusted_ratio }}%</strong>
            </div>
            <div class="credibility-card">
              <span>高风险比例</span>
              <strong class="text-danger">{{ credibility.summary.high_risk_ratio }}%</strong>
            </div>
          </div>
          <div v-if="credibility.results?.[0]" style="margin-top: 12px;">
            <el-tag
              :type="credibility.results[0].verdict === '可信' ? 'success' : credibility.results[0].verdict === '存疑' ? 'warning' : 'danger'"
            >
              研判结果: {{ credibility.results[0].verdict }}
            </el-tag>
            <span style="margin-left: 8px; font-size: 12px; color: #909399;">
              方法: {{ credibility.results[0].method }} | 分数: {{ credibility.results[0].credibility }}
            </span>
          </div>
        </div>
        <div class="assistant-actions" style="margin-top: 12px;">
          <el-button type="warning" :loading="false" @click="checkCredibility">检测可信度</el-button>
        </div>
        <el-empty v-if="!credibility" description="点击按钮检测信息可信度" :image-size="40" />
      </ChartPanel>

      <ChartPanel title="生命周期阶段" subtitle="舆情事件所处的发展阶段判断">
        <div v-if="lifecycle" class="lifecycle-card">
          <el-tag
            size="large"
            :type="lifecycle.stage === '高潮期' ? 'danger' : lifecycle.stage === '成长期' ? 'warning' : lifecycle.stage === '衰退期' ? 'info' : ''"
          >
            {{ lifecycle.stage }}
          </el-tag>
          <p style="margin-top: 12px;">{{ lifecycle.description }}</p>
          <p style="font-size: 12px; color: #909399;">置信度: {{ ((lifecycle.confidence || 0) * 100).toFixed(0) }}%</p>
        </div>
        <el-empty v-else description="请先点击预测趋势以获取生命周期判断" :image-size="40" />
      </ChartPanel>
    </div>

    <ChartPanel v-if="similarEvents.length" title="相似历史事件" subtitle="基于关键词匹配的相关事件">
      <div class="similar-events-list">
        <div v-for="(evt, idx) in similarEvents" :key="idx" class="similar-event-item">
          <span>{{ evt.event_title || evt.title }}</span>
          <el-tag size="small" type="info">{{ ((evt.similarity_score || 0) * 100).toFixed(0) }}% 相似</el-tag>
        </div>
      </div>
    </ChartPanel>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Back, Document } from '@element-plus/icons-vue'
import PageHeader from '../components/PageHeader.vue'
import ChartPanel from '../components/ChartPanel.vue'
import TrendLineChart from '../components/charts/TrendLineChart.vue'
import PredictionLineChart from '../components/charts/PredictionLineChart.vue'
import SentimentPieChart from '../components/charts/SentimentPieChart.vue'
import PlatformBarChart from '../components/charts/PlatformBarChart.vue'
import WordCloudChart from '../components/charts/WordCloudChart.vue'
import {
  checkCredibilityApi,
  generateReportApi,
  getEventDetailApi,
  getEventPlatformApi,
  getEventPropagationApi,
  getEventSentimentApi,
  getEventTrendApi,
  getEventWordCloudApi,
  getSimilarEventsApi
} from '../api/opinion'
import { askEventQuestion, generateEventReport, predictEventTrend } from '../api/llm'

const route = useRoute()
const router = useRouter()
const event = ref(null)
const trend = ref([])
const sentiment = ref([])
const platforms = ref([])
const words = ref([])
const report = ref(null)
const reportLoading = ref(false)
const question = ref('')
const answer = ref('')
const asking = ref(false)
const predictions = ref([])
const predictionTrend = ref('')
const predicting = ref(false)
const predictionSummary = ref('')
const reportText = ref('')
const propagation = ref(null)
const lifecycle = ref(null)
const credibility = ref(null)
const similarEvents = ref([])
const propLoading = ref(false)

const eventPayload = computed(() => ({
  id: event.value?.id,
  title: event.value?.title || '',
  summary: event.value?.summary || '',
  keywords: event.value?.keywords || [],
  occurTime: event.value?.occurTime || '',
  source: event.value?.source || '',
  sentiment_distribution: {
    positive: sentiment.value?.find((item) => item.name === '正面')?.value || 0,
    neutral: sentiment.value?.find((item) => item.name === '中性')?.value || 0,
    negative: sentiment.value?.find((item) => item.name === '负面')?.value || 0
  },
  trend_data: trend.value || [],
  platform_distribution: Object.fromEntries((platforms.value || []).map((item) => [item.platform, item.count]))
}))

async function loadDetail() {
  const id = route.params.id
  const [detailData, trendData, sentimentData, platformData, wordData] = await Promise.all([
    getEventDetailApi(id),
    getEventTrendApi(id),
    getEventSentimentApi(id),
    getEventPlatformApi(id),
    getEventWordCloudApi(id)
  ])
  event.value = detailData
  trend.value = trendData
  sentiment.value = sentimentData
  platforms.value = platformData
  words.value = wordData
}

async function createReport() {
  reportLoading.value = true
  try {
    const result = await generateEventReport(eventPayload.value)
    if (result?.report) {
      reportText.value = result.report
      report.value = {
        title: event.value?.title || '舆情分析报告',
        conclusion: result.report.split('\n').slice(0, 3).join(' '),
        suggestions: ['请查看下方结构化报告内容']
      }
      ElMessage.success('报告已生成')
      return
    }
    const fallback = await generateReportApi(route.params.id)
    report.value = fallback
    reportText.value = fallback?.conclusion || ''
  } finally {
    reportLoading.value = false
  }
}

async function submitQuestion() {
  if (!question.value.trim()) {
    ElMessage.warning('请输入问题')
    return
  }
  asking.value = true
  try {
    const data = await askEventQuestion(eventPayload.value, question.value.trim())
    answer.value = data.answer || '暂无回答'
    ElMessage.success('智能问答已返回')
  } finally {
    asking.value = false
  }
}

async function loadPrediction() {
  if (!trend.value?.length) {
    ElMessage.warning('当前事件暂无足够的历史热度数据')
    return
  }
  predicting.value = true
  try {
    const data = await predictEventTrend(trend.value)
    if (data.success) {
      predictions.value = data.predictions || []
      predictionTrend.value = data.trend || '平稳'
      lifecycle.value = data.lifecycle || null
      const lifecycleInfo = data.lifecycle
        ? ` | 生命周期: ${data.lifecycle.stage} (置信度 ${((data.lifecycle.confidence || 0) * 100).toFixed(0)}%)`
        : ''
      predictionSummary.value = `趋势判断：${data.trend || '平稳'}，变化率约 ${((data.change_ratio || 0) * 100).toFixed(1)}%${lifecycleInfo}`
      ElMessage.success('趋势预测已生成')
      return
    }
    ElMessage.warning(data.error || '趋势预测失败')
  } finally {
    predicting.value = false
  }
}

async function loadPropagation() {
  propLoading.value = true
  try {
    const data = await getEventPropagationApi(route.params.id)
    propagation.value = data
  } finally {
    propLoading.value = false
  }
}

async function checkCredibility() {
  try {
    const data = await checkCredibilityApi(route.params.id, [event.value?.summary || ''])
    credibility.value = data
    ElMessage.success('可信度检测完成')
  } catch {
    ElMessage.warning('可信度检测暂不可用')
  }
}

async function loadSimilarEvents() {
  try {
    const data = await getSimilarEventsApi(route.params.id)
    similarEvents.value = data.similar_events || []
  } catch {
    similarEvents.value = []
  }
}

function renderMarkdown(text) {
  if (!text) return ''
  // 先转义 HTML 特殊字符，防止乱码和 XSS
  const escaped = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')

  const lines = escaped.split('\n')
  const result = []
  let inList = false

  for (const line of lines) {
    // 空行
    if (!line.trim()) {
      if (inList) { result.push('</ul>'); inList = false }
      result.push('<br>')
      continue
    }

    // 一级标题
    const h1Match = line.match(/^# (.+)/)
    if (h1Match) {
      if (inList) { result.push('</ul>'); inList = false }
      result.push(`<h2>${h1Match[1]}</h2>`)
      continue
    }

    // 二级标题
    const h2Match = line.match(/^## (.+)/)
    if (h2Match) {
      if (inList) { result.push('</ul>'); inList = false }
      result.push(`<h3>${h2Match[1]}</h3>`)
      continue
    }

    // 三级标题
    const h3Match = line.match(/^### (.+)/)
    if (h3Match) {
      if (inList) { result.push('</ul>'); inList = false }
      result.push(`<h4>${h3Match[1]}</h4>`)
      continue
    }

    // 无序列表项
    const ulMatch = line.match(/^[-*]\s+(.+)/)
    if (ulMatch) {
      if (!inList) { result.push('<ul>'); inList = true }
      result.push(`<li>${ulMatch[1]}</li>`)
      continue
    }

    // 有序列表项
    const olMatch = line.match(/^\d+\.\s+(.+)/)
    if (olMatch) {
      if (!inList) { result.push('<ul>'); inList = true }
      result.push(`<li>${olMatch[1]}</li>`)
      continue
    }

    if (inList) { result.push('</ul>'); inList = false }

    // 普通段落：加粗转换
    const bolded = line.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    result.push(`<p>${bolded}</p>`)
  }

  if (inList) { result.push('</ul>') }
  return result.join('\n')
}

onMounted(() => {
  loadDetail()
  loadPropagation()
  loadSimilarEvents()
})
</script>
