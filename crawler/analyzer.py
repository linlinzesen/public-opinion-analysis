import json
import re
from collections import Counter
from typing import List, Dict

import pandas as pd

# jieba 为可选依赖，未安装时使用简单分词回退
try:
    import jieba
    _HAS_JIEBA = True
except ImportError:
    _HAS_JIEBA = False
    print("[analyzer] jieba 未安装，将使用简单字符级分词（建议: pip install jieba）")

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np


class CommentAnalyzer:
    """评论分析与统计模块。"""

    def __init__(self):
        self.stop_words = {
            "这个", "这个", "还是", "就是", "没有", "他们", "我们", "你们", "一", "有", "就", "都", "也",
            "在", "和", "或", "了", "的", "是", "不是", "很", "太", "我", "他", "她", "它", "啊", "呢",
        }

    def load_comments(self, path: str) -> pd.DataFrame:
        df = pd.read_csv(path, encoding="utf-8-sig")
        return df

    def preprocess_text(self, text: str) -> List[str]:
        if not isinstance(text, str):
            return []
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"\s+", "", text)
        if _HAS_JIEBA:
            words = [w for w in jieba.cut(text) if len(w) > 1 and w not in self.stop_words]
        else:
            # 简单回退：按字符二元组 + 单字过滤
            words = []
            for i in range(len(text) - 1):
                bigram = text[i:i + 2]
                if bigram not in self.stop_words and not re.search(r"[^一-鿿]", bigram):
                    words.append(bigram)
        return words

    def basic_stats(self, df: pd.DataFrame) -> Dict:
        return {
            "total_comments": int(len(df)),
            "avg_like_count": round(float(df["like_count"].mean()), 2) if "like_count" in df.columns else 0.0,
            "top_like_comments": df.sort_values("like_count", ascending=False)[["content", "like_count"]].head(5).to_dict("records") if "like_count" in df.columns else [],
        }

    def daily_trend(self, df: pd.DataFrame) -> pd.DataFrame:
        if "ctime_str" not in df.columns:
            return pd.DataFrame(columns=["date", "count"])
        df = df.copy()
        df["ctime_str"] = pd.to_datetime(df["ctime_str"], errors="coerce")
        # 过滤掉 NaT（无效时间），避免后续 .astype(str) 产生 "NaT" 字符串
        df = df[df["ctime_str"].notna()].copy()
        if df.empty:
            return pd.DataFrame(columns=["date", "count"])
        df["date"] = df["ctime_str"].dt.date.astype(str)
        return df.groupby("date").size().reset_index(name="count")

    def extract_keywords(self, df: pd.DataFrame, top_k: int = 20) -> List[Dict]:
        texts = []
        for text in df.get("content", []):
            if isinstance(text, str):
                words = self.preprocess_text(text)
                texts.append(" ".join(words))
            else:
                texts.append("")

        vectorizer = TfidfVectorizer(stop_words=list(self.stop_words))
        X = vectorizer.fit_transform(texts)
        scores = X.toarray().sum(axis=0)
        terms = vectorizer.get_feature_names_out()
        ranked = sorted(zip(terms, scores), key=lambda x: x[1], reverse=True)[:top_k]
        return [{"keyword": term, "score": round(float(score), 4)} for term, score in ranked]

    def calculate_heat_index(self, df: pd.DataFrame) -> pd.DataFrame:
        result = df.copy()
        if result.empty:
            result["heat_index"] = []
            return result

        result["like_count"] = pd.to_numeric(result.get("like_count", 0), errors="coerce").fillna(0)
        result["reply_count"] = pd.to_numeric(result.get("reply_count", 0), errors="coerce").fillna(0)
        score_col = result.get("score", pd.Series([0] * len(result)))
        sentiment_score = pd.to_numeric(score_col, errors="coerce").fillna(0)
        result["heat_index"] = (
            result["like_count"] * 0.6 + result["reply_count"] * 0.4 + sentiment_score.abs() * 2
        ).round(2)
        return result

    def daily_stats(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return pd.DataFrame(columns=["date", "comment_count", "positive", "negative", "neutral", "heat_index", "change_rate"])

        result = self.calculate_heat_index(df.copy())
        if "ctime_str" in result.columns:
            result["ctime_str"] = pd.to_datetime(result["ctime_str"], errors="coerce")
            # 过滤掉 NaT（无效时间），避免后续 .astype(str) 产生 "NaT" 字符串
            result = result[result["ctime_str"].notna()].copy()
            if result.empty:
                return pd.DataFrame(columns=["date", "comment_count", "positive", "negative", "neutral", "heat_index", "change_rate"])
            result["date"] = result["ctime_str"].dt.date.astype(str)
        else:
            result["date"] = "unknown"

        summary = result.groupby("date", as_index=False).agg(
            comment_count=("content", "size"),
            positive=("sentiment", lambda s: int((s == "positive").sum())),
            negative=("sentiment", lambda s: int((s == "negative").sum())),
            neutral=("sentiment", lambda s: int((s == "neutral").sum())),
            heat_index=("heat_index", "sum"),
        )

        # 按日期排序
        summary = summary.sort_values("date").reset_index(drop=True)

        # ── 计算变化率（日环比），避免极端值 ──
        counts = summary["comment_count"].values
        change_rates = [0.0]
        for i in range(1, len(counts)):
            prev = counts[i - 1]
            curr = counts[i]
            if prev > 0:
                rate = round((curr - prev) / prev * 100, 1)
                # 单日变化率封顶 300%，超过视为数据异常
                if abs(rate) > 300:
                    rate = 300.0 if rate > 0 else -300.0
                change_rates.append(rate)
            else:
                # 前一天为 0，不计算变化率（避免除零）
                change_rates.append(0.0)
        summary["change_rate"] = change_rates

        return summary[["date", "comment_count", "positive", "negative", "neutral", "heat_index", "change_rate"]]

    def aggregate_events(self, df: pd.DataFrame) -> List[Dict]:
        if df.empty:
            return []

        df = df.copy()
        if "ctime_str" in df.columns:
            df["ctime_str"] = pd.to_datetime(df["ctime_str"], errors="coerce")
            df = df.sort_values("ctime_str")

        events: List[Dict] = []
        grouped = df.groupby("keyword") if "keyword" in df.columns else None
        if grouped is None:
            return []

        for keyword, group in grouped:
            group = group.dropna(subset=["content"]).copy()
            if group.empty:
                continue
            groups = []
            if "sentiment" in group.columns:
                summary = Counter(group["sentiment"])
                platform_counts = Counter(group.get("platform", "unknown"))
                groups.append({
                    "keyword": keyword,
                    "event_title": f"关键词事件: {keyword}",
                    "total_comments": int(len(group)),
                    "positive": int(summary.get("positive", 0)),
                    "negative": int(summary.get("negative", 0)),
                    "neutral": int(summary.get("neutral", 0)),
                    "platform_distribution": dict(platform_counts),
                    "top_keywords": self.extract_keywords(group, top_k=10),
                })
            events.extend(groups)

        return events

    def save_json(self, data: Dict, path: str):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # ── 基于 ML 的事件发现 ───────────────────────────────────

    def discover_events_ml(
        self, df: pd.DataFrame, n_clusters: int = 5, content_key: str = "content"
    ) -> List[Dict]:
        """利用 TF-IDF + KMeans 聚类自动发现舆情事件。

        这是对需求"利用机器学习方法对舆情主题进行分类，识别舆情事件"的实现。
        """
        if df.empty or len(df) < n_clusters * 10:
            return []

        # 文本向量化
        texts = []
        for text in df.get(content_key, []):
            if isinstance(text, str) and text.strip():
                words = self.preprocess_text(text)
                texts.append(" ".join(words))
            else:
                texts.append("")

        if not any(texts):
            return []

        vectorizer = TfidfVectorizer(max_features=500, stop_words=list(self.stop_words))
        try:
            X = vectorizer.fit_transform(texts)
        except ValueError:
            return []

        # KMeans 聚类
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        labels = kmeans.fit_predict(X)

        # 为每个聚类提取关键词和统计信息
        events = []
        feature_names = vectorizer.get_feature_names_out()

        for cluster_id in range(n_clusters):
            mask = labels == cluster_id
            cluster_df = df.loc[mask].copy()
            if cluster_df.empty or len(cluster_df) < 5:
                continue

            # 提取该聚类的代表性关键词
            centroid = kmeans.cluster_centers_[cluster_id]
            top_indices = np.argsort(centroid)[-8:][::-1]
            top_keywords = [{"keyword": str(feature_names[i]), "score": round(float(centroid[i]), 4)} for i in top_indices]

            # 情感统计
            sentiment_counts = Counter(cluster_df.get("sentiment", pd.Series()))
            total = len(cluster_df)

            # 平台分布
            platform_counts = Counter(cluster_df.get("platform", "unknown"))

            # 生成事件标题
            title_keywords = "、".join([kw["keyword"] for kw in top_keywords[:3]])
            event_title = f"聚类事件: {title_keywords}相关舆情"

            events.append({
                "cluster_id": int(cluster_id),
                "event_title": event_title,
                "total_comments": int(total),
                "positive": int(sentiment_counts.get("positive", 0)),
                "negative": int(sentiment_counts.get("negative", 0)),
                "neutral": int(sentiment_counts.get("neutral", 0)),
                "platform_distribution": dict(platform_counts),
                "top_keywords": top_keywords,
                "cluster_size_ratio": round(total / len(df), 3),
            })

        # 按评论量排序
        events.sort(key=lambda e: e["total_comments"], reverse=True)
        return events

    # ── 相似事件检索 ─────────────────────────────────────────

    def find_similar_events(
        self, query_text: str, event_descriptions: List[Dict], top_k: int = 5
    ) -> List[Dict]:
        """基于 TF-IDF 余弦相似度检索相似事件。

        这是对需求"支持对历史事件和相似事件的检索"的实现。
        """
        if not event_descriptions or not query_text:
            return []

        query_words = self.preprocess_text(query_text)
        query_str = " ".join(query_words)
        if not query_str:
            return []

        # 构建事件描述文本
        event_texts = []
        for evt in event_descriptions:
            title = evt.get("event_title", "")
            keywords = evt.get("top_keywords", [])
            kw_text = " ".join([kw.get("keyword", "") for kw in keywords])
            event_texts.append(f"{title} {kw_text}")

        all_texts = [query_str] + event_texts
        vectorizer = TfidfVectorizer(stop_words=list(self.stop_words))
        try:
            X = vectorizer.fit_transform(all_texts)
        except ValueError:
            return []

        # 计算相似度
        sim_matrix = cosine_similarity(X[0:1], X[1:])
        similarities = sim_matrix[0]

        # 排序返回
        ranked = sorted(
            enumerate(similarities),
            key=lambda x: x[1],
            reverse=True,
        )[:top_k]

        results = []
        for idx, sim in ranked:
            if sim > 0.05:  # 过滤极低相似度
                evt = event_descriptions[idx].copy()
                evt["similarity_score"] = round(float(sim), 4)
                results.append(evt)

        return results

    # ── 增强版事件聚合 ───────────────────────────────────────

    def aggregate_events_enhanced(
        self, df: pd.DataFrame, similarity_threshold: float = 0.3
    ) -> List[Dict]:
        """增强版事件聚合：先按关键词分组，再合并相似事件。

        相比原始 aggregate_events，增加了跨关键词的相似度合并。
        """
        base_events = self.aggregate_events(df)
        if len(base_events) <= 1:
            return base_events

        # 检查事件间的相似度，合并高度相似的事件
        merged: List[Dict] = []
        used: set = set()

        for i, evt_i in enumerate(base_events):
            if i in used:
                continue
            merged_event = evt_i.copy()
            used.add(i)

            for j, evt_j in enumerate(base_events):
                if j in used or j <= i:
                    continue

                # 计算 keyword 重叠度
                kw_i = {kw.get("keyword", "") for kw in evt_i.get("top_keywords", [])}
                kw_j = {kw.get("keyword", "") for kw in evt_j.get("top_keywords", [])}
                if not kw_i or not kw_j:
                    continue

                overlap = len(kw_i & kw_j) / min(len(kw_i), len(kw_j))
                if overlap > similarity_threshold:
                    used.add(j)
                    # 合并
                    merged_event["total_comments"] += evt_j.get("total_comments", 0)
                    merged_event["positive"] += evt_j.get("positive", 0)
                    merged_event["negative"] += evt_j.get("negative", 0)
                    merged_event["neutral"] += evt_j.get("neutral", 0)
                    merged_event["event_title"] = f"{merged_event['event_title']} / {evt_j.get('event_title', '')}"

            merged.append(merged_event)

        return merged
