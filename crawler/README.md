# 作业 C 端：爬虫与数据分析

> 网络舆情事件智能分析系统 — 数据采集与离线分析端

## 概述

本模块负责舆情数据的**采集 → 清洗 → 情绪标注 → 热度计算 → 按日汇总 → 事件聚合**全链路。
支持 Bilibili、微博、今日头条三个平台，可选用 DeepSeek / OpenAI 兼容接口增强分析效果，也可纯规则式运行。

---

## 数据流

```
热搜榜（B站/微博/头条）
       │
       ▼
  fetch_hotsearch_titles()        ← crawler.py（热榜抓取 + 关键词提取）
       │
       ▼
  extract_event_keywords()        ← LLM 提取 / 规则式回退
       │
       ▼
  search_videos / search_posts / search_articles   ← 三个平台并行搜索
       │
       ▼
  raw_comments.csv                ← 原始评论数据（中间产物）
       │
       ▼
  SentimentAnalyzer.analyze_dataframe()  ← sentiment.py（情绪标注）
       │
       ▼
  labeled_comments.csv            ← 带情绪标签的评论（中间产物）
       │
       ▼
  CommentAnalyzer                 ← analyzer.py
  ├─ calculate_heat_index()       → 逐条计算热度指数
  ├─ daily_stats()                → 按日汇总（评论数/情绪/热度）
  ├─ extract_keywords()           → NLP 分词 + TF-IDF 关键词
  └─ aggregate_events()           → 按关键词聚合成舆情事件
       │
       ▼
  analysis_result.json            ← 最终汇总 JSON
```

---

## 目录结构

```
作业_C_爬虫与数据分析/
├── .env.example          # API 配置模板（复制为 .env 后填写）
├── .venv/                # Python 虚拟环境
├── README.md             # 本文件
├── run_pipeline.py       # ★ 一键启动入口
├── crawler.py            # 数据采集模块
├── sentiment.py          # 情绪分析模块
├── analyzer.py           # NLP + 统计 + 热度 + 事件聚合
├── tests/
│   ├── test_hotsearch.py         # 热榜回退 / LLM JSON 解析 / .env 加载测试
│   └── test_analysis_features.py # NLP 分词 / 热度指数 / 按日统计测试
└── data/                 # 输出目录（自动生成）
    ├── raw_comments.csv
    ├── labeled_comments.csv
    ├── analysis_result.json
    └── hot_titles_cache.json
```

---

## 快速开始

```bash
# 1. 进入目录
cd 作业_C_爬虫与数据分析

# 2. 激活虚拟环境
.\.venv\Scripts\Activate.ps1

# 3.（可选但推荐）配置 DeepSeek API
#    复制 .env.example → .env，填入你的 key

# 4. 一键运行
.\.venv\Scripts\python.exe run_pipeline.py
```

> 未配置 API Key 时，情绪分析和关键词提取会自动降级为规则式逻辑，不影响流程完整性。

---

## 模块接口速查

### crawler.py — 数据采集

| 类 | 关键方法 | 输入 | 输出 |
|---|---|---|---|
| BilibiliCommentCrawler | search_videos(keyword, max_results) | keyword: str | 追加到 self.all_comments: List[dict] |
| | crawl_video(bvid, max_pages) | bvid: str | List[dict] |
| WeiboCommentCrawler | search_posts(keyword, max_results) | keyword: str | 追加到 self.all_comments |
| | crawl_post(post_id, max_pages) | post_id: str | List[dict] |
| | fetch_hotsearch_titles(max_items) | max_items: int | List[str]（热榜标题） |
| | extract_event_keywords(hot_titles, max_keywords) | 热榜标题列表 | List[str]（事件关键词） |
| | filter_risk_keywords(titles) | 标题列表 | List[str]（高风险关键词） |
| ToutiaoSearchCrawler | search_articles(keyword, max_results) | keyword: str | 追加到 self.all_comments |

每条评论的数据结构（self.all_comments 中的元素）：

| 字段 | 类型 | 说明 |
|---|---|---|
| platform | str | "bilibili" / "weibo" / "toutiao" |
| source_id | str | 视频 BV 号 / 微博帖子 ID / 头条文章 ID |
| source_title | str | 视频或文章标题 |
| content | str | 评论正文 |
| like_count | int | 点赞数 |
| reply_count | int | 回复数 |
| ctime | int | Unix 时间戳 |
| ctime_str | str | 格式化时间 YYYY-MM-DD HH:MM:SS |
| user_name | str | 用户名 |
| keyword | str | 本次搜索关键词 |
| page | int | 抓取页码 |

热榜回退链路：
  实时 API 抓取 → 失败 → 读取 hot_titles_cache.json → 空 → 使用 DEFAULT_HOT_TITLES

LLM 关键词提取回退：
  读取 DEEPSEEK_API_KEY / OPENAI_API_KEY → 未配置 → filter_risk_keywords() 规则匹配

---

### sentiment.py — 情绪分析

