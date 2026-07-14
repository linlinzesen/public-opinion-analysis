"""基于当前舆情事件的智能问答。"""

import re
from typing import Any

from .config import get_config
from .llm_client import LLMServiceError, chat_completion
from .prompts import SYSTEM_PROMPT
from .utils import event_context, normalize_event_data


UNRELATED_PATTERNS = (
    r"写.{0,4}(代码|程序|作文|诗)",
    r"(天气|彩票|星座|翻译|菜谱|数学题)",
    r"(忽略|忘记).{0,12}(指令|要求|提示词)",
)


def _is_obviously_unrelated(question: str, event_data: dict[str, Any]) -> bool:
    if any(re.search(pattern, question, re.I) for pattern in UNRELATED_PATTERNS):
        return True
    title = str(event_data.get("title", ""))
    keywords = event_data.get("keywords") or []
    terms = [title] + ([str(x) for x in keywords] if isinstance(keywords, list) else [])
    # 常见事件分析意图无需包含标题关键词。
    analysis_terms = ("事件", "舆情", "热度", "趋势", "情感", "风险", "平台", "传播", "建议")
    return not any(term and term in question for term in terms + list(analysis_terms))


def _mock_answer(event: dict[str, Any], question: str) -> str:
    title = event.get("title") or "当前事件"
    sentiment = event.get("sentiment_distribution") or {}
    platforms = event.get("platform_distribution") or {}
    if "情感" in question or "负面" in question:
        return f"根据当前数据，{title}的情感分布为：{sentiment or '暂无数据'}。建议重点关注负面占比及其变化。"
    if "平台" in question or "传播" in question:
        return f"根据当前数据，{title}的平台分布为：{platforms or '暂无数据'}。可优先关注占比最高的平台。"
    if "风险" in question:
        return f"当前可从热度变化和负面情感占比研判{title}的风险；现有演示数据有限，建议结合最新趋势与异常增长点复核。"
    summary = event.get("summary") or "暂无事件摘要"
    return f"关于“{title}”，当前资料显示：{summary}。如需进一步分析，可询问传播趋势、情感倾向或风险。"


def ask_event_question(event_data: dict, question: str) -> dict:
    if not isinstance(question, str) or not question.strip():
        return {"success": False, "error": "question 不能为空"}
    try:
        event = normalize_event_data(event_data)
    except ValueError as exc:
        return {"success": False, "error": str(exc)}
    if not event.get("title") and not event.get("summary"):
        return {"success": False, "error": "event_data 至少需要 title 或 summary"}
    question = question.strip()[:1000]
    if _is_obviously_unrelated(question, event):
        return {
            "success": True,
            "answer": "这个问题与当前舆情事件关联不明显。请围绕该事件的传播趋势、情感倾向、平台分布或风险进行提问。",
            "mode": "guard",
            "model": None,
        }

    if get_config().mock_mode:
        return {
            "success": True,
            "answer": _mock_answer(event, question),
            "mode": "mock",
            "model": "mock-rule-based",
        }
    try:
        result = chat_completion(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"当前事件资料：\n{event_context(event)}\n\n用户问题：{question}",
                },
            ]
        )
        return {
            "success": True,
            "answer": result["content"],
            "mode": "api",
            "model": result["model"],
        }
    except LLMServiceError as exc:
        # API 故障时降级到规则回答，保障课程演示可用。
        return {
            "success": True,
            "answer": _mock_answer(event, question),
            "mode": "fallback",
            "model": "mock-rule-based",
            "warning": str(exc),
        }
