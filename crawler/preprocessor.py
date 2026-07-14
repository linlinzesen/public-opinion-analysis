"""数据预处理与正文提取模块。

功能：
1. 去重：基于内容相似度（Jaccard）和精确哈希去重
2. 去噪：过滤无意义文本（纯表情、纯数字、过短、广告等）
3. 格式标准化：统一时间格式、清理HTML标签、规范化空白
4. 正文提取：从原始网页文本中提取核心正文内容
"""

import hashlib
import re
from datetime import datetime
from typing import Any, Dict, List


# ── 文本清洗 ──────────────────────────────────────────────────

def clean_html(text: str) -> str:
    """去除 HTML 标签与转义字符。"""
    if not isinstance(text, str):
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&nbsp;", " ").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&amp;", "&").replace("&quot;", '"').replace("&#39;", "'")
    text = re.sub(r"&#?\w+;", "", text)
    return text


def normalize_whitespace(text: str) -> str:
    """规范化空白字符。"""
    if not isinstance(text, str):
        return ""
    text = re.sub(r"[\r\n\t]+", " ", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


def clean_text(text: str) -> str:
    """综合清洗：HTML + 空白规范化。"""
    return normalize_whitespace(clean_html(text))


# ── 正文提取 ──────────────────────────────────────────────────

def extract_main_content(html_or_text: str, min_length: int = 20) -> str:
    """从原始网页文本中提取核心正文内容。

    使用启发式规则：
    1. 去除 script/style 标签及其内容
    2. 按换行/段落分割，过滤导航、广告等噪音段落
    3. 保留最长的连续文本块
    """
    if not isinstance(html_or_text, str) or not html_or_text.strip():
        return ""

    text = html_or_text

    # 去除 script / style 块
    text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.S | re.I)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.S | re.I)
    text = re.sub(r"<nav[^>]*>.*?</nav>", "", text, flags=re.S | re.I)
    text = re.sub(r"<footer[^>]*>.*?</footer>", "", text, flags=re.S | re.I)

    # 去除 HTML 标签
    text = clean_html(text)

    # 按段落分割
    paragraphs = re.split(r"\n\s*\n|。\s*", text)
    good_paragraphs = []
    for para in paragraphs:
        para = normalize_whitespace(para)
        if not para:
            continue
        # 过滤噪音段落
        if _is_noise_paragraph(para):
            continue
        if len(para) >= min_length:
            good_paragraphs.append(para)

    return "。".join(good_paragraphs) if good_paragraphs else text[:500]


def _is_noise_paragraph(text: str) -> bool:
    """判断段落是否为噪音（导航、版权、广告等）。"""
    noise_patterns = [
        r"^(首页|登录|注册|关于我们|联系|版权|版权所有|ICP备|导航|更多)$",
        r"^(上一篇|下一篇|推荐阅读|相关文章|热门).*$",
        r"^(Copyright|All Rights Reserved|Powered by)",
        r"^(广告|推广|赞助|扫码|关注微信|下载APP)",
    ]
    text_stripped = text.strip()
    if len(text_stripped) < 10:
        return True
    for pattern in noise_patterns:
        if re.search(pattern, text_stripped, re.I):
            return True
    return False


