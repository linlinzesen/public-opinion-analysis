<template>
  <div class="page-stack">
    <PageHeader
      eyebrow="系统管理"
      title="爬取控制面板"
      description="配置爬虫参数、查看调度状态，手动触发数据采集与分析流水线。"
    />

    <!-- 调度状态 -->
    <section class="status-bar">
      <div class="status-card">
        <el-icon :size="20"><Clock /></el-icon>
        <div>
          <span>调度间隔</span>
          <strong>{{ status.interval_minutes || 30 }} 分钟</strong>
        </div>
      </div>
      <div class="status-card">
        <el-icon :size="20"><VideoPlay /></el-icon>
        <div>
          <span>上次执行</span>
          <strong>{{ lastRun || '暂无记录' }}</strong>
        </div>
      </div>
      <div class="status-card">
        <el-tag :type="running ? 'warning' : 'success'" size="large">
          {{ running ? '运行中' : '空闲' }}
        </el-tag>
      </div>
    </section>

    <!-- 爬取配置 -->
    <section class="config-section">
      <h3>
        <el-icon><Setting /></el-icon>
        爬取配置
      </h3>

      <div class="config-grid">
        <div class="config-item">
          <label>评论数 / 平台</label>
          <el-input-number v-model="config.commentsPerEvent" :min="100" :max="2000" :step="100" />
        </div>
        <div class="config-item">
          <label>请求延迟 (秒)</label>
          <el-input-number v-model="config.delay" :min="0.3" :max="5" :step="0.2" :precision="1" />
        </div>
        <div class="config-item">
          <label>数据模式（可多选）</label>
          <el-checkbox-group v-model="config.modes" class="platform-checks">
            <el-checkbox label="real">真实爬取</el-checkbox>
            <el-checkbox label="mock">兜底生成</el-checkbox>
          </el-checkbox-group>
        </div>
      </div>

      <h4 style="margin-top: 20px;">目标平台</h4>
      <el-checkbox-group v-model="config.platforms" class="platform-checks">
        <el-checkbox label="bilibili">B站</el-checkbox>
        <el-checkbox label="weibo">微博</el-checkbox>
        <el-checkbox label="toutiao">今日头条</el-checkbox>
        <el-checkbox label="xiaohongshu">小红书</el-checkbox>
      </el-checkbox-group>

      <h4 style="margin-top: 20px;">舆情事件（可编辑关键词）</h4>
      <div class="event-list">
        <div v-for="(evt, idx) in config.events" :key="idx" class="event-row">
          <el-input v-model="evt.keyword" placeholder="关键词" size="small" style="width: 160px;" />
          <el-input v-model="evt.event_title" placeholder="事件标题" size="small" style="flex: 1;" />
          <el-date-picker
            v-model="evt.dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始"
            end-placeholder="结束"
            size="small"
            style="width: 260px;"
            value-format="YYYY-MM-DD"
          />
          <el-select v-model="evt.risk_level" size="small" style="width: 100px;">
            <el-option label="高风险" value="high" />
            <el-option label="中风险" value="medium" />
            <el-option label="低风险" value="low" />
          </el-select>
          <el-button type="danger" :icon="Delete" circle size="small" @click="removeEvent(idx)" />
        </div>
        <el-button type="primary" :icon="Plus" size="small" @click="addEvent" style="margin-top: 8px;">
          添加事件
        </el-button>
      </div>
    </section>

    <!-- 操作按钮 -->
    <section class="action-bar">
      <el-button
        type="primary"
        size="large"
        :icon="VideoPlay"
        :loading="running"
        :disabled="running"
        @click="triggerCrawl"
      >
        {{ running ? '爬取进行中...' : '立即执行爬取' }}
      </el-button>
      <el-button size="large" :icon="RefreshRight" @click="loadStatus">
        刷新状态
      </el-button>
    </section>

    <!-- 执行日志 -->
    <section v-if="logs.length" class="log-section">
      <h3>
        <el-icon><Document /></el-icon>
        执行日志
        <el-button size="small" text @click="logs = []">清空</el-button>
      </h3>
      <div class="log-box">
        <div v-for="(line, idx) in logs" :key="idx" class="log-line">{{ line }}</div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Clock, Delete, Document, Plus, RefreshRight, Setting, VideoPlay } from '@element-plus/icons-vue'
import PageHeader from '../components/PageHeader.vue'
import http from '../api/http'

const running = ref(false)
const lastRun = ref('')
const logs = ref([])
const status = reactive({ interval_minutes: 30 })

const config = reactive({
  commentsPerEvent: 500,
  delay: 1.0,
  modes: ['real', 'mock'],
  platforms: ['bilibili', 'weibo', 'toutiao', 'xiaohongshu'],
  events: [
    { keyword: '台风巴威登陆', event_title: '超强台风"巴威"登陆浙江引发多省洪涝灾害', dateRange: ['2026-07-10', '2026-07-20'], risk_level: 'high' },
    { keyword: '幽灵外卖平台被罚', event_title: '市场监管总局对"幽灵外卖"重拳出击', dateRange: ['2026-07-05', '2026-07-15'], risk_level: 'high' },
    { keyword: '摆拍浸猪笼被刑拘', event_title: '湖南汨罗"摆拍浸猪笼"事件策划者被刑拘', dateRange: ['2026-07-04', '2026-07-14'], risk_level: 'medium' },
    { keyword: 'AI看病误诊纠纷', event_title: '大模型AI看病误诊致死纠纷引医疗AI监管升级', dateRange: ['2026-06-25', '2026-07-12'], risk_level: 'high' },
    { keyword: '无人驾驶出租车撞人', event_title: '无人驾驶出租车撞人致死事故引技术伦理大讨论', dateRange: ['2026-06-28', '2026-07-13'], risk_level: 'high' },
  ]
})

