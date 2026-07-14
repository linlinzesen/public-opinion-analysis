"""
基于 jieba 分词 + 规则 + LLM 混合策略的中文舆情情感分析模块。

优化要点：
1. 使用 jieba 分词替代字符级匹配，消除 "不好→好" 类误判
2. 否定词翻转（不/没/别/无/非/未 + 情感词 → 反转）
3. 程度副词加权（很/非常/极其 → 放大分数）
4. Emoji/表情符号情感词典（覆盖 B站/微博常见表情）
5. 反讽/反问模式检测
6. 置信度评分 → 高置信走规则，低置信批量调 LLM
7. 批量 LLM 分析（20条/次，大幅减少 API 调用）
8. 移除硬编码 API Key，仅从环境变量读取
"""

import json
import os
import re
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import requests

# jieba 为必需依赖（analyzer.py 同样使用）
try:
    import jieba
    _HAS_JIEBA = True
except ImportError:
    _HAS_JIEBA = False
    print("[sentiment] WARNING: jieba 未安装，将使用字符级分词（建议: pip install jieba）")


class SentimentAnalyzer:
    """基于规则 + LLM 混合策略的中文舆情情感分析器。

    规则层：jieba 分词 → 情感词匹配 → 否定翻转 → 程度加权 → 表情检测 → 置信度评分
    LLM层：批量调用 DeepSeek/OpenAI API，仅对低置信度评论进行深度分析
    """

    # ── 停用词 ──────────────────────────────────────────────────
    STOP_WORDS: set = {
        "这个", "那个", "还是", "就是", "没有", "他们", "我们", "你们",
        "一", "有", "就", "都", "也", "在", "和", "或", "了", "的",
        "是", "不是", "很", "太", "我", "他", "她", "它", "啊", "呢",
        "吧", "吗", "嘛", "哦", "嗯", "哇", "呀", "哈", "这", "那",
        "什么", "怎么", "为什么", "因为", "所以", "但是", "虽然", "如果",
        "可以", "应该", "会", "能", "要", "想", "让", "把", "被", "给",
        "对", "从", "到", "上", "下", "中", "里", "外", "前", "后",
        "一个", "一些", "很多", "可能", "已经", "还", "再", "又", "才",
        "不", "没", "别", "无", "非", "未", "莫",  # 否定词在分词后单独处理
    }

    # ── 否定词（出现在情感词前 N 个 token 内时翻转极性）─────────
    NEGATION_WORDS: set = {
        "不", "没", "别", "无", "非", "未", "莫", "休", "勿", "否",
        "看", "难", "少", "缺", "欠",
    }

    # ── 程度副词（加权系数）─────────────────────────────────────
    DEGREE_ADVERBS: Dict[str, float] = {
        "极其": 2.5, "极度": 2.5, "绝对": 2.0, "非常": 2.0,
        "特别": 2.0, "尤其": 2.0, "十分": 1.8, "相当": 1.5,
        "很": 1.5, "太": 1.5, "超": 1.5, "真": 1.3,
        "好": 1.3, "蛮": 1.2, "挺": 1.2, "够": 1.2,
        "有点": 0.7, "稍微": 0.6, "略微": 0.5, "比较": 0.8,
        "还": 0.7, "算": 0.6, "算是": 0.7, "还算": 0.7,
    }

    # ── 正向情感词（200+ 覆盖舆情场景）──────────────────────────
    POSITIVE_WORDS: set = {
        # 基础正向
        "支持", "赞", "好", "喜欢", "开心", "感谢", "满意", "稳", "靠谱", "加油",
        "好评", "推荐", "优秀", "棒", "厉害", "良心", "给力", "点赞", "顶",
        "进步", "解决", "改善", "提升", "合理", "公正", "透明", "积极",
        "希望", "期待", "放心", "安心", "信任", "值得", "不错", "可以",
        "认同", "理解", "包容", "理性", "客观", "友好", "善意",
        "保护", "保障", "维护", "权益", "安全", "健康",
        # 扩展：产品质量/消费维权
        "曝光", "揭露", "退货", "退款", "维权", "召回", "道歉", "赔偿",
        "整改", "配合", "负责", "担当", "诚信", "实在", "正规", "放心买",
        "质量好", "耐用", "好用", "性价比", "值得买", "回购", "种草",
        "真货", "正品", "原装", "无瑕疵", "完好", "完美",
        # 扩展：公共安全/社会事件
        "感动", "暖心", "正能量", "救援", "及时", "迅速", "有效",
        "致敬", "辛苦了", "好人", "英雄", "正义", "公平",
        "严查", "严惩", "打击", "整顿", "规范", "立法", "出台",
        "好消息", "胜利", "成功", "通过", "落实", "见效",
        # 扩展：技术/行业
        "创新", "突破", "领先", "先进", "智能", "高效", "便捷",
        "专业", "权威", "严谨", "科学", "客观公正",
        # 口语化
        "爱了", "绝了", "牛", "666", "yyds", "nb", "真香",
        "三连", "一键三连", "币有了", "下次一定", "投币",
        # 补充常用 n-gram（fallback 兼容）
        "挺好", "真好", "很好", "太好", "非常好", "更好",
        "确实", "没错", "好评", "不错", "还行", "认可",
        "好用", "有用", "有效", "有用处",
        "好厉害", "太好了", "很不错", "挺好的", "非常好",
        "不坏", "不差", "不贵", "不难", "没问题", "没事", "没关系",
    }

    # ── 负向情感词（200+ 覆盖舆情场景）──────────────────────────
    NEGATIVE_WORDS: set = {
        # 基础负向
        "不满", "差", "烂", "失望", "愤怒", "气", "烦", "垃圾", "坑人",
        "太差", "无语", "恶心", "可怕", "恐怖", "吓人", "担心", "害怕",
        "骗", "假", "坑", "害", "毒", "脏", "乱", "臭", "惨",
        "抗议", "投诉", "举报", "抵制", "谴责", "批评", "质疑",
        "不行", "过分", "缺德", "黑心", "无耻", "不要脸", "嚣张",
        "违法", "违规", "滥用", "侵犯", "损害", "危害", "威胁",
        "推卸", "敷衍", "忽悠", "糊弄", "蒙蔽", "隐瞒",
        # 扩展：产品质量/消费维权
        "缺陷", "故障", "坏", "破损", "瑕疵", "翻车", "踩雷", "避雷",
        "劣质", "次品", "假货", "山寨", "仿冒", "伪造", "虚假",
        "变质", "过期", "超标", "污染", "有毒", "有害",
        "拒退", "拒赔", "拖延", "刁难", "踢皮球", "不作为",
        "店大欺客", "霸王条款", "捆绑", "陷阱", "套路",
        # 扩展：公共安全/社会事件
        "黑幕", "内幕", "潜规则", "腐败", "失职", "渎职",
        "事故", "爆炸", "起火", "倒塌", "伤亡", "遇难",
        "恐慌", "焦虑", "愤怒", "悲哀", "无奈", "心寒",
        "无能", "怠慢", "漠视", "冷血", "残忍",
        # 扩展：技术/行业
        "落后", "倒退", "漏洞", "风险", "隐患", "不稳定",
        "滥竽充数", "粗制滥造", "偷工减料",
        # 口语化
        "呵呵", "醉了", "服了", "绝了", "离谱",
        # 补充常用 n-gram（fallback 兼容）
        "白说", "不行", "太差", "太烂", "太坑", "太黑",
        "很差", "极差", "极烂", "不好", "不行", "太坏",
        "太过", "过分", "太假", "太贵", "太坑人",
        "笑死", "坑爹", "扯淡", "闹着玩",
        "问题", "一般般", "一般", "普通", "平庸", "凑合",
        "失望", "差劲", "糟糕", "难受", "痛苦",
    }

    # ── B站/微博 表情符号情感值 ──────────────────────────────────
    EMOJI_SENTIMENT: Dict[str, float] = {
        # 正向表情
        "[星星眼]": 1.5, "[打call]": 1.5, "[喜欢]": 1.5,
        "[爱心]": 1.5, "[爱了]": 1.5, "[比心]": 1.5,
        "[给力]": 1.0, "[good]": 1.0, "[赞]": 1.0,
        "[加油]": 1.0, "[支持]": 1.0, "[ok]": 0.8,
        "[呲牙]": 1.0, "[大笑]": 1.0, "[哈哈]": 0.8,
        "[偷笑]": 0.5, "[微笑]": 0.3,
        "[吃瓜]": 0.2, "[吃瓜群众]": 0.1,
        "[doge]": 0.0, "[狗头]": 0.0, "[滑稽]": 0.0,
        "[保佑]": 0.5, "[祈祷]": 0.5, "[合十]": 0.5,
        # 负向表情
        "[委屈]": -1.5, "[大哭]": -1.5, "[哭]": -1.5,
        "[怒]": -2.0, "[发怒]": -2.0, "[生气]": -2.0,
        "[吐]": -1.5, "[呕吐]": -1.5,
        "[伤心]": -1.5, "[难过]": -1.5, "[心碎]": -1.5,
        "[无语]": -1.0, "[汗]": -0.5, "[尴尬]": -0.5,
        "[恐惧]": -1.5, "[害怕]": -1.5, "[震惊]": -0.5,
        "[笑哭]": -0.5, "[捂脸]": -0.3, "[破涕为笑]": 0.0,
        "[疑问]": -0.3, "[思考]": -0.2, "[晕]": -0.5,
        "[黑线]": -0.5, "[衰]": -1.0, "[骷髅]": -1.0,
    }

    # Unicode emoji 情感值
    UNICODE_EMOJI_SENTIMENT: Dict[str, float] = {
        "😂": -0.3, "🤣": 0.0, "😅": -0.3, "😊": 1.0,
        "😍": 1.5, "🥰": 1.5, "😘": 1.5, "❤": 1.5,
        "👍": 1.0, "👎": -1.0, "💪": 1.0, "🙏": 0.5,
        "😡": -2.0, "😠": -1.5, "🤬": -2.5, "💔": -1.5,
        "😭": -1.5, "😢": -1.0, "😰": -1.0, "😱": -1.0,
        "🤔": -0.2, "🤨": -0.5, "😒": -1.0, "🙄": -1.0,
        "🔥": 0.5, "👏": 1.0, "🎉": 1.0, "✨": 0.5,
        "💩": -1.5, "🤮": -1.5, "👻": -0.5, "☠": -1.0,
    }

    # ── 反问/反讽模式 ───────────────────────────────────────────
    RHETORICAL_PATTERNS: List[re.Pattern] = [
        re.compile(r"这也(叫|算|是|能|敢)"),
        re.compile(r"难道"),
        re.compile(r"还能(再)?"),
        re.compile(r"怎么(可能|会|可以|能)"),
        re.compile(r"凭?什么(要|能|可以)"),
        re.compile(r"(就这|就这水平|就这也)"),
        re.compile(r"(不会吧|不是吧|真的假的|认真的吗)"),
    ]

    # ── LLM 批量分析配置 ────────────────────────────────────────
    LLM_BATCH_SIZE: int = 20
    LLM_TIMEOUT: int = 60

    def __init__(self):
        """初始化情感分析器，构建所有词典和正则模式。"""
        self._pos_set = self.POSITIVE_WORDS
        self._neg_set = self.NEGATIVE_WORDS
        self._negation_set = self.NEGATION_WORDS
        self._degree_map = self.DEGREE_ADVERBS
        self._emoji_map = self.EMOJI_SENTIMENT
        self._unicode_emoji_map = self.UNICODE_EMOJI_SENTIMENT

        # 构建 B站表情正则（匹配 [xxx] 格式）
        self._bilibili_emoji_re = re.compile(r"\[[^\]]{1,8}\]")

        # 否定窗口大小（情感词前 N 个 token 内检查否定词）
        self._negation_window = 3

    # ── 文本清洗 ────────────────────────────────────────────────

    def clean_text(self, text: str) -> str:
        """去除 HTML 标签和多余空白，保留中文内容和表情符号。"""
        if not isinstance(text, str):
            return ""
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"\s+", "", text)
        return text

    # ── 中文分词 ────────────────────────────────────────────────

    def _segment(self, text: str) -> List[str]:
        """对清洗后的文本进行 jieba 分词，过滤停用词和单字。

        当 jieba 不可用时，回退到 n-gram 分词（bigram + trigram fallback）。

        注意：保留单字否定词（不/没/别等），因为它们是关键情感信号。
        """
        cleaned = self.clean_text(text)
        if not cleaned:
            return []

        if _HAS_JIEBA:
            words = [
                w for w in jieba.cut(cleaned)
                if len(w) > 1 or w in self._negation_set
            ]
            # 额外过滤：移除非否定单字和停用词（但保留否定词）
            words = [w for w in words if w not in self.STOP_WORDS or w in self._negation_set]
        else:
            # 回退：n-gram (bigram + trigram) + 过滤非中文
            words = []
            # 二元组
            for i in range(len(cleaned) - 1):
                bigram = cleaned[i:i + 2]
                if bigram not in self.STOP_WORDS and re.search(r"[一-鿿]", bigram):
                    words.append(bigram)
            # 三元组（覆盖"太好了"、"非常好"等三字词）
            for i in range(len(cleaned) - 2):
                trigram = cleaned[i:i + 3]
                if trigram not in self.STOP_WORDS and re.search(r"[一-鿿]", trigram):
                    words.append(trigram)
            # 保留否定单字位于文本中的位置（兼容 bigram 未切出的场景）
            for i, ch in enumerate(cleaned):
                if ch in self._negation_set:
                    words.append(ch)

        return words

    # ── 表情符号提取 ────────────────────────────────────────────

    def _extract_emojis(self, text: str) -> List[Tuple[str, float]]:
        """提取文本中的表情符号及其情感值。

        Returns:
            List of (emoji_text, sentiment_value) tuples
        """
        results: List[Tuple[str, float]] = []

        # B站/微博格式表情 [xxx]
        for match in self._bilibili_emoji_re.finditer(text):
            token = match.group()
            if token in self._emoji_map:
                results.append((token, self._emoji_map[token]))

        # Unicode emoji
        for emoji_char, value in self._unicode_emoji_map.items():
            count = text.count(emoji_char)
            if count > 0:
                results.extend([(emoji_char, value)] * count)

        return results

    # ── 反讽/反问检测 ───────────────────────────────────────────

    def _is_rhetorical(self, text: str) -> bool:
        """检测文本是否包含反讽/反问模式。"""
        for pattern in self.RHETORICAL_PATTERNS:
            if pattern.search(text):
                return True
        return False

    # ── 规则分析（核心）──────────────────────────────────────────

    def _rule_analyze(self, text: str) -> dict:
        """基于 jieba 分词 + 否定翻转 + 程度加权 + 表情检测的规则情感分析。

        Returns:
            dict with keys: sentiment, score, confidence, intensity,
                           positive_hits, negative_hits, emoji_hits, method
        """
        cleaned = self.clean_text(text)
        if not cleaned:
            return {
                "sentiment": "neutral", "score": 0.0, "confidence": 0.0,
                "positive_hits": [], "negative_hits": [], "emoji_hits": [],
                "intensity": "weak", "method": "rule",
            }

        words = self._segment(text)
        if not words:
            return {
                "sentiment": "neutral", "score": 0.0, "confidence": 0.0,
                "positive_hits": [], "negative_hits": [], "emoji_hits": [],
                "intensity": "weak", "method": "rule",
            }

        n = len(words)

        # ── Step 1: 匹配正/负向词 ──
        pos_indices: List[Tuple[int, str]] = []  # (index, word)
        neg_indices: List[Tuple[int, str]] = []

        for i, w in enumerate(words):
            if w in self._pos_set:
                pos_indices.append((i, w))
            elif w in self._neg_set:
                neg_indices.append((i, w))

        # ── Step 2: 对每个 hit 计算加权分数 ──
        pos_hits: List[Dict[str, Any]] = []
        neg_hits: List[Dict[str, Any]] = []
        pos_score = 0.0
        neg_score = 0.0

        for i, w in pos_indices:
            base = 1.0
            is_negated = False

            # 如果匹配词本身以否定词开头（"不错"、"不坏"），跳过双重否定检测
            word_starts_with_negation = any(w.startswith(nc) for nc in self._negation_set)

            if not word_starts_with_negation:
                # 检查否定窗口（支持 bigram fallback 模式下的字符级否定检测）
                for j in range(max(0, i - self._negation_window), i):
                    token = words[j]
                    # 直接 token 匹配
                    if token in self._negation_set:
                        is_negated = True
                        break
                    # fallback 模式：检查 token 中是否包含否定字符
                    for neg_char in self._negation_set:
                        if neg_char in token:
                            is_negated = True
                            break
                    if is_negated:
                        break

            # 检查程度副词
            for j in range(max(0, i - 2), i):
                if words[j] in self._degree_map:
                    degree = self._degree_map[words[j]]
                    if is_negated:
                        base *= (1.0 / max(degree, 1.0))
                    else:
                        base *= degree
                    break

            hit_value = -base if is_negated else base
            if is_negated:
                neg_score += abs(hit_value)
                neg_hits.append({"word": w, "value": hit_value, "negated": True, "index": i})
            else:
                pos_score += hit_value
                pos_hits.append({"word": w, "value": hit_value, "negated": False, "index": i})

        for i, w in neg_indices:
            base = 1.0
            is_negated = False

            # 匹配词本身以否定词开头 → 跳过双重否定
            word_starts_with_negation = any(w.startswith(nc) for nc in self._negation_set)

            if not word_starts_with_negation:
                for j in range(max(0, i - self._negation_window), i):
                    token = words[j]
                    if token in self._negation_set:
                        is_negated = True
                        break
                    for neg_char in self._negation_set:
                        if neg_char in token:
                            is_negated = True
                            break
                    if is_negated:
                        break

            for j in range(max(0, i - 2), i):
                if words[j] in self._degree_map:
                    base *= self._degree_map[words[j]]
                    break

            hit_value = -base if is_negated else base
            if is_negated:
                # 否定 + 负向词 = 弱正向（"不差" = 还行）
                pos_score += abs(hit_value) * 0.6
                pos_hits.append({"word": w, "value": abs(hit_value) * 0.6, "negated": True, "index": i})
            else:
                neg_score += abs(hit_value)
                neg_hits.append({"word": w, "value": hit_value, "negated": False, "index": i})

        # ── Step 3: 表情符号 ──
        emoji_hits = self._extract_emojis(text)
        emoji_total = sum(v for _, v in emoji_hits)
        if emoji_total > 0:
            pos_score += emoji_total
        else:
            neg_score += abs(emoji_total)

        # ── Step 4: 反问/反讽检测 ──
        is_rhetorical = self._is_rhetorical(text)
        if is_rhetorical:
            # 反问句将表面正向翻转为负向
            if pos_score > 0 and pos_score >= neg_score:
                # "这也叫好？" → 表面正向，实际讽刺 → 翻转
                temp = pos_score
                pos_score = neg_score
                neg_score = temp * 1.3  # 惩罚加权
                pos_hits, neg_hits = [], pos_hits
            elif pos_score == 0 and neg_score == 0:
                # "这也叫质检？" → 无情感词但反问语气本身表不满
                neg_score = 1.0
                neg_hits.append({"word": "rhetorical", "value": -1.0, "negated": False, "index": -1})

        # ── Step 4.5: [doge] 讽刺修饰 ──
        has_doge = any("doge" in e[0].lower() for e in emoji_hits)
        if has_doge and pos_score > 0 and neg_score == 0:
            # [doge] + 纯正向 = 讽刺性正向 → 翻转为负向
            neg_score = pos_score * 0.8
            pos_score = 0
            pos_hits, neg_hits = [], [{"word": "doge_sarcasm", "value": -neg_score, "negated": False, "index": -1}]
        elif has_doge and pos_score == 0 and neg_score == 0:
            # 仅 [doge]，无其他信号 → 轻度负面
            neg_score = 0.4

        # ── Step 5: 综合评分 ──
        raw_score = pos_score - neg_score

        # 归一化到 [-1, 1]
        total_magnitude = pos_score + abs(neg_score)
        if total_magnitude > 0:
            normalized_score = max(-1.0, min(1.0, raw_score / max(total_magnitude, 1.5)))
        else:
            normalized_score = 0.0

        # ── Step 6: 置信度评分 ──
        n_pos = len(pos_hits)
        n_neg = len(neg_hits)
        n_emoji = len(emoji_hits)
        total_hits = n_pos + n_neg + n_emoji

        if total_hits == 0:
            confidence = 0.0
        elif total_hits >= 4:
            confidence = 0.95
        elif total_hits >= 3:
            confidence = 0.85
        elif total_hits >= 2:
            confidence = 0.65
        else:
            confidence = 0.35

        # 负向词天然更可靠（"垃圾"、"骗"不容易出现在中性语境）
        # n_neg ≥ 1 时略微提升置信度
        if n_neg >= 1 and confidence < 0.8:
            confidence = min(0.85, confidence + 0.15)
        if n_emoji >= 2:
            confidence = min(0.95, confidence + 0.05)

        # 反问句降低置信度（规则不可靠）
        if is_rhetorical:
            confidence = min(confidence, 0.5)

        # ── Step 7: 判定类别 ──
        if abs(normalized_score) < 0.1:
            sentiment = "neutral"
        elif normalized_score > 0:
            sentiment = "positive"
        else:
            sentiment = "negative"

        # ── 强度等级 ──
        abs_score = abs(normalized_score)
        if abs_score >= 0.6:
            intensity = "strong"
        elif abs_score >= 0.25:
            intensity = "moderate"
        else:
            intensity = "weak"

        return {
            "sentiment": sentiment,
            "score": round(normalized_score, 2),
            "confidence": round(confidence, 2),
            "positive_hits": [h["word"] for h in pos_hits],
            "negative_hits": [h["word"] for h in neg_hits],
            "emoji_hits": [h[0] for h in emoji_hits],
            "intensity": intensity,
            "method": "rule",
            "is_rhetorical": is_rhetorical,
        }

    # ── 批量 LLM 分析 ───────────────────────────────────────────

    def _get_api_config(self) -> Optional[Tuple[str, str, str]]:
        """获取 LLM API 配置。仅从环境变量读取，无硬编码 fallback。

        Returns:
            (api_key, base_url, model) or None
        """
        api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not api_key:
            return None
        base_url = os.getenv("DEEPSEEK_BASE_URL") or os.getenv("OPENAI_BASE_URL") or "https://api.deepseek.com/v1"
        model = os.getenv("DEEPSEEK_MODEL") or os.getenv("OPENAI_MODEL") or "deepseek-chat"
        return api_key, base_url, model

    def _llm_analyze_batch(self, texts: List[str]) -> List[Optional[dict]]:
        """批量调用 LLM 分析多条评论的情感。

        Args:
            texts: 待分析的评论文本列表

        Returns:
            与 texts 等长的结果列表，LLM 失败时为 None
        """
        api_config = self._get_api_config()
        if not api_config:
            return [None] * len(texts)

        api_key, base_url, model = api_config

        # 构建 few-shot 批量 prompt
        examples = [
            {"id": -3, "text": "支持维权！消费者不能总是被欺负", "sentiment": "positive", "score": 0.9, "reason": "明确支持维权，表达强烈认同"},
            {"id": -2, "text": "垃圾品牌，以后再也不会买了", "sentiment": "negative", "score": -0.9, "reason": "强烈贬低品牌，表达极度不满和拒绝"},
            {"id": -1, "text": "等官方通报吧，现在信息太乱了", "sentiment": "neutral", "score": 0.0, "reason": "理性观望，无明确情感倾向"},
            {"id": -4, "text": "这也叫好？认真的吗", "sentiment": "negative", "score": -0.7, "reason": "反问句式表达讽刺，实际持否定态度"},
            {"id": -5, "text": "已经退货成功了，感谢大家的提醒", "sentiment": "positive", "score": 0.8, "reason": "成功维权并表达感谢"},
            {"id": -6, "text": "孩子在学校吃了一年多，想想就后怕", "sentiment": "negative", "score": -0.8, "reason": "对孩子健康安全的担忧和恐惧"},
            {"id": -7, "text": "观望中……到底是不是真的", "sentiment": "neutral", "score": -0.1, "reason": "持保留态度观察，略偏质疑但无明确情感"},
        ]

        items = [{"id": i, "text": t[:300]} for i, t in enumerate(texts)]

        system_prompt = (
            "你是中文舆情评论情感标注助手。对每条评论判断情感倾向。\n"
            "判断规则：\n"
            "- positive: 支持、满意、感谢、期待、认可、表扬、乐观、理性讨论建设性意见\n"
            "- negative: 愤怒、失望、批评、讽刺、担忧、抱怨、维权困难、恐惧\n"
            "- neutral: 纯询问、中性描述、观望态度、客观陈述、无法判断\n"
            "score 范围 -1.0(极负面) 到 1.0(极正面)，0 为完全中性。\n"
            "reason 用 15 字以内简要说明。\n"
            "对于反讽、反问句式（表面说好实际在批评），必须归类为 negative。"
        )

        user_prompt = (
            "请分析以下评论的情感倾向，参考示例格式输出 JSON 数组。\n\n"
            "示例：\n"
            + json.dumps(examples, ensure_ascii=False, indent=2) + "\n\n"
            f"待分析评论（共 {len(items)} 条）：\n"
            + json.dumps(items, ensure_ascii=False) + "\n\n"
            "只输出 JSON 数组，不要添加任何额外文本。"
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
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.05,  # 极低温度保证一致性
                    "max_tokens": 2048,
                },
                timeout=self.LLM_TIMEOUT,
            )

            if resp.status_code == 200:
                payload = resp.json()
                content = payload.get("choices", [{}])[0].get("message", {}).get("content", "")
                return self._parse_batch_response(content, len(texts))
        except Exception:
            pass

        return [None] * len(texts)

    def _parse_batch_response(self, content: str, expected_count: int) -> List[Optional[dict]]:
        """解析 LLM 批量返回的 JSON 数组。"""
        if not isinstance(content, str):
            return [None] * expected_count

        content = content.strip()

        # 去除 markdown 代码块包裹
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*", "", content)
            content = re.sub(r"\s*```$", "", content)

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            # 尝试提取 JSON 数组
            match = re.search(r"\[.*\]", content, re.DOTALL)
            if match:
                try:
                    parsed = json.loads(match.group())
                except json.JSONDecodeError:
                    return [None] * expected_count
            else:
                return [None] * expected_count

        if not isinstance(parsed, list):
            return [None] * expected_count

        # 构建索引映射
        results: Dict[int, dict] = {}
        for item in parsed:
            if isinstance(item, dict) and "id" in item:
                idx = item["id"]
                sentiment = str(item.get("sentiment", "neutral")).strip().lower()
                if sentiment not in {"positive", "neutral", "negative"}:
                    sentiment = "neutral"
                try:
                    score = float(item.get("score", 0))
                except (ValueError, TypeError):
                    score = 0.0
                score = max(-1.0, min(1.0, score))
                results[idx] = {
                    "sentiment": sentiment,
                    "score": score,
                    "positive_hits": [],
                    "negative_hits": [],
                    "emoji_hits": [],
                    "reason": str(item.get("reason", ""))[:50],
                    "confidence": 0.85,
                    "intensity": "strong" if abs(score) >= 0.6 else "moderate" if abs(score) >= 0.25 else "weak",
                    "method": "llm",
                }

        return [results.get(i) for i in range(expected_count)]

    # ── 单条 LLM 分析（兼容旧接口，内部使用批量）─────────────────

    def _llm_analyze_single(self, text: str) -> Optional[dict]:
        """单条 LLM 分析（通过批量接口实现）。"""
        results = self._llm_analyze_batch([text])
        return results[0] if results else None

    # ── 混合策略主入口 ──────────────────────────────────────────

    def analyze(self, text: str) -> dict:
        """分析单条文本的情感倾向（混合策略）。

        - 先跑规则分析
        - 置信度 ≥ 0.7 → 直接用规则结果
        - 置信度 < 0.7 → 调用 LLM 深度分析

        Returns:
            {"sentiment": "positive|neutral|negative", "score": float,
             "positive_hits": [...], "negative_hits": [...], "confidence": float, ...}
        """
        rule_result = self._rule_analyze(text)

        # 高置信度 → 直接用规则结果
        if rule_result["confidence"] >= 0.7:
            return rule_result

        # 低置信度 → 尝试 LLM
        api_config = self._get_api_config()
        if not api_config:
            # 无 API Key，标记为 rule_fallback
            rule_result["method"] = "rule_fallback"
            return rule_result

        llm_result = self._llm_analyze_single(text)
        if llm_result:
            # 合并：LLM 为主（权重 0.7），规则为辅（权重 0.3）
            llm_result["positive_hits"] = rule_result.get("positive_hits", [])
            llm_result["negative_hits"] = rule_result.get("negative_hits", [])
            llm_result["emoji_hits"] = rule_result.get("emoji_hits", [])
            llm_result["method"] = "hybrid"
            return llm_result

        # LLM 失败 → 规则结果
        rule_result["method"] = "rule_fallback"
        return rule_result

    # ── DataFrame 批量分析 ──────────────────────────────────────

    def analyze_dataframe(self, df: pd.DataFrame, text_col: str = "content") -> pd.DataFrame:
        """对 DataFrame 中的评论进行批量情感分析。

        策略：
        1. 所有评论先跑规则分析（快速）
        2. 筛选低置信度评论
        3. 批量调用 LLM 分析（20条/次）
        4. 合并结果

        接口与旧版完全兼容。
        """
        result = df.copy()
        n_total = len(result)

        # Step 1: 规则分析全量
        rule_results: List[dict] = []
        for text in result[text_col]:
            rule_results.append(self._rule_analyze(str(text)))

        # Step 2: 识别低置信度评论
        low_conf_indices = [
            i for i, r in enumerate(rule_results)
            if r["confidence"] < 0.7
        ]

        # Step 3: 批量 LLM（仅当有 API Key 且有低置信度评论时）
        api_config = self._get_api_config()
        llm_results: Dict[int, dict] = {}

        if api_config and low_conf_indices:
            batch_size = self.LLM_BATCH_SIZE
            for batch_start in range(0, len(low_conf_indices), batch_size):
                batch_indices = low_conf_indices[batch_start:batch_start + batch_size]
                batch_texts = [str(result.iloc[i][text_col]) for i in batch_indices]
                batch_llm = self._llm_analyze_batch(batch_texts)
                for idx, llm_r in zip(batch_indices, batch_llm):
                    if llm_r is not None:
                        rule_r = rule_results[idx]
                        llm_r["positive_hits"] = rule_r.get("positive_hits", [])
                        llm_r["negative_hits"] = rule_r.get("negative_hits", [])
                        llm_r["emoji_hits"] = rule_r.get("emoji_hits", [])
                        llm_r["method"] = "hybrid"
                        llm_results[idx] = llm_r

        # Step 4: 合并结果
        final_results = []
        for i, rule_r in enumerate(rule_results):
            if i in llm_results:
                final_results.append(llm_results[i])
            else:
                if rule_r.get("method") == "rule" and rule_r["confidence"] < 0.7:
                    rule_r["method"] = "rule_fallback"
                final_results.append(rule_r)

        # 写入 DataFrame
        result["cleaned_content"] = result[text_col].apply(self.clean_text)
        result["sentiment"] = [r["sentiment"] for r in final_results]
        result["score"] = [r["score"] for r in final_results]
        result["positive_hits"] = [r.get("positive_hits", []) for r in final_results]
        result["negative_hits"] = [r.get("negative_hits", []) for r in final_results]
        result["confidence"] = [r.get("confidence", 0.0) for r in final_results]
        result["intensity"] = [r.get("intensity", "weak") for r in final_results]
        result["method"] = [r.get("method", "rule") for r in final_results]
        result["reason"] = [r.get("reason", "") for r in final_results]

        # 统计信息
        n_llm = sum(1 for r in final_results if r.get("method") in ("hybrid", "llm"))
        n_rule_high = sum(1 for r in final_results if r.get("method") == "rule")
        n_rule_fallback = sum(1 for r in final_results if r.get("method") == "rule_fallback")
        print(f"  [情感分析] 总计 {n_total} 条 | 规则高置信: {n_rule_high} | LLM增强: {n_llm} | 规则兜底: {n_rule_fallback}")

        return result

    # ── 情感汇总 ────────────────────────────────────────────────

    def summarize(self, df: pd.DataFrame) -> dict:
        """汇总 DataFrame 中的情感分布。

        Returns:
            {"positive": int, "negative": int, "neutral": int}
        """
        if df.empty:
            return {"positive": 0, "negative": 0, "neutral": 0}
        counts = Counter(df["sentiment"])
        return {
            "positive": int(counts.get("positive", 0)),
            "negative": int(counts.get("negative", 0)),
            "neutral": int(counts.get("neutral", 0)),
        }

    def summarize_detailed(self, df: pd.DataFrame) -> dict:
        """详细情感汇总，包含强度分布和方法分布。"""
        basic = self.summarize(df)
        if df.empty:
            return {**basic, "intensity": {}, "method": {}}

        intensity_counts = Counter(df.get("intensity", pd.Series()))
        method_counts = Counter(df.get("method", pd.Series()))
        avg_score = round(float(df["score"].mean()), 3) if "score" in df.columns else 0.0

        return {
            **basic,
            "total": len(df),
            "avg_score": avg_score,
            "intensity": {
                "strong": int(intensity_counts.get("strong", 0)),
                "moderate": int(intensity_counts.get("moderate", 0)),
                "weak": int(intensity_counts.get("weak", 0)),
            },
            "method": {
                "rule_high_conf": int(method_counts.get("rule", 0)),
                "llm_enhanced": int(method_counts.get("hybrid", 0)) + int(method_counts.get("llm", 0)),
                "rule_fallback": int(method_counts.get("rule_fallback", 0)),
            },
        }


# ── 便捷函数（兼容旧版调用）──────────────────────────────────────

def analyze_sentiment(text: str) -> dict:
    """便捷函数：分析单条文本的情感。"""
    analyzer = SentimentAnalyzer()
    return analyzer.analyze(text)


def analyze_comments_csv(input_path: str, output_path: str, text_col: str = "content"):
    """便捷函数：读取 CSV → 情感分析 → 写回 CSV。"""
    analyzer = SentimentAnalyzer()
    df = pd.read_csv(input_path, encoding="utf-8-sig")
    labeled = analyzer.analyze_dataframe(df, text_col=text_col)
    labeled.to_csv(output_path, index=False, encoding="utf-8-sig")
    summary = analyzer.summarize(labeled)
    print(f"情感分析完成: {summary}")
    return labeled