def normalize_time(time_str: str) -> str:
    """将各种时间格式统一为 YYYY-MM-DD HH:MM:SS。"""
    if not isinstance(time_str, str) or not time_str.strip():
        return ""
    time_str = time_str.strip()

    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y/%m/%d %H:%M:%S",
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%a %b %d %H:%M:%S %z %Y",
        "%b %d %Y %H:%M:%S",
        "%m-%d %H:%M",
        "%m月%d日 %H:%M",
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(time_str, fmt)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue

    # 尝试提取数字日期
    match = re.search(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", time_str)
    if match:
        return f"{match.group(1)}-{match.group(2).zfill(2)}-{match.group(3).zfill(2)} 00:00:00"

    return time_str  # 无法解析，返回原文


# ── 去重 ──────────────────────────────────────────────────────

def _content_hash(text: str) -> str:
    """内容精确哈希。"""
    return hashlib.md5(text.encode("utf-8", errors="replace")).hexdigest()


def _jaccard_similarity(text_a: str, text_b: str) -> float:
    """基于字符二元组的 Jaccard 相似度。"""
    if not text_a or not text_b:
        return 0.0
    bigrams_a = set(text_a[i:i + 2] for i in range(len(text_a) - 1))
    bigrams_b = set(text_b[i:i + 2] for i in range(len(text_b) - 1))
    if not bigrams_a or not bigrams_b:
        return 0.0
    intersection = bigrams_a & bigrams_b
    union = bigrams_a | bigrams_b
    return len(intersection) / len(union)


def deduplicate_comments(
    comments: List[Dict[str, Any]],
    content_key: str = "content",
    similarity_threshold: float = 0.85,
) -> List[Dict[str, Any]]:
    """对评论列表进行去重。

    策略：
    1. 精确哈希去重（完全相同的文本）
    2. Jaccard 相似度去重（高度相似文本，视为重复/灌水）
    3. 保留最早出现的一条
    """
    if not comments:
        return []

    seen_hashes: set = set()
    kept: List[Dict[str, Any]] = []
    kept_texts: List[str] = []

    for comment in comments:
        content = str(comment.get(content_key, "")).strip()
        if not content:
            continue

        # 精确去重
        h = _content_hash(content)
        if h in seen_hashes:
            continue
        seen_hashes.add(h)

        # 相似度去重
        is_duplicate = False
        for existing_text in kept_texts[-50:]:  # 只检查最近 50 条，控制复杂度
            if _jaccard_similarity(content, existing_text) > similarity_threshold:
                is_duplicate = True
                break
        if is_duplicate:
            continue

        kept.append(comment)
        kept_texts.append(content)

    return kept


# ── 噪音过滤 ──────────────────────────────────────────────────

def is_noise_comment(text: str) -> bool:
    """判断评论是否为噪音（灌水、广告、无意义内容）。"""
    if not isinstance(text, str) or not text.strip():
        return True

    text = text.strip()
    # 过短
    if len(text) < 4:
        return True

    # 纯数字
    if re.match(r"^[\d\s.,，。]+$", text):
        return True

    # 纯表情/符号
    if re.match(r"^[\U0001F300-\U0001F9FF☀-➿ -⁯\s]+$", text):
        return True

    # 纯标点
    if re.match(r"^[!！?？.。，,;；'""''\[\]【】()（）…～~\-—\s]+$", text):
        return True

    # 灌水模式
    spam_patterns = [
        r"^(沙发|板凳|地板|前排|第一|打卡|mark|留名|路过)$",
        r"^.{1,3}(顶|赞|支持|加油|撒花).{0,3}$",
        r"^(dd|up|111|666|hhh|www|233)+$",
        r"^[a-zA-Z]{1,8}$",  # 纯字母无意义
    ]
    for pattern in spam_patterns:
        if re.match(pattern, text, re.I):
            return True

    return False


def filter_noise(comments: List[Dict[str, Any]], content_key: str = "content") -> List[Dict[str, Any]]:
    """过滤评论列表中的噪音。"""
    if not comments:
        return []
    result = []
    for c in comments:
        content = str(c.get(content_key, ""))
        if is_noise_comment(content):
            continue
        # 清洗后重新赋值
        c[content_key] = clean_text(content)
        result.append(c)
    return result


# ── 综合预处理流水线 ──────────────────────────────────────────

def preprocess_pipeline(
    comments: List[Dict[str, Any]],
    content_key: str = "content",
    time_key: str = "ctime_str",
) -> List[Dict[str, Any]]:
    """执行完整的预处理流水线：去噪 → 清洗 → 去重 → 时间标准化。

    返回清洗后的评论列表。
    """
    if not comments:
        return comments

    # 1. 去噪
    cleaned = filter_noise(comments, content_key=content_key)

    # 2. 时间标准化
    for c in cleaned:
        if time_key in c:
            c[time_key] = normalize_time(str(c.get(time_key, "")))

    # 3. 去重
    deduped = deduplicate_comments(cleaned, content_key=content_key)

    return deduped
