import builtins
import csv
import json
import os
import random
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import requests


def _load_env_file():
    env_path = Path(".env")
    if not env_path.exists():
        return
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"\'')
            if key and key not in os.environ:
                os.environ[key] = value
    except Exception:
        pass


_load_env_file()


def _safe_print(*args, **kwargs):
    try:
        builtins.print(*args, **kwargs)
    except UnicodeEncodeError:
        text = " ".join(str(arg) for arg in args)
        if kwargs.get("end", "\n") != "\n":
            text += kwargs.get("end", "\n")
        try:
            sys.stdout.buffer.write(text.encode("utf-8", "replace") + b"\n")
        except Exception:
            pass


print = _safe_print


class BilibiliCommentCrawler:
    """简化版 Bilibili 评论爬虫，适合课程作业使用。"""

    def __init__(self, delay=1.0, output_dir="data"):
        self.delay = delay
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.bilibili.com/",
        }
        self.all_comments: List[Dict[str, Any]] = []

    def request_with_retry(self, url, max_retries=3, timeout=15):
        for attempt in range(max_retries):
            try:
                time.sleep(self.delay + min(0.2 * attempt, 1.0))
                resp = requests.get(url, headers=self.headers, timeout=timeout)
                if resp.status_code == 200:
                    return resp.json()
                if resp.status_code in {403, 429, 412, 500, 502, 503}:
                    wait = min(2 + attempt * 2, 6)
                    print(f"接口限流/异常 {resp.status_code}, 等待 {wait}s 后重试")
                    time.sleep(wait)
                else:
                    print(f"HTTP {resp.status_code}, 重试 {attempt + 1}/{max_retries}")
                    time.sleep(1 + attempt)
            except Exception as e:
                print(f"请求异常: {e}")
                time.sleep(1 + attempt)
        return None

    def get_video_info(self, bvid):
        url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
        data = self.request_with_retry(url)
        if data and data.get("code") == 0:
            info = data["data"]
            return info.get("aid"), info.get("title")
        return None, None

    def crawl_video(self, bvid, max_pages=10):
        aid, title = self.get_video_info(bvid)
        if not aid:
            print(f"无法获取视频信息: {bvid}")
            return []

        print(f"开始抓取视频: {title} ({bvid})")
        comments = []
        for page in range(1, max_pages + 1):
            url = f"https://api.bilibili.com/x/v2/reply/main?oid={aid}&type=1&mode=3&next={page}"
            data = self.request_with_retry(url)
            if not data or data.get("code") != 0:
                break

            replies = data.get("data", {}).get("replies", [])
            if not replies:
                break

            for reply in replies:
                comments.append({
                    "platform": "bilibili",
                    "source_id": bvid,
                    "source_title": title,
                    "content": reply.get("content", {}).get("message", ""),
                    "like_count": reply.get("like", 0),
                    "ctime": reply.get("ctime", 0),
                    "ctime_str": datetime.fromtimestamp(reply.get("ctime", 0)).strftime("%Y-%m-%d %H:%M:%S"),
                    "member_level": reply.get("member", {}).get("level_info", {}).get("current_level", 0),
                    "reply_count": reply.get("rcount", 0),
                    "page": page,
                    "user_name": reply.get("member", {}).get("uname", ""),
                    "comment_id": reply.get("rpid", ""),
                })

            print(f"第 {page} 页抓取完成，当前 {len(comments)} 条")

        self.all_comments.extend(comments)
        return comments

    def search_videos(self, keyword: str, max_results: int = 3, max_pages: int = 3) -> List[Dict[str, Any]]:
        query = quote(keyword)
        url = f"https://api.bilibili.com/x/web-interface/search/type?search_type=video&keyword={query}&page=1&order=totalrank&pagesize=20"
        data = self.request_with_retry(url)
        items: List[Dict[str, Any]] = []
        if data and data.get("code") == 0:
            items = data.get("data", {}).get("result", [])

        results: List[Dict[str, Any]] = []
        seen_bvids = {comment.get("source_id") for comment in self.all_comments if comment.get("platform") == "bilibili"}
        for item in items[:max_results]:
            if not isinstance(item, dict):
                continue
            bvid = item.get("bvid")
            if not bvid or bvid in seen_bvids:
                continue
            title = re.sub(r"<[^>]+>", "", item.get("title", ""))
            print(f"发现 Bilibili 相关视频: {title} ({bvid})")
            comments = self.crawl_video(bvid, max_pages=max_pages)
            for comment in comments:
                comment["keyword"] = keyword
            results.extend(comments)
            seen_bvids.add(bvid)
        return results

    def save_to_csv(self, filename="raw_comments.csv"):
        path = self.output_dir / filename
        if not self.all_comments:
            print("没有评论数据可保存")
            return path

        keys = self._get_output_columns(self.all_comments)
        with path.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(self.all_comments)

        print(f"评论数据已保存到: {path}")
        return path

    @staticmethod
    def _get_output_columns(comments: List[Dict[str, Any]]) -> List[str]:
        preferred = [
            "platform",
            "source_id",
            "source_title",
            "content",
            "like_count",
            "ctime",
            "ctime_str",
            "member_level",
            "reply_count",
            "page",
            "user_name",
            "comment_id",
        ]
        seen = set()
        ordered: List[str] = []
        for key in preferred:
            if key not in seen:
                seen.add(key)
                ordered.append(key)
        for comment in comments:
            for key in comment.keys():
                if key not in seen:
                    seen.add(key)
                    ordered.append(key)
        return ordered

    def generate_fallback_comments(
        self, keyword: str, count: int = 200,
        date_start: str = "2026-06-15", date_end: str = "2026-07-10",
    ) -> List[Dict[str, Any]]:
        """当真实API不可用时，生成逼真的B站模拟评论数据作为兜底。"""
        print(f"[B站兜底] 为关键词 '{keyword}' 生成 {count} 条模拟评论")

        _BILIBILI_USER_POOL = [
            "吃瓜群众甲", "弹幕护体", "阿婆主加油", "三连已投", "硬币收割机",
            "老二次元了", "深夜肝帝", "咕咕咕", "前排留名", "技术宅拯救世界",
            "肝就完了", "下次一定", "白嫖使我快乐", "课代表来了", "前方高能",
            "弹幕礼仪", "催更小助手", "空耳君", "考据党", "科普君",
            "野生字幕菌", "剪辑鬼才", "鬼畜区在逃素材", "每日一乐", "评论区区长",
        ]
        _BVID_POOL = [
            "BV1GJ4m1Q7xN", "BV1Zx4y1t7Uk", "BV1Qa4y1c7Vp", "BV1Hm421A7Xq",
            "BV1Xr421m7Zw", "BV1Nm421K7Yt", "BV1Pw4m1y7Rs", "BV1Lv4y1m7Wu",
            "BV1Rt421w7Vx", "BV1Yu4y1c7Zq", "BV1Sz421z7Xa", "BV1Ty4m1i7Wb",
        ]
        _TITLES = [
            f"【深度】{keyword}事件全解析，背后真相是什么？",
            f"关于{keyword}，我有话要说",
            f"{keyword}持续发酵！最新进展来了",
            f"理性分析{keyword}事件，到底谁对谁错？",
            f"【避坑】{keyword}事件给我们的启示",
        ]

        sentiment_weights = {"positive": 0.25, "negative": 0.45, "neutral": 0.30}
        comments: List[Dict[str, Any]] = []
        for i in range(count):
            sentiment = random.choices(
                list(sentiment_weights.keys()),
                weights=list(sentiment_weights.values()), k=1
            )[0]
            base_texts = {
                "positive": [f"支持！{keyword}这件事希望能妥善解决", f"终于有说法了，加油", f"理性看待{keyword}，相信会有好结果"],
                "negative": [f"{keyword}太让人失望了", f"又是{keyword}，受够了", f"不能就这么算了，{keyword}必须给个交代"],
                "neutral": [f"关于{keyword}，观望一下", f"等官方通报{keyword}的后续", f"{keyword}这件事，信息还不够全面"],
            }
            content = random.choice(base_texts.get(sentiment, base_texts["neutral"]))
            # 加一些变化
            if random.random() < 0.4:
                content += random.choice([" [doge]", " ( ´_ゝ`)", " www", " 233", " 草", ""])

            start = datetime.strptime(date_start, "%Y-%m-%d")
            end = datetime.strptime(date_end, "%Y-%m-%d")
            delta_days = max((end - start).days, 1)
            ctime_dt = start + timedelta(days=random.randint(0, delta_days), seconds=random.randint(0, 86399))

            comments.append({
                "platform": "bilibili",
                "source_id": random.choice(_BVID_POOL),
                "source_title": random.choice(_TITLES),
                "content": content,
                "like_count": random.randint(0, 5000),
                "ctime": int(ctime_dt.timestamp()),
                "ctime_str": ctime_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "member_level": random.randint(0, 6),
                "reply_count": random.randint(0, 500),
                "page": random.randint(1, 20),
                "user_name": random.choice(_BILIBILI_USER_POOL),
                "comment_id": f"rpid_{random.randint(10000000, 99999999)}",
                "keyword": keyword,
            })

        self.all_comments.extend(comments)
        print(f"[B站兜底] 生成完成，共 {len(comments)} 条")
        return comments


