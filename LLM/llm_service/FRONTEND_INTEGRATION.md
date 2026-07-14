# 大模型与高级功能：前端联调文档

适用技术栈：Vue 3、TypeScript/JavaScript、Element Plus、ECharts。

## 1. 基础信息

- 独立调试地址：`http://localhost:5001`
- 集成主后端后：使用主后端地址
- API 前缀：`/api/llm`
- 请求格式：`application/json; charset=utf-8`
- 响应格式：JSON

后端会明确返回 `Content-Type: application/json; charset=utf-8`。浏览器和 Axios
会自动按 UTF-8 解析中文，不需要前端手动转码。

建议在 Vite 环境变量中配置：

```env
VITE_API_BASE_URL=http://localhost:5001
```

## 2. TypeScript 类型

```ts
export interface TrendPoint {
  time: string
  value: number
}

export interface EventData {
  id?: number | string
  title: string
  summary: string
  keywords?: string[]
  sentiment_distribution?: {
    positive?: number
    neutral?: number
    negative?: number
    [key: string]: number | undefined
  }
  trend_data?: TrendPoint[]
  platform_distribution?: Record<string, number>
}

export type LlmMode = 'api' | 'mock' | 'fallback' | 'guard'

export interface AskResponse {
  success: boolean
  answer?: string
  mode?: LlmMode
  model?: string | null
  warning?: string
  error?: string
}

export interface PredictResponse {
  success: boolean
  method?: 'linear_regression'
  trend?: '上升' | '下降' | '平稳'
  change_ratio?: number
  interval_hours?: number
  predictions: TrendPoint[]
  error?: string
}

export interface ReportResponse {
  success: boolean
  report?: string
  format?: 'markdown'
  mode?: Exclude<LlmMode, 'guard'>
  model?: string
  warning?: string
  error?: string
}
```

时间字段应使用 ISO 8601，例如 `2026-07-09T10:00:00+08:00`。情感分布和平台
分布可传百分数（如 55）或 0～1 比例（如 0.55），同一个对象内应保持一致。

## 3. Axios 封装

```ts
// src/api/llm.ts
import axios from 'axios'
import type {
  AskResponse,
  EventData,
  PredictResponse,
  ReportResponse,
  TrendPoint
} from '@/types/llm'

const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  timeout: 45_000,
  headers: { 'Content-Type': 'application/json; charset=utf-8' }
})

export async function askEventQuestion(
  eventData: EventData,
  question: string
): Promise<AskResponse> {
  const { data } = await client.post<AskResponse>('/api/llm/ask', {
    event_data: eventData,
    question
  })
  return data
}

export async function predictEventTrend(
  trendData: TrendPoint[]
): Promise<PredictResponse> {
  const { data } = await client.post<PredictResponse>('/api/llm/predict', {
    trend_data: trendData
  })
  return data
}

export async function generateEventReport(
  eventData: EventData
): Promise<ReportResponse> {
  const { data } = await client.post<ReportResponse>('/api/llm/report', {
    event_data: eventData
  })
  return data
}
```

如果前端使用 Vite 代理，可把 `baseURL` 设为 `/`，并在 `vite.config.ts` 配置：

```ts
server: {
  proxy: {
    '/api': {
      target: 'http://localhost:5001',
      changeOrigin: true
    }
  }
}
```

## 4. 智能问答接口

### `POST /api/llm/ask`

请求：

```json
{
  "event_data": {
    "title": "某品牌产品质量争议",
    "summary": "消费者发布质量问题视频，品牌方启动调查。",
    "keywords": ["产品质量", "品牌回应"],
    "sentiment_distribution": {"positive": 15, "neutral": 30, "negative": 55},
    "platform_distribution": {"微博": 55, "抖音": 30}
  },
  "question": "该事件当前主要风险是什么？"
}
```

成功响应：

```json
{
  "success": true,
  "answer": "当前可从热度变化和负面情感占比研判该事件风险……",
  "mode": "mock",
  "model": "mock-rule-based"
}
```

前端处理建议：

- 发送前对 `question.trim()` 判空；
- 请求期间使用 `ElButton` 的 `loading`；
- 展示 `answer`，不要把 `model` 当作业务内容；
- `mode=guard` 表示问题与事件无关，但仍是正常的 HTTP 200；
- `mode=fallback` 表示模型调用失败但已有可展示的降级答案；
- `warning` 仅用于开发调试，不建议作为红色错误弹窗打断用户。

## 5. 趋势预测接口

### `POST /api/llm/predict`