function addEvent() {
  config.events.push({
    keyword: '',
    event_title: '',
    dateRange: ['2026-07-01', '2026-07-15'],
    risk_level: 'medium'
  })
}

function removeEvent(idx) {
  if (config.events.length <= 1) {
    ElMessage.warning('至少保留一个事件')
    return
  }
  config.events.splice(idx, 1)
}

async function loadStatus() {
  try {
    const data = await http.get('/crawl/status')
    Object.assign(status, data)
    ElMessage.success('状态已刷新')
  } catch {
    // 忽略
  }
}

async function triggerCrawl() {
  running.value = true
  const startTime = new Date().toLocaleTimeString()
  logs.value.push(`[${startTime}] 发送爬取请求...`)

  try {
    const payload = {
      events: config.events.map(e => ({
        keyword: e.keyword,
        event_title: e.event_title,
        date_start: e.dateRange?.[0] || '',
        date_end: e.dateRange?.[1] || '',
        risk_level: e.risk_level,
      })),
      platforms: config.platforms,
      comments_per_event: config.commentsPerEvent,
      delay: config.delay,
      modes: config.modes,
    }

    logs.value.push(`[${new Date().toLocaleTimeString()}] 参数: ${config.events.length}个事件, ${config.platforms.length}个平台`)

    // 异步触发（立即返回）
    const result = await http.post('/crawl/trigger', payload, { timeout: 10000 })

    if (!result.success) {
      logs.value.push(`[${new Date().toLocaleTimeString()}] ⚠️ ${result.message}`)
      ElMessage.warning(result.message)
      running.value = false
      return
    }

    logs.value.push(`[${new Date().toLocaleTimeString()}] 爬取任务已提交，后台执行中...`)

    // 轮询等待完成（最多等 15 分钟）
    const maxPolls = 180  // 180 * 5s = 15 分钟
    let pollCount = 0
    const pollInterval = setInterval(async () => {
      pollCount++
      try {
        const status = await http.get('/crawl/status', { timeout: 5000 })
        if (status.running) {
          if (pollCount % 6 === 1) {  // 每 30 秒提示一次
            logs.value.push(`[${new Date().toLocaleTimeString()}] 仍在运行中...`)
          }
        } else {
          clearInterval(pollInterval)
          running.value = false
          lastRun.value = status.last_time || new Date().toLocaleString()
          if (status.last_result === 'success') {
            logs.value.push(`[${new Date().toLocaleTimeString()}] ✅ 爬取完成`)
            ElMessage.success('爬取完成，数据已更新')
          } else {
            logs.value.push(`[${new Date().toLocaleTimeString()}] ❌ 爬取失败`)
            ElMessage.error('爬取失败，请查看后端日志')
          }
        }
      } catch {
        // 轮询失败，继续尝试
      }

      if (pollCount >= maxPolls) {
        clearInterval(pollInterval)
        running.value = false
        logs.value.push(`[${new Date().toLocaleTimeString()}] ⚠️ 超时：已等待 15 分钟，请手动检查后端日志`)
        ElMessage.warning('轮询超时')
      }
    }, 5000)

  } catch (e) {
    logs.value.push(`[${new Date().toLocaleTimeString()}] ❌ 请求失败: ${e.message}`)
    ElMessage.error('请求失败')
    running.value = false
  }
}

onMounted(loadStatus)
</script>

<style scoped>
.status-bar {
  display: flex;
  gap: 16px;
  margin-bottom: 24px;
}
.status-card {
  display: flex;
  align-items: center;
  gap: 10px;
  background: var(--el-fill-color-light);
  border-radius: 8px;
  padding: 14px 20px;
  flex: 1;
}
.status-card strong {
  display: block;
  font-size: 15px;
}
.status-card span {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.config-section {
  background: var(--el-fill-color-lighter);
  border-radius: 8px;
  padding: 20px 24px;
  margin-bottom: 20px;
}
.config-section h3, .config-section h4 {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 0 0 14px 0;
  font-size: 15px;
}
.config-grid {
  display: flex;
  gap: 24px;
  flex-wrap: wrap;
}
.config-item label {
  display: block;
  font-size: 13px;
  color: var(--el-text-color-secondary);
  margin-bottom: 6px;
}
.platform-checks {
  display: flex;
  gap: 20px;
}
.event-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.event-row {
  display: flex;
  gap: 8px;
  align-items: center;
}

.action-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 24px;
}

.log-section {
  background: #1e1e1e;
  border-radius: 8px;
  padding: 16px 20px;
}
.log-section h3 {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #ccc;
  margin: 0 0 10px 0;
  font-size: 14px;
}
.log-box {
  max-height: 360px;
  overflow-y: auto;
  font-family: 'Consolas', 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.7;
  color: #8bc34a;
}
.log-line {
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
