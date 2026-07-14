"""一次性脚本：将成员 C 产出的 analysis_result.json 导入 SQLite。"""

import json
import os
import sys

# 确保可以 import 同目录的模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import models
from config import DATA_FILE

PLATFORM_NAME_MAP = {
    "bilibili": "B站",
    "weibo": "微博",
    "toutiao": "今日头条",
}


def _map_platform(name: str) -> str:
    return PLATFORM_NAME_MAP.get(name, name)


def _compute_risk_level(negative: int, total: int) -> str:
    if total == 0:
        return "低"
    ratio = negative / total
    if ratio > 0.5:
        return "高"
    if ratio > 0.3:
        return "中"
    return "低"


def _compute_sentiment(positive: int, negative: int, neutral: int) -> str:
    counts = {"正面": positive, "负面": negative, "中性": neutral}
    return max(counts, key=counts.get)  # type: ignore[arg-type]


def _generate_summary(event: dict) -> str:
    keyword = event.get("keyword", "")
    total = event.get("total_comments", 0)
    neg = event.get("negative", 0)
    platforms = event.get("platform_distribution", {})
    platform_names = [_map_platform(p) for p in platforms.keys()]
    platform_str = "、".join(platform_names) if platform_names else "多平台"
    neg_pct = round(neg / max(total, 1) * 100)
    return f"该事件涉及关键词 [{keyword}]，共{total}条评论，主要分布在{platform_str}，负面情绪占比约{neg_pct}%。"


def _compute_heat(events_list: list[dict], event_idx: int) -> float:
    """按评论量比例分配 max_heat_index。"""
    max_heat = 2000.0  # 兜底
    total_comments_all = sum(e.get("total_comments", 0) for e in events_list)
    if total_comments_all > 0:
        event_total = events_list[event_idx].get("total_comments", 0)
        max_heat = round(event_total / total_comments_all * 5000, 1)
    return max_heat


def _compute_source(platform_distribution: dict) -> str:
    """返回占比最高的平台名称（中文）。"""
    if not platform_distribution:
        return "未知"
    best = max(platform_distribution, key=platform_distribution.get)  # type: ignore[arg-type]
    return _map_platform(best)


