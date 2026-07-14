"""事件溯源与传播路径追踪模块。

功能：
1. 识别事件传播中的关键节点（初始爆料账号、首次大V转发、首次官方媒体介入）
2. 构建传播路径图（节点 + 边）
3. 按平台和时间线聚合传播链路

用于满足"事件溯源与关键传播路径"需求。
"""

import json
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


# ── 关键节点识别规则 ──────────────────────────────────────────

# 大 V 特征：高粉丝/高互动量
def _is_verified_account(user_name: str, like_count: int = 0, reply_count: int = 0, member_level: int = 0) -> bool:
    """判断是否为高影响力账号（大V/官媒/认证用户）。"""
    # 官方媒体关键词
    official_patterns = [
        "日报", "新闻", "发布", "官方", "政务", "公安", "法院", "检察",
        "人民网", "新华社", "央视", "中新网", "澎湃", "界面", "新京报",
        "观察者", "环球", "参考消息", "光明", "经济观察", "第一财经",
        "市场监管", "卫健委", "教育局", "政府", "应急管理",
    ]
    for pattern in official_patterns:
        if pattern in str(user_name):
            return True

    # 高互动量视为大V
    if like_count > 5000 or reply_count > 1000:
        return True

    # 高等级B站用户
    if member_level >= 5:
        return True

    return False


def _is_media_account(user_name: str) -> bool:
    """判断是否为官方媒体账号。"""
    media_keywords = [
        "新闻", "日报", "发布", "官方", "政务", "公安", "法院", "检察",
        "人民网", "新华社", "央视", "中新网", "澎湃", "界面", "新京报",
        "观察者", "环球", "参考消息", "光明", "经济观察", "第一财经",
        "市场监管", "政府", "应急管理",
    ]
    name = str(user_name)
    return any(kw in name for kw in media_keywords)


# ── 传播路径构建 ──────────────────────────────────────────────

def _parse_ctime(ctime_value: Any) -> Optional[datetime]:
    """解析时间字段。"""
    if isinstance(ctime_value, (int, float)):
        try:
            return datetime.fromtimestamp(ctime_value)
        except (ValueError, OSError):
            pass
    if isinstance(ctime_value, str):
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(ctime_value.strip(), fmt)
            except ValueError:
                continue
    return None


def trace_propagation(
    comments: List[Dict[str, Any]],
    platform_key: str = "platform",
    user_key: str = "user_name",
    time_key: str = "ctime_str",
    like_key: str = "like_count",
    reply_key: str = "reply_count",
    content_key: str = "content",
    level_key: str = "member_level",
) -> Dict[str, Any]:
    """追踪事件传播路径，识别关键节点。

    返回:
        - origin: 初始爆料信息
        - amplifiers: 关键放大节点（大V/官媒转发）
        - path: 按平台分组的传播路径
        - timeline: 关键时间节点
        - graph: 传播图数据（节点+边，可供前端渲染）
    """
    if not comments:
        return {
            "success": False,
            "error": "无评论数据用于分析传播路径",
            "origin": None,
            "amplifiers": [],
            "path": {},
            "timeline": [],
            "graph": {"nodes": [], "edges": []},
        }

    # 按时间排序
    sorted_comments = sorted(comments, key=lambda c: _parse_ctime(c.get(time_key)) or datetime.max)

    # ── 寻找初始爆料 ──
    origin = None
    for comment in sorted_comments:
        if str(comment.get(content_key, "")).strip():
            origin = {
                "user_name": comment.get(user_key, "未知用户"),
                "platform": comment.get(platform_key, "未知平台"),
                "content_preview": str(comment.get(content_key, ""))[:200],
                "time": str(comment.get(time_key, "")),
                "source_id": str(comment.get("source_id", "")),
                "comment_id": str(comment.get("comment_id", "")),
                "like_count": comment.get(like_key, 0),
            }
            break

    if not origin:
        origin = {"user_name": "未识别", "platform": "未知", "content_preview": "无数据", "time": ""}

    # ── 寻找关键放大节点 ──
    amplifiers: List[Dict[str, Any]] = []
    seen_users: set = set()
    for comment in sorted_comments:
        user = str(comment.get(user_key, ""))
        if not user or user in seen_users:
            continue
        likes = int(comment.get(like_key, 0) or 0)
        replies = int(comment.get(reply_key, 0) or 0)
        level = int(comment.get(level_key, 0) or 0)

        if _is_verified_account(user, likes, replies, level):
            seen_users.add(user)
            node_type = "官方媒体" if _is_media_account(user) else "大V/高影响力用户"
            amplifiers.append({
                "user_name": user,
                "platform": comment.get(platform_key, "未知平台"),
                "type": node_type,
                "time": str(comment.get(time_key, "")),
                "like_count": likes,
                "reply_count": replies,
                "content_preview": str(comment.get(content_key, ""))[:150],
            })

            if len(amplifiers) >= 10:
                break

    # ── 按平台统计传播路径 ──
    platform_timeline: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for comment in sorted_comments:
        platform = comment.get(platform_key, "unknown")
        platform_timeline[platform].append({
            "user_name": comment.get(user_key, ""),
            "time": str(comment.get(time_key, "")),
            "like_count": comment.get(like_key, 0),
            "reply_count": comment.get(reply_key, 0),
            "content_preview": str(comment.get(content_key, ""))[:100],
        })

    path = {}
    for platform, items in platform_timeline.items():
        path[platform] = {
            "total_posts": len(items),
            "first_post_time": items[0]["time"] if items else "",
            "top_users": sorted(items, key=lambda x: x.get("like_count", 0), reverse=True)[:5],
        }

    # ── 关键时间节点 ──
    timeline: List[Dict[str, str]] = []
    if origin and origin.get("time"):
        timeline.append({"stage": "首次曝光", "time": origin["time"], "actor": origin.get("user_name", "")})

    for amp in amplifiers[:5]:
        timeline.append({
            "stage": f"{amp.get('type', '关键转发')}介入",
            "time": amp.get("time", ""),
            "actor": amp.get("user_name", ""),
        })

    # ── 构建传播图（节点 + 边） ──
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []
    node_ids: set = set()

    # 添加起源节点
    if origin.get("user_name"):
        origin_id = f"origin_{origin['user_name']}"
        nodes.append({
            "id": origin_id,
            "name": origin["user_name"],
            "type": "origin",
            "platform": origin.get("platform", ""),
            "symbolSize": 40,
        })
        node_ids.add(origin_id)

    # 添加放大节点
    for i, amp in enumerate(amplifiers):
        amp_id = f"amp_{i}_{amp['user_name']}"
        if amp_id not in node_ids:
            nodes.append({
                "id": amp_id,
                "name": amp["user_name"],
                "type": "amplifier",
                "platform": amp.get("platform", ""),
                "symbolSize": 30,
                "subtype": amp.get("type", ""),
            })
            node_ids.add(amp_id)

        # 连接到起源
        if origin.get("user_name"):
            origin_id = f"origin_{origin['user_name']}"
            edges.append({
                "source": origin_id,
                "target": amp_id,
                "label": f"{amp.get('platform', '')}转发",
            })

    graph = {"nodes": nodes, "edges": edges}

    return {
        "success": True,
        "origin": origin,
        "amplifiers": amplifiers,
        "path": path,
        "timeline": timeline,
        "graph": graph,
        "summary": {
            "total_platforms": len(path),
            "total_amplifiers": len(amplifiers),
            "has_media_intervention": any(_is_media_account(a.get("user_name", "")) for a in amplifiers),
            "propagation_depth": len(timeline),
        },
    }
