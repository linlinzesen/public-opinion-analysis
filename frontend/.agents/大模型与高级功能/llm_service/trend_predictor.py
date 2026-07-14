"""使用一元线性回归预测未来 24 小时热度，不依赖 numpy。"""

from datetime import datetime, timedelta
from typing import Any

from .utils import compact_number, to_number


TIME_KEYS = ("time", "timestamp", "datetime", "date")
VALUE_KEYS = ("value", "heat", "hotness", "count")


def _parse_time(value: Any) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("趋势数据时间必须是非空字符串")
    text = value.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"无法解析时间：{value}，请使用 ISO 8601 格式") from exc


def _pick(item: dict[str, Any], keys: tuple[str, ...], label: str) -> Any:
    for key in keys:
        if key in item:
            return item[key]
    raise ValueError(f"趋势数据缺少{label}字段，可用字段：{', '.join(keys)}")


def _linear_regression(values: list[float]) -> tuple[float, float]:
    n = len(values)
    mean_x = (n - 1) / 2
    mean_y = sum(values) / n
    denominator = sum((x - mean_x) ** 2 for x in range(n))
    slope = (
        sum((x - mean_x) * (y - mean_y) for x, y in enumerate(values))
        / denominator
        if denominator
        else 0.0
    )
    return slope, mean_y - slope * mean_x


def predict_trend(trend_data: list[dict[str, Any]]) -> dict[str, Any]:
    """预测未来 24 小时。

    支持 time/timestamp/date 与 value/heat/hotness/count 等常见字段别名。
    小时数据输出 24 点；日数据输出未来 1 天的 1 个点。
    """
    if not isinstance(trend_data, list) or len(trend_data) < 2:
        return {
            "success": False,
            "error": "trend_data 至少需要 2 个数据点",
            "predictions": [],
        }
    try:
        parsed = []
        for item in trend_data:
            if not isinstance(item, dict):
                raise ValueError("trend_data 中的每一项必须是对象")
            parsed.append(
                (
                    _parse_time(_pick(item, TIME_KEYS, "时间")),
                    to_number(_pick(item, VALUE_KEYS, "热度值"), "热度值"),
                )
            )
        parsed.sort(key=lambda point: point[0])
        if any(parsed[i][0] == parsed[i - 1][0] for i in range(1, len(parsed))):
            raise ValueError("趋势数据中不能包含重复时间点")

        intervals = [
            (parsed[i][0] - parsed[i - 1][0]).total_seconds()
            for i in range(1, len(parsed))
        ]
        interval_seconds = sorted(intervals)[len(intervals) // 2]
        if interval_seconds <= 0:
            raise ValueError("趋势数据时间顺序异常")

        slope, intercept = _linear_regression([point[1] for point in parsed])
        future_count = max(1, int(24 * 3600 / interval_seconds))
        future_count = min(future_count, 24)  # 演示系统限制响应体大小
        predictions = []
        last_time = parsed[-1][0]
        for step in range(1, future_count + 1):
            predicted = slope * (len(parsed) - 1 + step) + intercept
            next_time = last_time + timedelta(seconds=interval_seconds * step)
            predictions.append(
                {
                    "time": next_time.isoformat(),
                    "value": compact_number(predicted),
                }
            )

        # 相对当前热度变化小于 5% 视为平稳，减少轻微波动造成误判。
        current = max(abs(parsed[-1][1]), 1.0)
        change_ratio = (float(predictions[-1]["value"]) - parsed[-1][1]) / current
        trend = "上升" if change_ratio > 0.05 else "下降" if change_ratio < -0.05 else "平稳"
        return {
            "success": True,
            "method": "linear_regression",
            "trend": trend,
            "change_ratio": round(change_ratio, 4),
            "interval_hours": round(interval_seconds / 3600, 2),
            "predictions": predictions,
        }
    except (ValueError, TypeError) as exc:
        return {"success": False, "error": str(exc), "predictions": []}
