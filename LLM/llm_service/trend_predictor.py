"""使用 numpy 多项式拟合预测未来 24 小时热度 + 生命周期阶段判断。"""

from datetime import datetime, timedelta
from typing import Any

import numpy as np

from .utils import compact_number, to_number


TIME_KEYS = ("time", "timestamp", "datetime", "date")
VALUE_KEYS = ("value", "heat", "hotness", "count")

# ── 生命周期阶段 ─────────────────────────────────────────────
# 基于热度值变化的斜率与近期趋势判断舆情事件所处阶段

LIFECYCLE_STAGES = ("潜伏期", "成长期", "高潮期", "衰退期")


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
    """使用 numpy.polyfit 做一次多项式（线性）拟合，返回 (slope, intercept)。"""
    n = len(values)
    if n < 2:
        return 0.0, values[0] if n == 1 else 0.0
    x = np.arange(n, dtype=np.float64)
    y = np.array(values, dtype=np.float64)
    slope, intercept = np.polyfit(x, y, 1)
    return float(slope), float(intercept)


def _detect_lifecycle_stage(
    values: list[float], slope: float, interval_hours: float
) -> dict[str, Any]:
    """根据热度序列和线性回归斜率判断舆情事件所处生命周期。

    判断逻辑：
    - 潜伏期：序列后半段均值仍低于前半段 1.2 倍，且整体热度较低
    - 成长期：斜率 > 0.05（明显上升），且后半段均值显著高于前半段
    - 高潮期：后半段均值是前半段 1.5 倍以上且斜率趋于平稳（|slope| < 0.05）
    - 衰退期：斜率 < -0.05（明显下降），后半段均值低于前半段
    """
    n = len(values)
    arr = np.array(values, dtype=np.float64)

    if n < 4:
        if slope > 0.02:
            return {"stage": "成长期", "confidence": 0.6, "description": "数据量较少，根据上升趋势初步判断为成长期"}
        return {"stage": "成长期", "confidence": 0.4, "description": "数据量不足，默认为成长期，建议积累更多数据后复核"}

    half = n // 2
    first_half_avg = float(np.mean(arr[:half]))
    second_half_avg = float(np.mean(arr[half:]))
    ratio = second_half_avg / max(first_half_avg, 1.0)
    max_val = float(np.max(arr))
    recent_trend = float(arr[-1] - arr[-min(3, n)])

    # 最近 3 个点的斜率
    recent_n = min(3, n)
    recent_slope, _ = _linear_regression(values[-recent_n:])

    if slope > 0.05 and ratio > 1.3:
        return {
            "stage": "成长期",
            "confidence": min(0.9, 0.6 + abs(slope) * 2),
            "description": f"热度呈明显上升趋势（增幅 {((ratio - 1) * 100):.0f}%），处于快速成长期",
            "first_half_avg": compact_number(first_half_avg),
            "second_half_avg": compact_number(second_half_avg),
        }
    if slope > 0.02 and ratio > 1.15:
        return {
            "stage": "成长期",
            "confidence": min(0.8, 0.5 + abs(slope) * 3),
            "description": "热度稳步上升，处于成长阶段",
            "first_half_avg": compact_number(first_half_avg),
            "second_half_avg": compact_number(second_half_avg),
        }

    if ratio > 1.5 and abs(slope) < 0.05:
        return {
            "stage": "高潮期",
            "confidence": 0.75,
            "description": "热度处于高位且趋势平稳，判断进入高潮期/平台期",
            "first_half_avg": compact_number(first_half_avg),
            "second_half_avg": compact_number(second_half_avg),
        }
    if ratio > 1.2 and abs(recent_slope) < 0.03 and second_half_avg > first_half_avg * 1.25:
        return {
            "stage": "高潮期",
            "confidence": 0.65,
            "description": "热度已攀至较高水平，近期波动趋缓，可能进入高潮期",
            "first_half_avg": compact_number(first_half_avg),
            "second_half_avg": compact_number(second_half_avg),
        }

    if slope < -0.05 or (recent_trend < 0 and ratio < 0.9):
        return {
            "stage": "衰退期",
            "confidence": min(0.9, 0.6 + abs(slope) * 2),
            "description": "热度呈下降趋势，事件关注度正在消退",
            "first_half_avg": compact_number(first_half_avg),
            "second_half_avg": compact_number(second_half_avg),
        }

    # 默认：整体变化不大 → 潜伏期
    if max_val < 100:
        return {
            "stage": "潜伏期",
            "confidence": 0.7,
            "description": "整体热度较低且无明显增长，事件处于潜伏/酝酿阶段",
            "first_half_avg": compact_number(first_half_avg),
            "second_half_avg": compact_number(second_half_avg),
        }
    return {
        "stage": "潜伏期",
        "confidence": 0.5,
        "description": "热度变化不显著，建议持续监测以确认是否进入新阶段",
        "first_half_avg": compact_number(first_half_avg),
        "second_half_avg": compact_number(second_half_avg),
    }


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
            "lifecycle": {"stage": "潜伏期", "confidence": 0.3, "description": "数据不足，无法判断"},
        }
    try:
        skipped = 0
        parsed = []
        for item in trend_data:
            if not isinstance(item, dict):
                continue
            try:
                time_val = _pick(item, TIME_KEYS, "时间")
                # 跳过 NaT / NaN / null / 空字符串等无效时间
                if isinstance(time_val, str) and time_val.strip().lower() in ("nat", "nan", "null", "none", ""):
                    skipped += 1
                    continue
                parsed.append(
                    (
                        _parse_time(time_val),
                        to_number(_pick(item, VALUE_KEYS, "热度值"), "热度值"),
                    )
                )
            except (ValueError, TypeError):
                skipped += 1
                continue

        if len(parsed) < 2:
            return {
                "success": False,
                "error": f"trend_data 至少需要 2 个有效数据点（已跳过 {skipped} 个无效条目）",
                "predictions": [],
                "lifecycle": {"stage": "潜伏期", "confidence": 0.3, "description": "有效数据不足，无法判断"},
            }

        parsed.sort(key=lambda point: point[0])
        # 去重：相同时间点保留第一个
        seen_times = set()
        unique_parsed = []
        for point in parsed:
            if point[0] not in seen_times:
                seen_times.add(point[0])
                unique_parsed.append(point)
        parsed = unique_parsed

        if len(parsed) < 2:
            return {
                "success": False,
                "error": f"去重后有效数据点不足 2 个（已跳过 {skipped} 个无效条目）",
                "predictions": [],
                "lifecycle": {"stage": "潜伏期", "confidence": 0.3, "description": "去重后数据不足，无法判断"},
            }

        intervals = [
            (parsed[i][0] - parsed[i - 1][0]).total_seconds()
            for i in range(1, len(parsed))
        ]
        interval_seconds = float(np.median(intervals))
        if interval_seconds <= 0:
            raise ValueError("趋势数据时间顺序异常")

        slope, intercept = _linear_regression([point[1] for point in parsed])
        values_arr = np.array([p[1] for p in parsed], dtype=np.float64)
        future_count = max(1, int(24 * 3600 / interval_seconds))
        future_count = min(future_count, 24)  # 演示系统限制响应体大小

        # 使用 numpy.polyval 批量计算预测值
        future_x = np.arange(len(parsed), len(parsed) + future_count, dtype=np.float64)
        predicted_vals = np.polyval([slope, intercept], future_x)

        predictions = []
        last_time = parsed[-1][0]
        for step in range(1, future_count + 1):
            predicted = float(predicted_vals[step - 1])
            next_time = last_time + timedelta(seconds=interval_seconds * step)
            predictions.append(
                {
                    "time": next_time.isoformat(),
                    "value": compact_number(predicted),
                }
            )

        # 相对当前热度变化小于 5% 视为平稳，减少轻微波动造成误判。
        current = max(abs(values_arr[-1]), 1.0)
        change_ratio = (float(predictions[-1]["value"]) - float(values_arr[-1])) / current
        trend = "上升" if change_ratio > 0.05 else "下降" if change_ratio < -0.05 else "平稳"

        # 生命周期阶段判断
        lifecycle = _detect_lifecycle_stage(values_arr.tolist(), slope, interval_seconds / 3600)

        return {
            "success": True,
            "method": "numpy_polyfit",
            "trend": trend,
            "change_ratio": round(change_ratio, 4),
            "interval_hours": round(interval_seconds / 3600, 2),
            "predictions": predictions,
            "lifecycle": lifecycle,
        }
    except (ValueError, TypeError) as exc:
        return {"success": False, "error": str(exc), "predictions": [],
                "lifecycle": {"stage": "潜伏期", "confidence": 0.2, "description": f"数据解析异常: {exc}"}}