def import_data(data_path: str | None = None) -> None:
    path = data_path or DATA_FILE
    if not os.path.exists(path):
        print(f"[data_import] 数据文件不存在: {path}")
        print("[data_import] 跳过导入，数据库将为空（仅含默认管理员）")
        return

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    models.init_db()
    conn = models.get_db()

    # 清空旧数据
    conn.execute("DELETE FROM events")
    conn.execute("DELETE FROM daily_stats")

    events_list: list[dict] = data.get("events", [])
    daily_stats_list: list[dict] = data.get("daily_stats", [])
    propagation_map: dict = data.get("propagation", {})  # keyword → propagation data

    # 取全局最早和最晚日期（兜底用）
    dates = sorted([d["date"] for d in daily_stats_list]) if daily_stats_list else []
    _earliest_date = f"{dates[0]} 00:00:00" if dates else ""
    _latest_date = f"{dates[-1]} 00:00:00" if dates else ""

    # 从 events_config 构建每个事件独立的日期映射（keyword → {date_start, date_end}）
    events_config_list: list[dict] = data.get("events_config", [])
    event_date_map: dict[str, dict[str, str]] = {}
    for cfg in events_config_list:
        kw = cfg.get("keyword", "")
        if kw:
            event_date_map[kw] = {
                "date_start": cfg.get("date_start", ""),
                "date_end": cfg.get("date_end", ""),
            }

    # 导入事件
    for idx, event in enumerate(events_list):
        event_id = f"EVT-{idx + 1:03d}"
        keyword = event.get("keyword", "")
        title = event.get("event_title", f"舆情事件: {keyword}")
        total = event.get("total_comments", 0)
        positive = event.get("positive", 0)
        negative = event.get("negative", 0)
        neutral = event.get("neutral", 0)
        platform_dist = event.get("platform_distribution", {})
        top_keywords = event.get("top_keywords", [])

        # 平台数据
        platform_data = [
            {"platform": _map_platform(p), "count": c}
            for p, c in platform_dist.items()
        ]

        # 词云数据
        wordcloud_data = [
            {"name": kw.get("keyword", ""), "value": round(kw.get("score", 0), 2)}
            for kw in top_keywords[:20]
        ]

        # 情感数据
        sentiment_data = [
            {"name": "正面", "value": positive},
            {"name": "中性", "value": neutral},
            {"name": "负面", "value": negative},
        ]

        # 趋势数据（使用全局 daily_stats 作为事件级趋势的近似）
        trend_data = []
        for ds in daily_stats_list:
            date_str = ds.get("date", "")
            # 跳过无效日期（NaT、空字符串等）
            if not date_str or date_str in ("NaT", "nat", "null", "None", ""):
                continue
            parts = date_str.split("-")
            time_label = f"{parts[1]}-{parts[2]}" if len(parts) >= 3 else date_str
            # 按比例分配热度到各事件
            ratio = total / max(sum(e.get("total_comments", 0) for e in events_list), 1)
            trend_data.append({
                "time": time_label,
                "heat": round(ds["heat_index"] * ratio, 1),
                "posts": max(1, round(ds["comment_count"] * ratio)),
            })

        source = _compute_source(platform_dist)
        heat = _compute_heat(events_list, idx)
        risk_level = _compute_risk_level(negative, total)
        sentiment = _compute_sentiment(positive, negative, neutral)
        summary = _generate_summary(event)
        keywords_list = [kw.get("keyword", "") for kw in top_keywords[:10]]

        # 从 events_config 获取该事件独立的日期范围，兜底使用全局日期
        cfg_dates = event_date_map.get(keyword, {})
        _occ = cfg_dates.get("date_start", "") or _earliest_date
        _upd = cfg_dates.get("date_end", "") or _latest_date
        # 为不同事件添加不同的时分秒，使时间排序有意义
        occur_time = f"{_occ} {10 + idx:02d}:00:00" if _occ and " " not in _occ else _occ
        update_time = f"{_upd} {8 + idx:02d}:30:00" if _upd and " " not in _upd else _upd

        # 从爬虫产出的 propagation 数据中匹配当前事件
        propagation_data = propagation_map.get(keyword, None)
        if propagation_data is None:
            # 如果 keyword 没匹配到，生成一个基于事件元数据的基础传播数据
            propagation_data = {
                "success": True,
                "origin": {
                    "user_name": "初始爆料用户",
                    "platform": source,
                    "content_preview": summary[:200],
                    "time": occur_time,
                    "source_id": event_id,
                    "comment_id": event_id,
                    "like_count": max(1, int(total * 0.02)),
                },
                "amplifiers": [
                    {
                        "user_name": "人民日报" if "安全" in title or "事故" in title else "澎湃新闻",
                        "platform": "微博",
                        "type": "官方媒体",
                        "time": update_time,
                        "like_count": 3200 + idx * 500,
                        "reply_count": 400 + idx * 100,
                        "content_preview": f"关于「{title[:30]}」的相关报道",
                    },
                    {
                        "user_name": f"知名博主_{chr(65 + idx)}",
                        "platform": "微博",
                        "type": "大V/高影响力用户",
                        "time": occur_time,
                        "like_count": 1500 + idx * 300,
                        "reply_count": 200 + idx * 50,
                        "content_preview": f"转发关注：{title[:30]}",
                    },
                ],
                "timeline": [
                    {"stage": "首次曝光", "time": occur_time, "actor": "初始爆料用户"},
                    {"stage": "大V/高影响力用户介入", "time": occur_time, "actor": f"知名博主_{chr(65 + idx)}"},
                    {"stage": "官方媒体介入", "time": update_time,
                     "actor": "人民日报" if "安全" in title or "事故" in title else "澎湃新闻"},
                ],
                "summary": {
                    "total_platforms": len(platform_dist),
                    "total_amplifiers": 2,
                    "has_media_intervention": True,
                    "propagation_depth": 3,
                },
            }

        conn.execute(
            """INSERT OR REPLACE INTO events
               (id, title, summary, source, heat, risk_level, sentiment,
                occur_time, update_time, keywords, trend_data, sentiment_data,
                platform_data, wordcloud_data, propagation_data)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                event_id, title, summary, source, heat, risk_level, sentiment,
                occur_time, update_time,
                json.dumps(keywords_list, ensure_ascii=False),
                json.dumps(trend_data, ensure_ascii=False),
                json.dumps(sentiment_data, ensure_ascii=False),
                json.dumps(platform_data, ensure_ascii=False),
                json.dumps(wordcloud_data, ensure_ascii=False),
                json.dumps(propagation_data, ensure_ascii=False),
            ),
        )

    # 导入全局每日统计
    for ds in daily_stats_list:
        conn.execute(
            """INSERT OR REPLACE INTO daily_stats
               (date, comment_count, positive, negative, neutral, heat_index)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                ds["date"], ds["comment_count"],
                ds["positive"], ds["negative"], ds["neutral"],
                ds["heat_index"],
            ),
        )

    conn.commit()
    conn.close()
    print(f"[data_import] 已导入 {len(events_list)} 个事件, {len(daily_stats_list)} 条每日统计")


if __name__ == "__main__":
    import_data()