请求：

```json
{
  "trend_data": [
    {"time": "2026-07-09T08:00:00+08:00", "value": 120},
    {"time": "2026-07-09T09:00:00+08:00", "value": 145},
    {"time": "2026-07-09T10:00:00+08:00", "value": 180}
  ]
}
```

成功响应：

```json
{
  "success": true,
  "method": "linear_regression",
  "trend": "上升",
  "change_ratio": 3.9907,
  "interval_hours": 1.0,
  "predictions": [
    {"time": "2026-07-09T11:00:00+08:00", "value": 208.33}
  ]
}
```

小时数据通常返回 24 个预测点。`change_ratio` 是比例而非百分数字符串：
`0.15` 表示预测期末相对当前热度上升约 15%。

ECharts 建议把历史数据和预测数据画成两条线：

```ts
const option = {
  tooltip: { trigger: 'axis' },
  legend: { data: ['历史热度', '预测热度'] },
  xAxis: { type: 'time' },
  yAxis: { type: 'value', min: 0 },
  series: [
    {
      name: '历史热度',
      type: 'line',
      data: eventData.trend_data?.map(p => [p.time, p.value]) ?? [],
      smooth: true
    },
    {
      name: '预测热度',
      type: 'line',
      data: result.predictions.map(p => [p.time, p.value]),
      lineStyle: { type: 'dashed' },
      itemStyle: { color: '#E6A23C' },
      smooth: true
    }
  ]
}
```

趋势标签建议：上升用 `danger` 或橙红色，下降用 `success`，平稳用 `info`。

## 6. 报告生成接口

### `POST /api/llm/report`

请求体只有 `event_data`：

```json
{
  "event_data": {
    "title": "某品牌产品质量争议",
    "summary": "消费者发布质量问题视频，品牌方启动调查。",
    "keywords": ["产品质量", "品牌回应"],
    "sentiment_distribution": {"positive": 15, "neutral": 30, "negative": 55},
    "trend_data": [
      {"time": "2026-07-09T08:00:00+08:00", "value": 120},
      {"time": "2026-07-09T09:00:00+08:00", "value": 145}
    ],
    "platform_distribution": {"微博": 55, "抖音": 30}
  }
}
```

响应：

```json
{
  "success": true,
  "report": "# 某品牌产品质量争议舆情分析报告\n\n## 一、事件概述\n……",
  "format": "markdown",
  "mode": "mock",
  "model": "mock-template"
}
```

`report` 是 Markdown，建议使用 `markdown-it` 渲染。若使用 `v-html`，必须先使用
DOMPurify 等库进行清洗，不能直接信任模型输出：

```ts
import MarkdownIt from 'markdown-it'
import DOMPurify from 'dompurify'

const md = new MarkdownIt({ html: false, breaks: true })
const safeHtml = computed(() =>
  DOMPurify.sanitize(md.render(report.value ?? ''))
)
```

如果课程项目不想增加依赖，可使用 `<pre class="report-text">{{ report }}</pre>`
保留换行展示。

## 7. 状态码和错误处理

| HTTP 状态 | 含义 | 前端处理 |
|---|---|---|
| 200 | 成功，含 mock/guard/fallback | 正常展示内容 |
| 400 | 请求字段缺失或数据格式错误 | 展示响应中的 `error` |
| 404 | 地址或代理配置错误 | 检查 API baseURL |
| 500 | 未预期服务异常 | 展示统一错误并记录日志 |

Axios 错误处理示例：

```ts
import axios from 'axios'
import { ElMessage } from 'element-plus'

try {
  const result = await generateEventReport(eventData)
  report.value = result.report ?? ''
} catch (error) {
  if (axios.isAxiosError(error)) {
    ElMessage.error(error.response?.data?.error ?? '服务暂时不可用，请稍后重试')
  } else {
    ElMessage.error('发生未知错误')
  }
}
```

## 8. 联调验收清单

- 问答、预测、报告三个请求都使用 snake_case 字段；
- 当前事件详情能完整传入，特别是趋势、情感和平台分布；
- 空问题不发送，趋势数据少于两个点时禁用预测按钮；
- 所有按钮都有 loading，避免用户重复提交；
- 正确展示 HTTP 400 的 `error`；
- `mode=guard` 和 `mode=fallback` 不当作系统崩溃；
- 预测折线使用不同颜色或虚线；
- Markdown 输出经过安全清洗；
- 切换事件后清空上一个事件的问答和报告；
- mock 模式下完成一轮端到端演示，再接真实 API。
