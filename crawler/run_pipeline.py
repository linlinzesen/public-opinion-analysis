"""
舆情数据采集与分析流水线。

支持两种模式：
1. 真实API爬取模式（需配置API Key和环境）
2. 兜底数据生成模式（当API不可用时自动fallback）

默认配置：5个舆情事件 × 4个平台 × 每个平台600条评论 = 12000条评论
"""

import csv
import random
import os
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

import pandas as pd

from crawler import BilibiliCommentCrawler, WeiboCommentCrawler, ToutiaoSearchCrawler, XiaohongshuCrawler
from sentiment import SentimentAnalyzer
from analyzer import CommentAnalyzer
from preprocessor import preprocess_pipeline
from fake_detector import detect_fake_text, summarize_credibility
from propagation_tracer import trace_propagation

# ── 5个近期热点舆情事件（2026年7月） ──────────────────────────────
EVENTS = [
    {
        "keyword": "台风巴威登陆",
        "event_title": "超强台风\"巴威\"登陆浙江引发多省洪涝灾害与谣言治理风波",
        "date_start": "2026-07-10",
        "date_end": "2026-07-20",
        "risk_level": "high",
        "description": "7月11日超强台风\"巴威\"在浙江台州玉环登陆，最大风力17级以上，强降雨波及十余省区市。期间2人因编造涉台风谣言被依法处理。",
    },
    {
        "keyword": "幽灵外卖平台被罚",
        "event_title": "市场监管总局对\"幽灵外卖\"重拳出击，7家平台被罚35.97亿元",
        "date_start": "2026-07-05",
        "date_end": "2026-07-15",
        "risk_level": "high",
        "description": "市场监管总局对7家外卖平台\"幽灵店铺\"问题开出35.97亿元罚单，平台法定代表人同步被罚，引发外卖行业大震动。",
    },
    {
        "keyword": "摆拍浸猪笼被刑拘",
        "event_title": "湖南汨罗\"摆拍浸猪笼\"事件策划者被刑拘，低俗摆拍整治升级",
        "date_start": "2026-07-04",
        "date_end": "2026-07-14",
        "risk_level": "medium",
        "description": "何某纠集8人摆拍\"女子被关铁笼游街\"低俗场景博取流量，策划者被刑事拘留，参与者被行政拘留，释放明确法律信号。",
    },
    {
        "keyword": "鹿晗工作室被踢出超话",
        "event_title": "鹿晗粉丝将工作室\"踢出超话\"引爆内娱粉丝治理争议",
        "date_start": "2026-07-06",
        "date_end": "2026-07-16",
        "risk_level": "medium",
        "description": "因网红持续造谣\"鹿晗疑似出轨\"，工作室仅转发旧声明，激怒死忠粉。大吧公开将工作室移出超话关联，被称为\"内娱新型物种\"。",
    },
    {
        "keyword": "热搜泛娱乐化争议",
        "event_title": "主流媒体集体发声：公共议题应从娱乐八卦手中夺回热搜C位",
        "date_start": "2026-07-05",
        "date_end": "2026-07-15",
        "risk_level": "medium",
        "description": "台风洪涝期间娱乐八卦仍占据热搜大半，浙江日报、杭州网等主流媒体批评平台算法偏向娱乐内容，呼吁公共议题回归。",
    },
]

# 每个平台在每个事件中的评论数配比（4平台 × 600 = 2400/事件）
PLATFORM_CONFIG = {
    "bilibili": 150,       # B站 25%
    "weibo": 150,           # 微博 25%
    "toutiao": 150,         # 今日头条 25%
    "xiaohongshu": 150,     # 小红书 25%
}
COMMENTS_PER_EVENT = 600  # 每个事件总评论数

# 真实爬取参数
REAL_CRAWL_MAX_RESULTS = 10    # 每个关键词搜索的结果数
REAL_CRAWL_MAX_PAGES = 2       # 每个视频/帖子的评论页数
REAL_CRAWL_BILIBILI_RESULTS = 15
REAL_CRAWL_BILIBILI_PAGES = 3


