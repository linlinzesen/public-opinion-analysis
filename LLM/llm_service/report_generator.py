"""结构化 Markdown 舆情分析报告生成。"""

from typing import Any

from .config import get_config
from .llm_client import LLMServiceError, chat_completion
from .prompts import REPORT_SYSTEM_PROMPT
from .trend_predictor import predict_trend
from .utils import event_context, normalize_event_data


def _percent(distribution: Any, names: tuple[str, ...]) -> float:
    if not isinstance(distribution, dict):
        return 0.0
    for name in names:
        if name in distribution:
            try:
                value = float(distribution[name])
                return value * 100 if 0 <= value <= 1 else value
            except (TypeError, ValueError):
                return 0.0
    return 0.0


def _risk_level(event: dict[str, Any], trend: dict[str, Any]) -> tuple[str, str]:
    negative = _percent(event.get("sentiment_distribution"), ("negative", "负面", "neg"))
    direction = trend.get("trend", "未知")
    if negative >= 60 or (negative >= 40 and direction == "上升"):
        return "高", f"负面情感占比约 {negative:.1f}%，预测趋势为{direction}"
    if negative >= 30 or direction == "上升":
        return "中", f"负面情感占比约 {negative:.1f}%，预测趋势为{direction}"
    return "低", f"负面情感占比约 {negative:.1f}%，预测趋势为{direction}"


def _mock_report(event: dict[str, Any]) -> str:
    title = event.get("title") or "未命名事件"
    summary = event.get("summary") or "当前暂无摘要。"
    keywords = event.get("keywords") or []
    sentiment = event.get("sentiment_distribution") or "暂无数据"
    platforms = event.get("platform_distribution") or "暂无数据"
    occur_time = event.get("occurTime") or "暂无数据"
    source = event.get("source") or "暂无数据"
    trend = predict_trend(event.get("trend_data") or [])
    direction = trend.get("trend", "数据不足，暂无法判断")
    level, reason = _risk_level(event, trend)
    keyword_text = "、".join(map(str, keywords)) if isinstance(keywords, list) else str(keywords)

    # 从摘要和关键词中尝试提取人物/机构信息
    people_hint = ""
    if isinstance(keywords, list) and keywords:
        org_keywords = [k for k in keywords if len(str(k)) >= 2 and not str(k).startswith(("回复", "支持", "抵制", "怎么"))]
        if org_keywords:
            people_hint = f"关键词中涉及：{'、'.join(org_keywords[:5])}。"

    return f"""# {title}舆情分析报告

## 一、事件概述

- **发生时间**：{occur_time}
- **首发平台**：{source}
- **事件起因**：{summary}
- **涉及人物/机构**：{people_hint or "当前数据中暂无明确人物/机构信息。"}

关键词：{keyword_text or "暂无"}。

## 二、传播趋势分析

当前趋势研判为：**{direction}**。平台分布：{platforms}。

## 三、情感倾向分析

当前情感分布：{sentiment}。应持续关注负面情绪占比及其短时增幅。

## 四、风险等级研判

风险等级：**{level}**。研判依据：{reason}。

## 五、处置建议

1. 持续监测高占比平台与热度异常增长时段。
2. 核验核心信息，及时发布清晰、可追溯的权威说明。
3. 对集中出现的负面观点分类回应，避免情绪进一步扩散。
4. 设置热度和负面占比预警阈值，动态复核风险等级。
"""


def generate_report(event_data: dict) -> dict:
    try:
        event = normalize_event_data(event_data)
    except ValueError as exc:
        return {"success": False, "error": str(exc)}
    if not event.get("title") and not event.get("summary"):
        return {"success": False, "error": "event_data 至少需要 title 或 summary"}

    if get_config().mock_mode:
        return {
            "success": True,
            "report": _mock_report(event).strip(),
            "format": "markdown",
            "mode": "mock",
            "model": "mock-template",
        }
    try:
        result = chat_completion(
            [
                {"role": "system", "content": REPORT_SYSTEM_PROMPT},
                {"role": "user", "content": f"事件数据：\n{event_context(event)}"},
            ],
            temperature=0.3,
        )
        return {
            "success": True,
            "report": result["content"],
            "format": "markdown",
            "mode": "api",
            "model": result["model"],
        }
    except LLMServiceError as exc:
        return {
            "success": True,
            "report": _mock_report(event).strip(),
            "format": "markdown",
            "mode": "fallback",
            "model": "mock-template",
            "warning": str(exc),
        }
