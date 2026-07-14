"""虚假文本检测模块。

功能：
对采集到的评论/报道进行真实性评估，给出置信度分数。
采用 规则引擎 + 大模型 混合策略：
1. 规则层：基于文本特征（夸大用语、情感极端性、来源可信度）快速筛查
2. LLM层：调用大模型进行深度语义真实性判断（可选）
3. 兜底层：规则评估，确保无API时也能运行
"""

import json
import os
import re
from typing import Any, Dict, List

import requests


# ── 规则层 ────────────────────────────────────────────────────

# 夸大 / 煽动性用语列表
_EXAGGERATED_PATTERNS = [
    r"(绝对|100%|百分百|肯定|必[须需]|从来|永远|全是|都是假的)",
    r"(震惊|炸了|疯了|逆天|离谱|不敢相信|太可怕了|难以置信)",
    r"(惊天|重磅|独家|内幕|绝密|曝光|揭秘|真相|黑幕)",
    r"(千万别|一定[要不]|赶紧|立刻马|速看|紧急通知|马上删)",
    r"(不转不是|转发让更多人|扩散|接力|求扩散)",
    r"(最[强好好]的|世界第一|史上最|全国最|全球最)",
]

# 可疑来源模式
_SUSPICIOUS_SOURCE_PATTERNS = [
    r"(营销号|水军|工作室代发|推广合作)",
    r"(chatgpt|gpt|ai生成|人工智能生成|自动生成)",
]

# 信息缺失信号（缺乏具体人名、时间、地点、数字等可验证细节）
_INFO_SCARCITY_PATTERNS = [
    r"据说|听说|有消息称|据知情人士|网传|据爆料|有网友",
]


def _count_pattern_hits(text: str, patterns: List[str]) -> int:
    """统计文本中匹配到的模式数量。"""
    count = 0
    for pattern in patterns:
        if re.search(pattern, text, re.I):
            count += 1
    return count


def _has_verifiable_details(text: str) -> bool:
    """检测文本是否包含可验证的细节（人名、时间、地点、数字等）。"""
    has_name = bool(re.search(r"(某某|[张李王陈刘杨赵黄周吴]某|[A-Z]\w+)", text))
    has_time = bool(re.search(r"(\d{1,2}月\d{1,2}日|\d{4}年|上周|昨天|今天)", text))
    has_place = bool(re.search(r"(市|省|区|县|街道|路|广场|大厦|小区|村)", text))
    has_number = bool(re.search(r"(\d+[万亿千百]|\d+\.?\d*%)", text))
    details_found = sum([has_name, has_time, has_place, has_number])
    return details_found >= 2


def rule_based_credibility(text: str, source: str = "") -> Dict[str, Any]:
    """基于规则的虚假文本检测。

    返回:
        credibility: 0-100 的可信度分数
        risk_factors: 风险因素列表
        verdict: "可信" / "存疑" / "高风险"
    """
    if not isinstance(text, str) or not text.strip():
        return {"credibility": 50, "risk_factors": ["文本为空"], "verdict": "存疑"}

    text = text.strip()
    score = 100.0
    risk_factors: List[str] = []

    # 1. 夸大用语检查
    exaggerated_count = _count_pattern_hits(text, _EXAGGERATED_PATTERNS)
    if exaggerated_count >= 3:
        score -= 30
        risk_factors.append(f"多处使用夸大/煽动性用语（{exaggerated_count}处）")
    elif exaggerated_count >= 1:
        score -= exaggerated_count * 8
        risk_factors.append(f"含有夸大/煽动性用语（{exaggerated_count}处）")

    # 2. 信息缺失检查
    info_scarcity = _count_pattern_hits(text, _INFO_SCARCITY_PATTERNS)
    if info_scarcity >= 1:
        score -= info_scarcity * 10
        risk_factors.append("缺乏明确信息来源，使用模糊/传闻表述")

    # 3. 可验证细节检查
    if not _has_verifiable_details(text):
        score -= 15
        risk_factors.append("缺乏具体人物、时间、地点等可验证细节")

    # 4. 文本长度检查（过短或过长都可能可疑）
    if len(text) < 15:
        score -= 10
        risk_factors.append("文本过短，信息量不足")

    # 5. 来源可信度
    if source:
        suspicious_source = _count_pattern_hits(source, _SUSPICIOUS_SOURCE_PATTERNS)
        if suspicious_source > 0:
            score -= 20
            risk_factors.append("来源可信度较低")

    # 6. 极端情感检查（过于情绪化的文本更可能不实）
    extreme_emotion = len(re.findall(r"[!！]{2,}|[?？]{2,}", text))
    if extreme_emotion >= 2:
        score -= 5
        risk_factors.append("情感表达过于极端")

    score = max(0, min(100, score))

    if score >= 70:
        verdict = "可信"
    elif score >= 40:
        verdict = "存疑"
    else:
        verdict = "高风险"

    return {
        "credibility": round(score, 1),
        "risk_factors": risk_factors,
        "verdict": verdict,
    }


