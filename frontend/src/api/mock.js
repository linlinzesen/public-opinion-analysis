export const mockStats = {
  eventTotal: 128,
  hotEventTotal: 18,
  highRiskTotal: 7,
  platformTotal: 9,
  todayIncrement: 26,
  avgEmotionScore: 68
}

export const mockEvents = [
  {
    id: 'EVT-2026070701',
    title: '某品牌售后争议持续发酵',
    summary: '多平台用户集中讨论售后响应、退款周期与客服态度，相关话题热度在短时间内快速攀升。',
    source: '微博',
    heat: 9632,
    riskLevel: '高',
    sentiment: '负面',
    occurTime: '2026-07-07 09:40',
    updateTime: '2026-07-07 13:20',
    keywords: ['售后', '退款', '客服', '消费者权益']
  },
  {
    id: 'EVT-2026070604',
    title: '城市轨道交通延误引发讨论',
    summary: '早高峰期间线路延误，用户主要关注通勤影响、现场引导和后续补偿说明。',
    source: '新闻客户端',
    heat: 7218,
    riskLevel: '中',
    sentiment: '中性',
    occurTime: '2026-07-06 08:15',
    updateTime: '2026-07-07 10:55',
    keywords: ['地铁', '通勤', '延误', '公告']
  },
  {
    id: 'EVT-2026070502',
    title: '校园食品安全话题升温',
    summary: '家长和学生围绕食堂管理、抽检结果公开、责任追踪进行集中表达。',
    source: '短视频平台',
    heat: 8845,
    riskLevel: '高',
    sentiment: '负面',
    occurTime: '2026-07-05 18:30',
    updateTime: '2026-07-07 09:10',
    keywords: ['校园', '食品安全', '抽检', '家长']
  },
  {
    id: 'EVT-2026070408',
    title: '文旅活动带动本地消费',
    summary: '暑期活动吸引游客关注，讨论集中在交通组织、住宿价格和活动体验。',
    source: '小红书',
    heat: 5320,
    riskLevel: '低',
    sentiment: '正面',
    occurTime: '2026-07-04 20:00',
    updateTime: '2026-07-06 22:12',
    keywords: ['文旅', '暑期', '消费', '体验']
  },
  {
    id: 'EVT-2026070309',
    title: '新产品发布会口碑分化',
    summary: '用户对价格、性能和外观评价差异明显，科技媒体评测带来二次传播。',
    source: '知乎',
    heat: 6460,
    riskLevel: '中',
    sentiment: '中性',
    occurTime: '2026-07-03 21:30',
    updateTime: '2026-07-06 11:26',
    keywords: ['发布会', '价格', '评测', '性能']
  }
]

export const mockTrend = [
  { time: '07-01', heat: 180, posts: 620 },
  { time: '07-02', heat: 260, posts: 840 },
  { time: '07-03', heat: 480, posts: 1300 },
  { time: '07-04', heat: 720, posts: 1880 },
  { time: '07-05', heat: 1160, posts: 2940 },
  { time: '07-06', heat: 1520, posts: 3760 },
  { time: '07-07', heat: 1340, posts: 3310 }
]

export const mockSentiment = [
  { name: '正面', value: 24 },
  { name: '中性', value: 36 },
  { name: '负面', value: 40 }
]

export const mockPlatforms = [
  { platform: '微博', count: 3280 },
  { platform: '短视频', count: 2860 },
  { platform: '新闻', count: 1960 },
  { platform: '论坛', count: 1180 },
  { platform: '知乎', count: 960 },
  { platform: '小红书', count: 730 }
]

export const mockWords = [
  { name: '退款', value: 92 },
  { name: '回应', value: 86 },
  { name: '客服', value: 81 },
  { name: '热搜', value: 74 },
  { name: '监管', value: 68 },
  { name: '道歉', value: 62 },
  { name: '证据', value: 57 },
  { name: '体验', value: 51 },
  { name: '投诉', value: 47 },
  { name: '品牌', value: 42 },
  { name: '消费者', value: 39 },
  { name: '声明', value: 35 }
]

export const mockPlatformsFollowed = [
  { id: 1, name: '微博热搜', url: 'https://s.weibo.com/top/summary' },
  { id: 2, name: '知乎热榜', url: 'https://www.zhihu.com/hot' },
  { id: 3, name: '百度热搜', url: 'https://top.baidu.com/board' }
]

export const mockKeywordsFollowed = [
  { id: 1, word: '食品安全', level: '高' },
  { id: 2, word: '售后争议', level: '中' },
  { id: 3, word: '城市交通', level: '中' }
]

export function getMockEventDetail(id) {
  return mockEvents.find((event) => event.id === id) || mockEvents[0]
}
