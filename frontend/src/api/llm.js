import axios from 'axios'

const client = axios.create({
  baseURL: import.meta.env.VITE_LLM_API_BASE_URL || '/',
  timeout: 45000,
  headers: {
    'Content-Type': 'application/json; charset=utf-8'
  }
})

function normalizeTrendData(trendData) {
  if (!Array.isArray(trendData)) return []

  const currentYear = new Date().getFullYear()
  // 无效时间标记（pandas NaT 序列化后可能产生的字符串）
  const INVALID_TIMES = new Set(['nat', 'null', 'none', 'nan', 'undefined'])

  return trendData
    .map((item) => {
      const rawTime = item?.time ?? item?.timestamp ?? item?.datetime ?? item?.date
      const rawValue = item?.value ?? item?.heat ?? item?.hotness ?? item?.count

      if (typeof rawTime !== 'string' || !rawTime.trim()) {
        return null
      }

      const trimmed = rawTime.trim()
      // 过滤 pandas NaT / NaN / null 等无效时间标记
      if (INVALID_TIMES.has(trimmed.toLowerCase())) {
        console.warn('[normalizeTrendData] 跳过无效时间:', trimmed)
        return null
      }

      let normalizedTime = trimmed

      if (/^\d{2}-\d{2}$/.test(trimmed)) {
        const [month, day] = trimmed.split('-').map(Number)
        normalizedTime = `${currentYear}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}T00:00:00`
      } else if (/^\d{2}\/\d{2}$/.test(trimmed)) {
        const [month, day] = trimmed.split('/').map(Number)
        normalizedTime = `${currentYear}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}T00:00:00`
      } else if (/^\d{4}-\d{2}-\d{2}$/.test(trimmed)) {
        normalizedTime = `${trimmed}T00:00:00`
      } else if (/^\d{4}\/\d{2}\/\d{2}$/.test(trimmed)) {
        normalizedTime = `${trimmed.replace(/\//g, '-') }T00:00:00`
      } else if (trimmed.includes(' ')) {
        normalizedTime = trimmed.replace(' ', 'T')
      } else {
        // 不认识的格式也跳过，避免 "NaT" 等无效值进入后端
        console.warn('[normalizeTrendData] 无法识别的时间格式:', trimmed)
        return null
      }

      return {
        time: normalizedTime,
        value: Number(rawValue)
      }
    })
    .filter(Boolean)
}

export async function askEventQuestion(eventData, question) {
  const { data } = await client.post('/api/llm/ask', {
    event_data: eventData,
    question
  })
  return data
}

export async function predictEventTrend(trendData) {
  const { data } = await client.post('/api/llm/predict', {
    trend_data: normalizeTrendData(trendData)
  })
  return data
}

export async function generateEventReport(eventData) {
  const { data } = await client.post('/api/llm/report', {
    event_data: eventData
  })
  return data
}
