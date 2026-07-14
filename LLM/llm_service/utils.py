"""事件数据清洗、摘要与通用工具。"""

import json
from typing import Any


EVENT_FIELDS = (
    "id",
    "title",
    "summary",
    "keywords",
    "sentiment_distribution",
    "trend_data",
    "platform_distribution",
    "occurTime",
    "source",
)

FIELD_ALIASES = {
    "event_title": "title",
    "event_summary": "summary",
    "sentiment": "sentiment_distribution",
    "heat_trend": "trend_data",
    "trend": "trend_data",
    "platforms": "platform_distribution",
}


def normalize_event_data(event_data: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(event_data, dict):
        raise ValueError("event_data 必须是 JSON 对象")
    normalized = dict(event_data)
    for source, target in FIELD_ALIASES.items():
        if target not in normalized and source in normalized:
            normalized[target] = normalized[source]
    return {key: normalized.get(key) for key in EVENT_FIELDS if key in normalized}


def event_context(event_data: dict[str, Any], max_chars: int = 12000) -> str:
    """序列化白名单字段，并限制长度，控制调用成本。"""
    text = json.dumps(
        normalize_event_data(event_data),
        ensure_ascii=False,
        indent=2,
        default=str,
    )
    return text[:max_chars]


def to_number(value: Any, field_name: str = "value") -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} 必须是数字") from exc
    if number != number or number in (float("inf"), float("-inf")):
        raise ValueError(f"{field_name} 必须是有限数字")
    return number


def compact_number(value: float) -> int | float:
    rounded = round(max(0.0, value), 2)
    return int(rounded) if rounded.is_integer() else rounded