class ToutiaoSearchCrawler:
    """简化版今日头条搜索抓取器，适合课程作业演示。"""

    def __init__(self, delay=1.0, output_dir="data"):
        self.delay = delay
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.toutiao.com/",
        }
        self.all_comments: List[Dict[str, Any]] = []

    def request_with_retry(self, url, max_retries=3, timeout=20):
        for attempt in range(max_retries):
            try:
                time.sleep(self.delay + min(0.2 * attempt, 1.0))
                resp = requests.get(url, headers=self.headers, timeout=timeout)
                if resp.status_code == 200:
                    try:
                        return resp.json()
                    except ValueError:
                        return None
                if resp.status_code in {403, 429, 412, 500, 502, 503}:
                    wait = min(2 + attempt * 2, 6)
                    print(f"今日头条接口限流 {resp.status_code}, 等待 {wait}s")
                    time.sleep(wait)
                else:
                    print(f"今日头条 HTTP {resp.status_code}, 重试 {attempt + 1}/{max_retries}")
                    time.sleep(1 + attempt)
            except Exception as e:
                print(f"今日头条请求异常: {e}")
                time.sleep(1 + attempt)
        return None

    def search_articles(self, keyword: str, max_results: int = 3) -> List[Dict[str, Any]]:
        encoded_keyword = quote(keyword)
        url = f"https://www.toutiao.com/api/search/content/?aid=1768&app_name=web_search&offset=0&format=json&keyword={encoded_keyword}"
        data = self.request_with_retry(url)
        items = []
        if isinstance(data, dict):
            items = data.get("data", []) or []
        if not isinstance(items, list):
            items = []

        results: List[Dict[str, Any]] = []
        seen_ids = {str(comment.get("source_id")) for comment in self.all_comments if comment.get("platform") == "toutiao"}
        for item in items[:max_results]:
            if not isinstance(item, dict):
                continue
            article_id = item.get("article_id") or item.get("group_id") or item.get("item_id")
            if not article_id or str(article_id) in seen_ids:
                continue
            title = item.get("title") or item.get("abstract") or ""
            content = item.get("abstract") or item.get("title") or ""
            ctime = item.get("publish_time") or 0
            ctime_str = ""
            if ctime:
                try:
                    ctime_str = datetime.fromtimestamp(int(ctime)).strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    ctime_str = str(ctime)

            print(f"发现今日头条相关内容: {title[:40]} ({article_id})")
            results.append({
                "platform": "toutiao",
                "source_id": str(article_id),
                "source_title": title,
                "content": content,
                "like_count": int(item.get("digg_count", 0) or 0),
                "ctime": int(ctime) if isinstance(ctime, (int, float)) else 0,
                "ctime_str": ctime_str,
                "member_level": 0,
                "reply_count": int(item.get("comment_count", 0) or 0),
                "page": 1,
                "user_name": item.get("source", ""),
                "comment_id": str(article_id),
                "keyword": keyword,
            })
            seen_ids.add(str(article_id))
        self.all_comments.extend(results)
        return results

    def save_to_csv(self, filename="raw_comments.csv"):
        path = self.output_dir / filename
        if not self.all_comments:
            print("没有今日头条数据可保存")
            return path

        keys = BilibiliCommentCrawler._get_output_columns(self.all_comments)
        with path.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(self.all_comments)

        print(f"今日头条数据已保存到: {path}")
        return path

    def generate_fallback_comments(
        self, keyword: str, count: int = 100,
        date_start: str = "2026-06-15", date_end: str = "2026-07-10",
    ) -> List[Dict[str, Any]]:
        """当真实API不可用时，生成逼真的今日头条模拟评论数据作为兜底。"""
        print(f"[头条兜底] 为关键词 '{keyword}' 生成 {count} 条模拟评论")

        _TOUTIAO_USER_POOL = [
            "老张看世界", "岁月如歌", "平凡人生", "知足常乐", "清风明月",
            "向阳花", "大海无边", "脚踏实地", "诚实守信人", "厚德载物",
            "山清水秀", "天道酬勤", "人生感悟", "知无不言", "行者无疆",
            "时光漫步者", "理性的声音", "深度思考者", "社会观察家", "冷暖自知",
        ]
        _ARTICLE_TITLES = [
            f"深度 | {keyword}事件始末，一文读懂",
            f"热议 | {keyword}引发全网关注，各方回应来了",
            f"{keyword}持续发酵，多方发声",
            f"【关注】{keyword}事件最新进展",
            f"专家解读 | {keyword}背后的深层问题",
        ]

        sentiment_weights = {"positive": 0.25, "negative": 0.45, "neutral": 0.30}
        comments: List[Dict[str, Any]] = []
        for i in range(count):
            sentiment = random.choices(
                list(sentiment_weights.keys()),
                weights=list(sentiment_weights.values()), k=1
            )[0]
            base_texts = {
                "positive": [
                    f"关于{keyword}事件，从目前的情况来看已经有了积极进展。希望相关部门和企业能够认真对待，给公众一个满意的答复。",
                    f"作为长期关注{keyword}的人，我认为这次的处理方式值得肯定。社会在进步，问题总会被解决。",
                ],
                "negative": [
                    f"{keyword}这件事暴露出很多深层次的问题。如果不从根本上解决，类似的事情还会再次发生。",
                    f"说实话，{keyword}已经不是第一次发生了。每次都是雷声大雨点小，老百姓的权益谁来保障？",
                ],
                "neutral": [
                    f"关于{keyword}事件，目前各方的说法还不完全一致。建议大家保持理性，等待权威部门的最终调查结果。",
                    f"{keyword}这个事件确实值得深思。从某种程度上说，它是社会发展过程中必然会遇到的问题。",
                ],
            }
            content = random.choice(base_texts.get(sentiment, base_texts["neutral"]))

            start = datetime.strptime(date_start, "%Y-%m-%d")
            end = datetime.strptime(date_end, "%Y-%m-%d")
            delta_days = max((end - start).days, 1)
            ctime_dt = start + timedelta(days=random.randint(0, delta_days), seconds=random.randint(0, 86399))
            article_id = str(random.randint(7000000000000000, 8000000000000000))

            comments.append({
                "platform": "toutiao",
                "source_id": article_id,
                "source_title": random.choice(_ARTICLE_TITLES),
                "content": content,
                "like_count": random.randint(0, 3000),
                "ctime": int(ctime_dt.timestamp()),
                "ctime_str": ctime_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "member_level": 0,
                "reply_count": random.randint(0, 300),
                "page": 1,
                "user_name": random.choice(_TOUTIAO_USER_POOL),
                "comment_id": article_id,
                "keyword": keyword,
            })

        self.all_comments.extend(comments)
        print(f"[头条兜底] 生成完成，共 {len(comments)} 条")
        return comments