def _try_real_crawl(crawler, keyword: str, platform_name: str, max_results: int, max_pages: int) -> int:
    """尝试真实API爬取，返回爬到的评论数。"""
    try:
        if platform_name == "bilibili":
            crawler.search_videos(keyword, max_results=max_results, max_pages=max_pages)
        elif platform_name == "weibo":
            crawler.search_posts(keyword, max_results=max_results)
        elif platform_name == "toutiao":
            crawler.search_articles(keyword, max_results=max_results)
        return len(crawler.all_comments)
    except Exception as e:
        print(f"  [{platform_name}] 真实爬取失败: {e}")
        return 0


def main():
    random.seed(42)

    # ── 读取前端传入的自定义爬取配置（如果存在）──
    config_path = Path("crawl_config.json")
    custom_config = None
    if config_path.exists():
        try:
            import json as _json
            custom_config = _json.loads(config_path.read_text(encoding="utf-8"))
            print("[配置] 已加载前端自定义爬取配置")
        except Exception as e:
            print(f"[配置] 读取配置失败: {e}")

    # 使用自定义配置或默认配置
    global EVENTS, COMMENTS_PER_EVENT, PLATFORM_CONFIG
    if custom_config:
        custom_events = custom_config.get("events", [])
        if custom_events:
            EVENTS = [
                {
                    "keyword": e.get("keyword", ""),
                    "event_title": e.get("event_title", ""),
                    "date_start": e.get("date_start", ""),
                    "date_end": e.get("date_end", ""),
                    "risk_level": e.get("risk_level", "medium"),
                    "description": e.get("description", ""),
                }
                for e in custom_events
                if e.get("keyword")
            ]
            print(f"[配置] 使用自定义事件列表: {len(EVENTS)} 个事件")

        custom_platforms = custom_config.get("platforms", [])
        if custom_platforms:
            PLATFORM_CONFIG = {p: custom_config.get("comments_per_event", 500) for p in custom_platforms}
            print(f"[配置] 使用自定义平台: {list(PLATFORM_CONFIG.keys())}")

        custom_comments = custom_config.get("comments_per_event")
        if custom_comments and not custom_platforms:
            COMMENTS_PER_EVENT = custom_comments

        custom_delay = custom_config.get("delay")
        if custom_delay is not None:
            print(f"[配置] 使用自定义延迟: {custom_delay}s")

        # 数据模式：支持多选 ['real', 'mock']
        custom_modes = custom_config.get("modes", [])
        if custom_modes:
            use_real = "real" in custom_modes
            use_mock = "mock" in custom_modes
            print(f"[配置] 数据模式: 真实爬取={'是' if use_real else '否'}, 兜底生成={'是' if use_mock else '否'}")
        else:
            use_real, use_mock = True, True

    print("=" * 60)
    print("舆情数据采集与分析流水线")
    print(f"配置: {len(EVENTS)} 个事件 × 4 个平台 × 每平台150条 = 每事件600条")
    print("=" * 60)

    # API配置检查
    print("\n[API配置检查]")
    has_api_key = bool(os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY"))
    print(f"  LLM API Key: {'已配置' if has_api_key else '未配置 (情感分析将使用规则模式)'}")

    # 使用自定义 delay 或默认 0.5s
    _delay = custom_config.get("delay", 0.5) if custom_config else 0.5

    # 初始化爬虫（四平台）
    crawler = BilibiliCommentCrawler(delay=_delay, output_dir="data")
    weibo_crawler = WeiboCommentCrawler(delay=_delay, output_dir="data")
    toutiao_crawler = ToutiaoSearchCrawler(delay=_delay, output_dir="data")
    xhs_crawler = XiaohongshuCrawler(delay=_delay, output_dir="data")

    # 使用预定义的5个事件关键词
    event_keywords = [e["keyword"] for e in EVENTS]
    print(f"  舆情事件关键词: {event_keywords}")

    # ── 阶段2: 数据采集（真实爬取 + 兜底生成） ──
    print("\n[阶段2] 数据采集...")

    total_real = 0
    total_fallback = 0

    for event in EVENTS:
        keyword = event["keyword"]
        print(f"\n--- 事件: {keyword} ---")

        # B站 —— 真实数据主力（API开放，无需登录）
        before = len(crawler.all_comments)
        if use_real:
            _try_real_crawl(crawler, keyword, platform_name="bilibili",
                            max_results=REAL_CRAWL_BILIBILI_RESULTS, max_pages=REAL_CRAWL_BILIBILI_PAGES)
        bilibili_real = len(crawler.all_comments) - before
        bilibili_target = PLATFORM_CONFIG.get("bilibili", 0)
        if use_mock and bilibili_real < bilibili_target:
            need = bilibili_target - bilibili_real
            crawler.generate_fallback_comments(
                keyword, count=need,
                date_start=event["date_start"], date_end=event["date_end"],
            )
            total_fallback += need
        total_real += bilibili_real

        # 微博 —— 需配置 WEIBO_COOKIE 才能稳定爬取
        before = len(weibo_crawler.all_comments)
        if use_real:
            _try_real_crawl(weibo_crawler, keyword, platform_name="weibo",
                            max_results=REAL_CRAWL_MAX_RESULTS, max_pages=REAL_CRAWL_MAX_PAGES)
        weibo_real = len(weibo_crawler.all_comments) - before
        weibo_target = PLATFORM_CONFIG.get("weibo", 0)
        if use_mock and weibo_real < weibo_target:
            need = weibo_target - weibo_real
            weibo_crawler.generate_fallback_comments(
                keyword, count=need,
                date_start=event["date_start"], date_end=event["date_end"],
            )
            total_fallback += need
        total_real += weibo_real

        # 今日头条 —— 反爬较严，大概率走兜底
        before = len(toutiao_crawler.all_comments)
        if use_real:
            _try_real_crawl(toutiao_crawler, keyword, platform_name="toutiao",
                            max_results=REAL_CRAWL_MAX_RESULTS, max_pages=REAL_CRAWL_MAX_PAGES)
        toutiao_real = len(toutiao_crawler.all_comments) - before
        toutiao_target = PLATFORM_CONFIG.get("toutiao", 0)
        if use_mock and toutiao_real < toutiao_target:
            need = toutiao_target - toutiao_real
            toutiao_crawler.generate_fallback_comments(
                keyword, count=need,
                date_start=event["date_start"], date_end=event["date_end"],
            )
            total_fallback += need
        total_real += toutiao_real

        # 小红书 —— API需签名认证，绝大部分走兜底
        before = len(xhs_crawler.all_comments)
        if use_real:
            _try_real_crawl(xhs_crawler, keyword, platform_name="xiaohongshu",
                            max_results=REAL_CRAWL_MAX_RESULTS, max_pages=1)
        xhs_real = len(xhs_crawler.all_comments) - before
        xhs_target = PLATFORM_CONFIG.get("xiaohongshu", 0)
        if use_mock and xhs_real < xhs_target:
            need = xhs_target - xhs_real
            xhs_crawler.generate_fallback_comments(
                keyword, count=need,
                date_start=event["date_start"], date_end=event["date_end"],
            )
            total_fallback += need
        total_real += xhs_real

    # ── 阶段3: 合并 & 预处理 ──
    print("\n[阶段3] 合并评论数据 & 预处理（去噪/去重/标准化）...")
    combined_comments = (
        crawler.all_comments
        + weibo_crawler.all_comments
        + toutiao_crawler.all_comments
        + xhs_crawler.all_comments
    )

    before_preprocess = len(combined_comments)
    combined_comments = preprocess_pipeline(combined_comments)
    after_preprocess = len(combined_comments)
    removed = before_preprocess - after_preprocess
    print(f"  预处理前: {before_preprocess} 条 → 预处理后: {after_preprocess} 条 (移除 {removed} 条噪音/重复)")

    # ── 阶段3.5: 按事件时间窗口过滤，去除过于久远的评论 ──
    from datetime import datetime, timedelta
    event_date_ranges = {}
    for evt in EVENTS:
        start = datetime.strptime(evt["date_start"], "%Y-%m-%d")
        end = datetime.strptime(evt["date_end"], "%Y-%m-%d")
        # 前后各放宽 30 天作为缓冲
        event_date_ranges[evt["keyword"]] = (start - timedelta(days=30), end + timedelta(days=30))

    filtered_comments = []
    out_of_range = 0
    for c in combined_comments:
        kw = c.get("keyword", "")
        if kw in event_date_ranges:
            ctime_str = c.get("ctime_str", "")
            try:
                ctime_dt = datetime.strptime(str(ctime_str)[:10], "%Y-%m-%d")
                start, end = event_date_ranges[kw]
                if start <= ctime_dt <= end:
                    filtered_comments.append(c)
                else:
                    out_of_range += 1
            except (ValueError, IndexError):
                filtered_comments.append(c)  # 时间解析失败，保留
        else:
            filtered_comments.append(c)  # 无 keyword 标记，保留

    if out_of_range > 0:
        print(f"  时间过滤: 移除 {out_of_range} 条超出事件时间范围的评论（窗口：事件前后各30天）")
    combined_comments = filtered_comments
    after_time_filter = len(combined_comments)
    print(f"  时间过滤后: {after_time_filter} 条")

    # 统计平台分布
    platform_counts = {"bilibili": 0, "weibo": 0, "toutiao": 0, "xiaohongshu": 0}
    for c in combined_comments:
        platform_counts[c.get("platform", "unknown")] = platform_counts.get(c.get("platform", "unknown"), 0) + 1
    print(f"  总评论数: {len(combined_comments)}")
    print(f"  B站: {platform_counts.get('bilibili', 0)} | 微博: {platform_counts.get('weibo', 0)} | 今日头条: {platform_counts.get('toutiao', 0)} | 小红书: {platform_counts.get('xiaohongshu', 0)}")
    print(f"  真实爬取: {total_real} | 兜底生成: {total_fallback}")

    # 保存原始数据
    raw_path = Path("data") / "raw_comments.csv"
    if combined_comments:
        keys = BilibiliCommentCrawler._get_output_columns(combined_comments)
        with raw_path.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(combined_comments)
        print(f"  原始评论已保存到: {raw_path}")
    else:
        print("  警告: 没有采集到任何评论数据!")
        raw_path.write_text(
            "platform,source_id,source_title,content,like_count,ctime,ctime_str,member_level,reply_count,page,user_name,comment_id\n",
            encoding="utf-8-sig",
        )

    # ── 阶段4: 情感分析 ──
    print("\n[阶段4] 情感分析...")
    df = pd.read_csv(raw_path, encoding="utf-8-sig")
    print(f"  加载 {len(df)} 条评论进行情感分析")

    analyzer = CommentAnalyzer()
    sentiment = SentimentAnalyzer()

    labeled = sentiment.analyze_dataframe(df)
    labeled.to_csv(Path("data") / "labeled_comments.csv", index=False, encoding="utf-8-sig")
    print(f"  标注完成，已保存到 labeled_comments.csv")

    # ── 阶段5: 统计分析与事件聚合 ──
    print("\n[阶段5] 统计分析与事件聚合...")

    labeled = analyzer.calculate_heat_index(labeled)
    stats = analyzer.basic_stats(labeled)
    trend = analyzer.daily_trend(labeled)
    daily_stats = analyzer.daily_stats(labeled)
    keywords_result = analyzer.extract_keywords(labeled)
    events_result = analyzer.aggregate_events(labeled)
    base_event_count = len(events_result)

    # ── 增强：ML 事件发现 ──
    print("\n[ML增强] 利用 KMeans 聚类自动发现舆情事件...")
    ml_events = analyzer.discover_events_ml(labeled, n_clusters=5)
    print(f"  ML 聚类发现 {len(ml_events)} 个事件簇")
    for me in ml_events:
        print(f"    - {me['event_title']}: {me['total_comments']} 条评论")

    # ── 增强：跨关键词相似事件聚合 ──
    enhanced_events = analyzer.aggregate_events_enhanced(labeled)
    print(f"  增强聚合: {base_event_count} → {len(enhanced_events)} 个事件")

    # 为聚合事件补充元数据
    for event in events_result:
        kw = event.get("keyword", "")
        matched = next((e for e in EVENTS if e["keyword"] == kw), None)
        if matched:
            event["event_title"] = matched["event_title"]
            event["risk_level"] = matched["risk_level"]

    sentiment_summary = sentiment.summarize(labeled)

    print(f"  基础统计: {stats}")
    print(f"  情感分布: {sentiment_summary}")
    print(f"  聚合事件数: {len(events_result)}")
    for evt in events_result:
        print(f"    - {evt.get('event_title', evt.get('keyword', ''))}: {evt.get('total_comments', 0)} 条评论")

    # ── 阶段6: 虚假文本检测 ──
    print("\n[阶段6] 虚假文本检测...")
    comments_for_detection = combined_comments[:500]  # 抽样检测，控制耗时
    fake_results = []
    for c in comments_for_detection:
        result = detect_fake_text(str(c.get("content", "")))
        result["comment_id"] = str(c.get("comment_id", c.get("source_id", "")))
        result["text_preview"] = str(c.get("content", ""))[:80]
        fake_results.append(result)
    cred_summary = summarize_credibility(fake_results)
    print(f"  虚假检测完成: 可信={cred_summary['trusted']}, 存疑={cred_summary['suspicious']}, 高风险={cred_summary['high_risk']}, 平均可信度={cred_summary['avg_credibility']}")

    # ── 阶段7: 传播路径追踪 ──
    print("\n[阶段7] 事件传播路径追踪...")
    propagation_results = {}
    for event in EVENTS:
        kw = event["keyword"]
        event_comments = [c for c in combined_comments if c.get("keyword") == kw]
        if event_comments:
            prop_result = trace_propagation(event_comments)
            propagation_results[kw] = prop_result
            print(f"  [{kw}] 初始爆料: {prop_result.get('origin', {}).get('user_name', '未知')}, 放大节点: {len(prop_result.get('amplifiers', []))}个")
        else:
            propagation_results[kw] = {"success": False, "error": "该事件无评论数据"}

    # ── 阶段8: 输出 analysis_result.json ──
    print("\n[阶段8] 输出 analysis_result.json...")

    result = {
        "meta": {
            "total_events": len(EVENTS),
            "total_comments": len(combined_comments),
            "platforms": ["bilibili", "weibo", "toutiao", "xiaohongshu"],
            "comments_per_event": COMMENTS_PER_EVENT,
            "generated_at": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
            "data_source": {
                "real_crawled": total_real,
                "fallback_generated": total_fallback,
            },
        },
        "events_config": EVENTS,
        "basic_stats": stats,
        "daily_trend": trend.to_dict("records") if not trend.empty else [],
        "daily_stats": daily_stats.to_dict("records") if not daily_stats.empty else [],
        "keywords": keywords_result,
        "sentiment_summary": sentiment_summary,
        "heat_index_summary": {
            "avg_heat_index": round(float(labeled["heat_index"].mean()), 2) if "heat_index" in labeled.columns else 0.0,
            "max_heat_index": round(float(labeled["heat_index"].max()), 2) if "heat_index" in labeled.columns else 0.0,
        },
        "platform_distribution": platform_counts,
        "events": events_result,
        "ml_discovered_events": ml_events,
        "enhanced_events": enhanced_events,
        "credibility": {
            "summary": cred_summary,
            "samples": fake_results[:20],  # 仅保留前20条作为样本
        },
        "propagation": propagation_results,
    }

    output_path = Path("data") / "analysis_result.json"
    analyzer.save_json(result, str(output_path))
    print(f"  分析结果已保存到: {output_path}")

    print("\n" + "=" * 60)
    print("流水线执行完成!")
    print(f"  总评论: {len(combined_comments)} 条")
    print(f"  事件数: {len(events_result)} 个")
    print(f"  平台覆盖: B站/微博/今日头条/小红书")
    print(f"  虚假检测: 已检测 {len(fake_results)} 条, 高风险 {cred_summary['high_risk']} 条")
    print(f"  传播追踪: 已追踪 {len(propagation_results)} 个事件")
    print("=" * 60)


if __name__ == "__main__":
    main()