| 方法 | 输入 | 输出 |
|---|---|---|
| analyze(text) | text: str | {"sentiment": "positive|neutral|negative", "score": float, ...} |
| analyze_dataframe(df) | df: DataFrame (需有列 content) | DataFrame（新增列 sentiment, score, reason） |
| summarize(df) | 含 sentiment 列的 DataFrame | {"positive": int, "negative": int, "neutral": int} |
| clean_text(text) | text: str | 去 HTML / 去空白后的纯文本 |

情绪标注回退：
  LLM API 可用 → 调用 DeepSeek JSON 标注 → 失败/无 Key → _rule_analyze() 规则匹配

---

### analyzer.py — NLP + 统计 + 热度 + 事件聚合

| 方法 | 输入 | 输出 |
|---|---|---|
| preprocess_text(text) | text: str | List[str]（jieba 分词 + 去停用词） |
| basic_stats(df) | DataFrame | {"total_comments", "avg_like_count", "top_like_comments"} |
| daily_trend(df) | 含 ctime_str 的 DataFrame | DataFrame（列 date, count） |
| daily_stats(df) | 含 ctime_str, sentiment 的 DataFrame | DataFrame（列 date, comment_count, positive, negative, neutral, heat_index） |
| extract_keywords(df, top_k) | DataFrame（含 content） | [{"keyword": str, "score": float}, ...] |
| calculate_heat_index(df) | DataFrame（含 like_count, reply_count, score） | DataFrame（新增列 heat_index） |
| aggregate_events(df) | 含 keyword, sentiment 的 DataFrame | [{keyword, total_comments, positive, negative, neutral, platform_distribution, top_keywords}, ...] |
| save_json(data, path) | dict, 路径 | 写入 JSON 文件 |

热度指数公式：
  heat_index = like_count * 0.6 + reply_count * 0.4 + |score| * 2

---

## 输出文件 Schema

### data/raw_comments.csv
中间产物，列 = crawler 评论数据结构（见上表），编码 UTF-8-BOM。

### data/labeled_comments.csv
在 raw_comments.csv 基础上新增：

| 新增列 | 类型 | 说明 |
|---|---|---|
| cleaned_content | str | 清洗后纯文本 |
| sentiment | str | positive / neutral / negative |
| score | float | 情绪得分（正=正面，负=负面） |
| reason | str | LLM 标注原因（规则式为空） |
| heat_index | float | 热度指数 |

### data/analysis_result.json

{
  "basic_stats": {
    "total_comments": 111,
    "avg_like_count": 107.45,
    "top_like_comments": [{ "content": "...", "like_count": 3345 }]
  },
  "daily_trend": [{ "date": "2026-07-08", "count": 31 }],
  "daily_stats": [{
    "date": "2026-07-08",
    "comment_count": 31,
    "positive": 14, "negative": 10, "neutral": 7,
    "heat_index": 6483.8
  }],
  "keywords": [{ "keyword": "投诉", "score": 12.34 }],
  "sentiment_summary": { "positive": 50, "negative": 30, "neutral": 31 },
  "events": [{
    "keyword": "争议",
    "total_comments": 40,
    "positive": 15, "negative": 10, "neutral": 15,
    "platform_distribution": { "bilibili": 30, "weibo": 10 },
    "top_keywords": [{ "keyword": "...", "score": 1.2 }]
  }],
  "heat_index_summary": { "avg_heat_index": 66.76, "max_heat_index": 2012.0 }
}

### data/hot_titles_cache.json
["热榜标题1", "热榜标题2", ...]

---

## 配置

| 环境变量 | 说明 | 默认值 |
|---|---|---|
| DEEPSEEK_API_KEY | DeepSeek API 密钥 | 无（未配置则规则式） |
| DEEPSEEK_BASE_URL | API 地址 | https://api.deepseek.com/v1 |
| DEEPSEEK_MODEL | 模型名 | deepseek-chat |
| OPENAI_API_KEY | OpenAI 兼容密钥（备选） | 无 |
| OPENAI_BASE_URL | OpenAI 兼容地址（备选） | 无 |
| OPENAI_MODEL | OpenAI 兼容模型（备选） | 无 |

优先级：OPENAI_* 和 DEEPSEEK_* 任一组有值即可。.env 文件中的值会先于系统环境变量加载。

---

## 测试

```bash
# 运行全部测试
.\.venv\Scripts\python.exe -m unittest -q tests.test_hotsearch tests.test_analysis_features

# 仅热榜&回退测试（4 项）
.\.venv\Scripts\python.exe -m unittest -q tests.test_hotsearch

# 仅分析功能测试（3 项）
.\.venv\Scripts\python.exe -m unittest -q tests.test_analysis_features
```

---

## 交接说明

- 接手的同学只需：复制 .env.example → .env，填 key，运行 run_pipeline.py。
- 网络热榜不可用时：自动读取 hot_titles_cache.json → 兜底默认标题，不会中断。
- 未配 API Key 时：情绪分析和关键词提取自动退回规则式，仍能产出完整结果。
- 前端对接：直接用 data/analysis_result.json，Schema 见上文。
- 自定义关键词：修改 run_pipeline.py 中 keywords 的兜底列表即可跳过热榜自动发现。