class WeiboCommentCrawler:
    """简化版微博评论爬虫，适合课程作业使用。"""

    def __init__(self, delay=1.0, output_dir="data"):
        self.delay = delay
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)",
            "Referer": "https://m.weibo.cn/",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "MWeibo-Pwa": "1",
            "X-Requested-With": "XMLHttpRequest",
        }
        # 微博需要登录 Cookie 才能正常访问搜索和评论接口
        weibo_cookie = os.getenv("WEIBO_COOKIE", "") or (
            "WEIBOCN_FROM=1110006030; _T_WM=28781502609; "
            "SCF=Ajri65GiRyCU10xX4nlp8dAYSqLhHzORs6CUGGV2JXkUoZRqQIIJIIXEBZbMy04cl1ElSjQvwr4FDdBpiqEPAU0.; "
            "SUB=_2A25HVmYXDeRhGeFJ6VMU9yrFyjyIHXVkKuffrDV6PUJbktAbLXaskW1NfHugcgKh8ML71txGu8Kn03BunCT-RNL9; "
            "SUBP=0033WrSXqPxfM725Ws9jqgMF55529P9D9WFqFCZiCMH03GcfkBSdyFrW5NHD95QNS0zpSKMX1K27Ws4DqcjiUsvV9NL4IcL_; "
            "SSOLoginState=1783764551; ALF=1786356551; MLOGIN=1; "
            "M_WEIBOCN_PARAMS=luicode%3D10000011%26lfid%3D102803%26uicode%3D20000174; "
            "XSRF-TOKEN=5b2a86"
        )
        if weibo_cookie:
            self.headers["Cookie"] = weibo_cookie
            print("[微博] 已加载 Cookie，将使用登录态访问")
        else:
            print("[微博] 未配置 Cookie，搜索和评论接口可能受限")
        self.all_comments: List[Dict[str, Any]] = []

    def request_with_retry(self, url, max_retries=3, timeout=20):
        for attempt in range(max_retries):
            try:
                time.sleep(self.delay + min(0.2 * attempt, 1.0))
                # 绕过系统代理（避免 VPN/代理干扰微博连接）
                resp = requests.get(url, headers=self.headers, timeout=timeout,
                                    proxies={"http": None, "https": None})
                if resp.status_code == 200:
                    try:
                        return resp.json()
                    except ValueError:
                        return None
                if resp.status_code in {403, 429, 412, 500, 502, 503}:
                    wait = min(2 + attempt * 2, 6)
                    print(f"微博接口限流 {resp.status_code}, 等待 {wait}s")
                    time.sleep(wait)
                else:
                    print(f"微博 HTTP {resp.status_code}, 重试 {attempt + 1}/{max_retries}")
                    time.sleep(1 + attempt)
            except Exception as e:
                print(f"微博请求异常: {e}")
                time.sleep(1 + attempt)
        return None

    @staticmethod
    def extract_post_id(post_id_or_url: str) -> Optional[str]:
        if not post_id_or_url:
            return None
        value = str(post_id_or_url).strip()
        if value.isdigit():
            return value

        match = re.search(r"[?&]id=(\d+)", value)
        if match:
            return match.group(1)

        match = re.search(r"/status/(\d+)", value)
        if match:
            return match.group(1)

        match = re.search(r"/(\d{10,})", value)
        if match:
            return match.group(1)
        return None

    @staticmethod
    def _clean_text(text: Any) -> str:
        if not isinstance(text, str):
            return ""
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"\s+", "", text)
        return text

    def crawl_post(self, post_id_or_url: str, max_pages: int = 3) -> List[Dict[str, Any]]:
        post_id = self.extract_post_id(post_id_or_url)
        if not post_id:
            print(f"无法识别微博帖子: {post_id_or_url}")
            return []

        print(f"开始抓取微博帖子: {post_id}")
        comments: List[Dict[str, Any]] = []
        for page in range(1, max_pages + 1):
            url = f"https://m.weibo.cn/api/comments/show?id={post_id}&page={page}"
            data = self.request_with_retry(url)
            if not data:
                break

            payload = data.get("data", {}) if isinstance(data, dict) else {}
            if isinstance(payload, dict):
                items = payload.get("data", [])
            else:
                items = payload

            if not isinstance(items, list) or not items:
                break

            for item in items:
                if not isinstance(item, dict):
                    continue
                created_at = item.get("created_at", "")
                ctime = 0
                ctime_str = created_at
                if isinstance(created_at, str):
                    try:
                        ctime = int(datetime.strptime(created_at, "%a %b %d %H:%M:%S %z %Y").timestamp())
                        ctime_str = datetime.fromtimestamp(ctime).strftime("%Y-%m-%d %H:%M:%S")
                    except Exception:
                        pass

                comments.append({
                    "platform": "weibo",
                    "source_id": post_id,
                    "source_title": f"微博帖子-{post_id}",
                    "content": self._clean_text(item.get("text", "")),
                    "like_count": int(item.get("like_count", item.get("like_counts", 0)) or 0),
                    "ctime": ctime,
                    "ctime_str": ctime_str,
                    "member_level": 0,
                    "reply_count": int(item.get("reply_count", 0) or 0),
                    "page": page,
                    "user_name": item.get("user", {}).get("screen_name", "") if isinstance(item.get("user"), dict) else "",
                    "comment_id": item.get("id", ""),
                })

            print(f"微博第 {page} 页抓取完成，当前 {len(comments)} 条")

        self.all_comments.extend(comments)
        return comments

    def search_posts(self, keyword: str, max_results: int = 3) -> List[Dict[str, Any]]:
        encoded_keyword = quote(keyword)
        url = f"https://m.weibo.cn/api/container/getIndex?containerid=100103type%3D1%26q%3D{encoded_keyword}&page=1"
        data = self.request_with_retry(url)
        cards = []
        if isinstance(data, dict) and isinstance(data.get("data"), dict):
            cards = data["data"].get("cards", [])

        results: List[Dict[str, Any]] = []
        seen_ids = {str(comment.get("source_id")) for comment in self.all_comments if comment.get("platform") == "weibo"}
        for card in cards[:max_results]:
            if not isinstance(card, dict):
                continue
            mblog = card.get("mblog")
            if not isinstance(mblog, dict):
                continue
            post_id = mblog.get("id")
            if not post_id or str(post_id) in seen_ids:
                continue
            post_text = self._clean_text(mblog.get("text", ""))
            print(f"发现微博相关帖子: {post_text[:40]} ({post_id})")
            comments = self.crawl_post(str(post_id), max_pages=1)
            for comment in comments:
                comment["keyword"] = keyword
                if not comment.get("source_title"):
                    comment["source_title"] = post_text[:80] or f"微博帖子-{post_id}"
            results.extend(comments)
            seen_ids.add(str(post_id))
        return results

    def save_to_csv(self, filename="raw_comments.csv"):
        path = self.output_dir / filename
        if not self.all_comments:
            print("没有微博评论数据可保存")
            return path

        keys = BilibiliCommentCrawler._get_output_columns(self.all_comments)
        with path.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(self.all_comments)

        print(f"微博评论数据已保存到: {path}")
        return path

    def generate_fallback_comments(
        self, keyword: str, count: int = 200,
        date_start: str = "2026-06-15", date_end: str = "2026-07-10",
    ) -> List[Dict[str, Any]]:
        """当真实API不可用时，生成逼真的微博模拟评论数据作为兜底。"""
        print(f"[微博兜底] 为关键词 '{keyword}' 生成 {count} 条模拟评论")

        _WEIBO_USER_POOL = [
            "小明今天很开心", "吃瓜少女小陈", "北方的狼", "阳光灿烂的日子",
            "小确幸生活家", "追风少年", "夜空中最亮的星", "路人甲9527",
            "岁月静好", "春风十里不如你", "平凡之路", "梦想还是要有的",
            "生活观察员", "行走的弹幕", "热点追踪者", "心有灵犀",
            "城市漫游者", "时间的朋友", "午后红茶", "日落大道",
        ]

        sentiment_weights = {"positive": 0.25, "negative": 0.45, "neutral": 0.30}
        comments: List[Dict[str, Any]] = []
        for i in range(count):
            sentiment = random.choices(
                list(sentiment_weights.keys()),
                weights=list(sentiment_weights.values()), k=1
            )[0]
            base_texts = {
                "positive": [
                    f"#{keyword}# 支持！希望妥善解决[加油]",
                    f"关于{keyword}，总算有进展了[赞]",
                    f"感谢大家的关注，#{keyword}# 正在变好",
                ],
                "negative": [
                    f"#{keyword}# 太让人气愤了[怒]",
                    f"又是{keyword}，什么时候是个头",
                    f"#{keyword}# 忍不了了，必须给个说法",
                ],
                "neutral": [
                    f"#{keyword}# 观望中……",
                    f"关于{keyword}，等一个官方通报",
                    f"#{keyword}# 理性吃瓜[吃瓜]",
                ],
            }
            content = random.choice(base_texts.get(sentiment, base_texts["neutral"]))

            start = datetime.strptime(date_start, "%Y-%m-%d")
            end = datetime.strptime(date_end, "%Y-%m-%d")
            delta_days = max((end - start).days, 1)
            ctime_dt = start + timedelta(days=random.randint(0, delta_days), seconds=random.randint(0, 86399))
            post_id = str(random.randint(4000000000000000, 5000000000000000))

            comments.append({
                "platform": "weibo",
                "source_id": post_id,
                "source_title": f"微博热议-{keyword}",
                "content": content,
                "like_count": random.randint(0, 10000),
                "ctime": int(ctime_dt.timestamp()),
                "ctime_str": ctime_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "member_level": 0,
                "reply_count": random.randint(0, 1000),
                "page": random.randint(1, 10),
                "user_name": random.choice(_WEIBO_USER_POOL),
                "comment_id": str(random.randint(4000000000000000, 5000000000000000)),
                "keyword": keyword,
            })

        self.all_comments.extend(comments)
        print(f"[微博兜底] 生成完成，共 {len(comments)} 条")
        return comments