# ── LLM 层 ────────────────────────────────────────────────────

def llm_credibility_check(text: str) -> Dict[str, Any] | None:
    """使用大模型进行深度真实性判断。"""
    api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY") or "sk-2b4c81db82374941afe9972e7f1cf9c0"
    if not api_key:
        return None

    base_url = os.getenv("DEEPSEEK_BASE_URL") or os.getenv("OPENAI_BASE_URL") or "https://api.deepseek.com/v1"
    model = os.getenv("DEEPSEEK_MODEL") or os.getenv("OPENAI_MODEL") or "deepseek-chat"

    prompt = (
        "你是中文虚假信息检测助手。请分析以下文本的可信度，只输出 JSON：\n"
        '{"credibility": 0-100的分数, "verdict": "可信|存疑|高风险", '
        '"risk_factors": ["风险1", "风险2"], "reasoning": "简短分析"}\n\n'
        f"待分析文本：{text[:500]}"
    )

    try:
        resp = requests.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": "你是虚假信息检测助手，只输出 JSON。"},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.1,
            },
            timeout=20,
        )
        if resp.status_code == 200:
            payload = resp.json()
            content = payload.get("choices", [{}])[0].get("message", {}).get("content", "")
            content = content.strip()
            if content.startswith("```"):
                content = re.sub(r"^```(?:json)?\s*", "", content)
                content = re.sub(r"\s*```$", "", content)
            try:
                parsed = json.loads(content)
            except Exception:
                return None
            if isinstance(parsed, dict):
                return {
                    "credibility": float(parsed.get("credibility", 50)),
                    "verdict": str(parsed.get("verdict", "存疑")),
                    "risk_factors": parsed.get("risk_factors", []),
                    "reasoning": parsed.get("reasoning", ""),
                    "method": "llm",
                }
    except Exception:
        pass

    return None


# ── 混合检测 ──────────────────────────────────────────────────

def detect_fake_text(text: str, source: str = "", use_llm: bool = True) -> Dict[str, Any]:
    """虚假文本检测主入口。

    策略：优先使用 LLM，失败或不可用时回退到规则引擎。

    返回:
        credibility: 0-100 可信度分数
        verdict: "可信" / "存疑" / "高风险"
        risk_factors: 风险因素列表
        method: "llm" / "rule" / "hybrid"
    """
    if not isinstance(text, str) or not text.strip():
        return {
            "credibility": 50,
            "verdict": "存疑",
            "risk_factors": ["文本为空"],
            "method": "rule",
        }

    # 首先运行规则引擎
    rule_result = rule_based_credibility(text, source)

    # 尝试 LLM
    if use_llm:
        llm_result = llm_credibility_check(text)
        if llm_result:
            # 混合：LLM 和规则取加权平均
            hybrid_score = round(llm_result["credibility"] * 0.6 + rule_result["credibility"] * 0.4, 1)
            combined_factors = list(set(rule_result["risk_factors"] + llm_result.get("risk_factors", [])))
            return {
                "credibility": hybrid_score,
                "verdict": "可信" if hybrid_score >= 70 else "存疑" if hybrid_score >= 40 else "高风险",
                "risk_factors": combined_factors,
                "method": "hybrid",
                "rule_score": rule_result["credibility"],
                "llm_score": llm_result["credibility"],
                "reasoning": llm_result.get("reasoning", ""),
            }

    return {**rule_result, "method": "rule"}


def batch_detect(comments: List[Dict[str, Any]], content_key: str = "content", source_key: str = "source_title") -> List[Dict[str, Any]]:
    """对评论列表批量进行虚假检测。"""
    results = []
    for comment in comments:
        text = str(comment.get(content_key, ""))
        source = str(comment.get(source_key, ""))
        result = detect_fake_text(text, source)
        result["comment_id"] = comment.get("comment_id", comment.get("source_id", ""))
        result["text_preview"] = text[:100]
        results.append(result)
    return results


def summarize_credibility(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """汇总虚假检测结果。"""
    if not results:
        return {"total": 0, "trusted": 0, "suspicious": 0, "high_risk": 0, "avg_credibility": 50}

    verdict_counts = {"可信": 0, "存疑": 0, "高风险": 0}
    total_score = 0.0
    for r in results:
        verdict = r.get("verdict", "存疑")
        verdict_counts[verdict] = verdict_counts.get(verdict, 0) + 1
        total_score += r.get("credibility", 50)

    return {
        "total": len(results),
        "trusted": verdict_counts.get("可信", 0),
        "suspicious": verdict_counts.get("存疑", 0),
        "high_risk": verdict_counts.get("高风险", 0),
        "avg_credibility": round(total_score / len(results), 1),
        "trusted_ratio": round(verdict_counts.get("可信", 0) / len(results) * 100, 1),
        "high_risk_ratio": round(verdict_counts.get("高风险", 0) / len(results) * 100, 1),
    }
