import http from './http'
import {
  getMockEventDetail,
  mockEvents,
  mockPlatforms,
  mockSentiment,
  mockStats,
  mockTrend,
  mockWords
} from './mock'

const mockEnabled = () => import.meta.env.VITE_ENABLE_MOCK === 'true'

export async function getOverviewStatsApi() {
  if (mockEnabled()) return mockStats
  return http.get('/overview/stats')
}

export async function getEventsApi(params = {}) {
  if (mockEnabled()) {
    const keyword = params.keyword?.trim()
    let records = [...mockEvents]
    if (keyword) {
      records = records.filter((event) => {
        return event.title.includes(keyword) || event.summary.includes(keyword) || event.keywords.some((word) => word.includes(keyword))
      })
    }
    if (params.riskLevel) {
      records = records.filter((event) => event.riskLevel === params.riskLevel)
    }
    if (params.sortBy === 'heat') {
      records.sort((a, b) => b.heat - a.heat)
    } else {
      records.sort((a, b) => new Date(a.occurTime) - new Date(b.occurTime))
    }
    return {
      records,
      total: records.length
    }
  }
  const result = await http.get('/events', { params })
  return Array.isArray(result) ? { records: result, total: result.length } : result
}

export async function getEventDetailApi(id) {
  if (mockEnabled()) return getMockEventDetail(id)
  return http.get(`/events/${id}`)
}

export async function getEventTrendApi(id) {
  if (mockEnabled()) return mockTrend
  return http.get(`/events/${id}/trend`)
}

export async function getEventSentimentApi(id) {
  if (mockEnabled()) return mockSentiment
  return http.get(`/events/${id}/sentiment`)
}

export async function getEventPlatformApi(id) {
  if (mockEnabled()) return mockPlatforms
  return http.get(`/events/${id}/platforms`)
}

export async function getEventWordCloudApi(id) {
  if (mockEnabled()) return mockWords
  return http.get(`/events/${id}/word-cloud`)
}

export async function generateReportApi(id) {
  if (mockEnabled()) {
    const event = getMockEventDetail(id)
    return {
      title: `${event.title} 舆情分析报告`,
      conclusion: '事件处于持续传播阶段，负面情绪占比较高，应优先回应核心诉求并同步权威处置进展。',
      suggestions: ['发布统一口径说明', '持续监测高传播节点', '对高频问题建立回应清单']
    }
  }
  return http.post(`/events/${id}/report`)
}

export async function getEventPropagationApi(id) {
  if (mockEnabled()) {
    return {
      success: true,
      origin: { user_name: '匿名用户', platform: '微博', content_preview: '首次爆料内容...', time: '2026-06-15 10:00:00' },
      amplifiers: [
        { user_name: '人民日报', platform: '微博', type: '官方媒体', time: '2026-06-16 08:00:00', like_count: 8500, reply_count: 1200 },
        { user_name: '知名博主', platform: 'B站', type: '大V/高影响力用户', time: '2026-06-15 14:00:00', like_count: 3200, reply_count: 450 }
      ],
      timeline: [
        { stage: '首次曝光', time: '2026-06-15 10:00:00', actor: '匿名用户' },
        { stage: '大V/高影响力用户介入', time: '2026-06-15 14:00:00', actor: '知名博主' },
        { stage: '官方媒体介入', time: '2026-06-16 08:00:00', actor: '人民日报' }
      ],
      summary: { total_platforms: 3, total_amplifiers: 2, has_media_intervention: true, propagation_depth: 3 }
    }
  }
  return http.get(`/events/${id}/propagation`)
}

export async function checkCredibilityApi(id, texts) {
  if (mockEnabled()) {
    return {
      success: true,
      summary: { total: 1, trusted: 1, suspicious: 0, high_risk: 0, avg_credibility: 78, trusted_ratio: 100, high_risk_ratio: 0 },
      results: [{ credibility: 78, verdict: '可信', risk_factors: [], method: 'rule', text_preview: (texts || [''])[0]?.slice(0, 100) || '' }]
    }
  }
  return http.post(`/events/${id}/credibility`, { texts: texts || [] })
}

export async function getSimilarEventsApi(id) {
  if (mockEnabled()) {
    return { success: true, event_id: id, similar_events: [] }
  }
  return http.get(`/events/${id}/similar`)
}