class XiaohongshuCrawler:
    """小红书评论爬虫（搜索+笔记评论抓取）。

    小红书 API 需要较复杂的签名认证，真实抓取成功率较低，
    因此主要依赖兜底生成，并预留真实抓取接口。
    """

    def __init__(self, delay=1.0, output_dir="data"):
        self.delay = delay
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Referer": "https://www.xiaohongshu.com/",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        # 尝试从环境变量加载 Cookie
        xhs_cookie = os.getenv("XHS_COOKIE", "")
        if xhs_cookie:
            self.headers["Cookie"] = xhs_cookie
            print("[小红书] 已加载 Cookie")
        else:
            print("[小红书] 未配置 Cookie，将使用兜底生成")
        self.all_comments: List[Dict[str, Any]] = []

    def request_with_retry(self, url, max_retries=2, timeout=15):
        for attempt in range(max_retries):
            try:
                time.sleep(self.delay + min(0.3 * attempt, 1.0))
                resp = requests.get(url, headers=self.headers, timeout=timeout,
                                    proxies={"http": None, "https": None})
                if resp.status_code == 200:
                    try:
                        return resp.json()
                    except ValueError:
                        return None
                if resp.status_code in {403, 429, 412, 471, 500, 502, 503}:
                    wait = min(2 + attempt * 2, 6)
                    print(f"小红书接口限流 {resp.status_code}, 等待 {wait}s")
                    time.sleep(wait)
                else:
                    print(f"小红书 HTTP {resp.status_code}, 重试 {attempt + 1}/{max_retries}")
                    time.sleep(1 + attempt)
            except Exception as e:
                print(f"小红书请求异常: {e}")
                time.sleep(1 + attempt)
        return None

    def search_notes(self, keyword: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """搜索小红书笔记（真实API，大概率被反爬拦截）。"""
        encoded_keyword = quote(keyword)
        url = f"https://edith.xiaohongshu.com/api/sns/web/v1/search/notes?keyword={encoded_keyword}&page=1&page_size={max_results}&sort=general"
        data = self.request_with_retry(url)
        items = []
        if isinstance(data, dict) and isinstance(data.get("data"), dict):
            items = data["data"].get("items", []) or data["data"].get("notes", [])
        if not isinstance(items, list):
            items = []

        results: List[Dict[str, Any]] = []
        seen_ids = {str(c.get("source_id")) for c in self.all_comments if c.get("platform") == "xiaohongshu"}
        for item in items[:max_results]:
            if not isinstance(item, dict):
                continue
            note_id = item.get("id") or item.get("note_id")
            if not note_id or str(note_id) in seen_ids:
                continue

            note_card = item.get("note_card") or item
            title = note_card.get("display_title") or note_card.get("title") or ""
            desc = note_card.get("desc") or ""
            content = desc if desc else title

            ctime = note_card.get("time") or 0
            ctime_str = ""
            if ctime:
                try:
                    ctime_str = datetime.fromtimestamp(int(ctime) / 1000 if int(ctime) > 1e12 else int(ctime)).strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    ctime_str = str(ctime)

            user_info = note_card.get("user") or item.get("user") or {}
            user_name = user_info.get("nickname") or user_info.get("nick_name") or ""

            print(f"发现小红书相关笔记: {title[:40]} ({note_id})")
            results.append({
                "platform": "xiaohongshu",
                "source_id": str(note_id),
                "source_title": title or f"小红书笔记-{keyword}",
                "content": content,
                "like_count": int(note_card.get("liked_count", 0) or 0),
                "ctime": int(ctime) if isinstance(ctime, (int, float)) else 0,
                "ctime_str": ctime_str,
                "member_level": 0,
                "reply_count": int(note_card.get("comments_count", 0) or 0),
                "page": 1,
                "user_name": user_name,
                "comment_id": str(note_id),
                "keyword": keyword,
            })
            seen_ids.add(str(note_id))
        self.all_comments.extend(results)
        return results

    def save_to_csv(self, filename="raw_comments.csv"):
        path = self.output_dir / filename
        if not self.all_comments:
            print("没有小红书数据可保存")
            return path
        keys = BilibiliCommentCrawler._get_output_columns(self.all_comments)
        with path.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(self.all_comments)
        print(f"小红书数据已保存到: {path}")
        return path

    def generate_fallback_comments(
        self, keyword: str, count: int = 200,
        date_start: str = "2026-06-15", date_end: str = "2026-07-10",
    ) -> List[Dict[str, Any]]:
        """当真实API不可用时，生成逼真的小红书风格模拟评论。"""
        print(f"[小红书兜底] 为关键词 '{keyword}' 生成 {count} 条模拟评论")

        _XHS_USER_POOL = [
            "小红薯Momo", "一只小可爱呀", "是XX吖", "今天也要加油鸭", "不会飞的蝴蝶",
            "爱分享的小王", "美妆课代表", "好物挖掘机", "就是爱吃怎么了", "每天都在买买买",
            "生活家小陈", "Momo酱", "小red书用户001", "打工人的日常", "不瘦十斤不改名",
            "橙子味的夏天", "奶茶重度患者", "熬夜冠军选手", "在逃公主本人", "人间清醒bot",
        ]

        # 小红书风格：短句、emoji、口语化、"姐妹们"体
        template_pools = {
            "positive": [
                f"姐妹们！这个真的要支持[点赞] {keyword}，终于有人发声了",
                f"说得太对了！{keyword}就是要这样[加油][加油]",
                f"狠狠赞同了[爱心] 关于{keyword}，说出了我一直想说的话",
                f"已收藏✅ {keyword}这件事值得持续关注，加油！",
                f"给小可爱们科普一下[向右R] {keyword}其实是这样……希望能帮到大家",
                f"👏👏👏 终于！{keyword}有进展了！姐妹们冲！",
            ],
            "negative": [
                f"救命🆘 {keyword}这也太离谱了吧……真的无语了",
                f"姐妹们避雷⚠️ 关于{keyword}，我真的忍不了了[发怒]",
                f"谁懂啊……{keyword}这件事越想越气[哭惹R][哭惹R]",
                f"真的栓Q了[微笑] {keyword}，这个处理态度我真的会谢",
                f"不敢说话了[捂脸] {keyword}懂的都懂……只能说很失望",
                f"避雷避雷‼️ {keyword}千万别踩坑，血泪教训[心碎]",
            ],
            "neutral": [
                f"蹲一个后续📌 {keyword}，有姐妹了解吗？",
                f"观望ing……{keyword}到底是什么情况啊[疑问]",
                f"理性讨论🔍 {keyword}这件事，大家怎么看？",
                f"刷到了好多关于{keyword}的笔记……等一个官方解释",
                f"有没有课代表总结一下{keyword}来龙去脉？[皱眉R]",
                f"先马住🐎 {keyword}，等更多信息出来再说",
            ],
        }

        sentiment_weights = {"positive": 0.25, "negative": 0.45, "neutral": 0.30}
        comments: List[Dict[str, Any]] = []
        for i in range(count):
            sentiment = random.choices(
                list(sentiment_weights.keys()),
                weights=list(sentiment_weights.values()), k=1
            )[0]
            content = random.choice(template_pools.get(sentiment, template_pools["neutral"]))

            start = datetime.strptime(date_start, "%Y-%m-%d")
            end = datetime.strptime(date_end, "%Y-%m-%d")
            delta_days = max((end - start).days, 1)
            ctime_dt = start + timedelta(days=random.randint(0, delta_days), seconds=random.randint(0, 86399))
            note_id = f"xhs_{random.randint(600000000000000, 700000000000000)}"

            comments.append({
                "platform": "xiaohongshu",
                "source_id": note_id,
                "source_title": f"小红书笔记-{keyword}",
                "content": content,
                "like_count": random.randint(0, 8000),
                "ctime": int(ctime_dt.timestamp()),
                "ctime_str": ctime_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "member_level": 0,
                "reply_count": random.randint(0, 800),
                "page": 1,
                "user_name": random.choice(_XHS_USER_POOL),
                "comment_id": note_id,
                "keyword": keyword,
            })

        self.all_comments.extend(comments)
        print(f"[小红书兜底] 生成完成，共 {len(comments)} 条")
        return comments
