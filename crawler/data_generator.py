"""
评论数据生成器 - 当真实API爬取不可用时，生成逼真的模拟评论数据。

支持5个舆情事件 × 3个平台 (B站/微博/今日头条) × 每个事件500条评论。
"""

import random
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

# ── 5个近期热点舆情事件（2026年7月） ──────────────────────────────
EVENT_CONFIGS = [
    {
        "keyword": "台风巴威登陆",
        "event_title": "超强台风\"巴威\"登陆浙江引发多省洪涝灾害与谣言治理风波",
        "description": "7月11日超强台风\"巴威\"在浙江台州玉环登陆，最大风力17级以上，强降雨波及十余省区市。期间2人因编造涉台风谣言被依法处理，引发公众对灾害预警与谣言治理的广泛讨论。",
        "date_start": "2026-07-10",
        "date_end": "2026-07-20",
        "risk_level": "high",
    },
    {
        "keyword": "幽灵外卖平台被罚",
        "event_title": "市场监管总局对\"幽灵外卖\"重拳出击，7家平台被罚35.97亿元",
        "description": "市场监管总局对7家外卖平台\"幽灵店铺\"问题开出35.97亿元罚单，平台法定代表人同步被罚，引发外卖行业大震动和消费者广泛讨论。",
        "date_start": "2026-07-05",
        "date_end": "2026-07-15",
        "risk_level": "high",
    },
    {
        "keyword": "摆拍浸猪笼被刑拘",
        "event_title": "湖南汨罗\"摆拍浸猪笼\"事件策划者被刑拘，低俗摆拍整治升级",
        "description": "何某纠集8人摆拍\"女子被关铁笼游街\"低俗场景博取流量，策划者被刑事拘留，参与者被行政拘留。释放\"摆拍博流量将被刑事打击\"的明确法律信号。",
        "date_start": "2026-07-04",
        "date_end": "2026-07-14",
        "risk_level": "medium",
    },
    {
        "keyword": "鹿晗工作室被踢出超话",
        "event_title": "鹿晗粉丝将工作室\"踢出超话\"引爆内娱粉丝治理争议",
        "description": "因网红司晓迪持续造谣\"鹿晗疑似出轨\"，工作室仅转发半年前旧声明，激怒死忠粉。大吧公开将工作室移出超话关联，被称为\"内娱新型物种\"，引爆饭圈治理讨论。",
        "date_start": "2026-07-06",
        "date_end": "2026-07-16",
        "risk_level": "medium",
    },
    {
        "keyword": "热搜泛娱乐化争议",
        "event_title": "主流媒体集体发声：公共议题应从娱乐八卦手中夺回热搜C位",
        "description": "台风洪涝期间娱乐八卦仍占据热搜大半，浙江日报、杭州网等主流媒体批评平台算法偏向娱乐内容，呼吁\"公共议题应从娱乐八卦手中夺回热搜C位\"。",
        "date_start": "2026-07-05",
        "date_end": "2026-07-15",
        "risk_level": "medium",
    },
]

# ── 各平台评论模板 ──────────────────────────────────────────────

# B站风格评论 (偏年轻化、弹幕文化、表情包用语)
BILIBILI_COMMENTS = {
    "台风巴威登陆": {
        "positive": [
            "救援人员辛苦了！[打call] 希望大家平安",
            "这次预警做得不错，比上次台风进步很多",
            "还好提前做了准备，社区通知很及时",
            "支持严惩造谣者！灾害面前还搞这些",
            "有一说一，这次防汛响应速度值得点赞",
            "感谢所有一线人员的付出[爱心] 注意安全",
            "虽然风很大但政府应对还是有进步的",
            "已经在安置点了，物资供应很充足，感谢",
        ],
        "negative": [
            "又是台风又是洪水，这天气还让不让人活了",
            "排水系统也太差了吧，年年淹年年不改",
            "造谣的人真是缺德，灾害面前还博流量",
            "我们小区停电快24小时了都没人管[无语]",
            "预警发了跟没发一样，信息根本不通畅",
            "年年防汛年年涝，基础设施到底什么时候能跟上",
            "太可怕了这风，窗户都吹飞了[害怕]",
            "官方通报能不能及时一点？？等了半天没消息",
        ],
        "neutral": [
            "沿海居民注意安全，非必要不出门",
            "有没有人知道台风路径最新情况？",
            "等一个灾后评估，看看损失多大",
            "建议沿海城市加强防洪标准建设",
            "理性讨论：这次应对和去年台风相比怎么样",
            "有没有在浙江的兄弟说说现场情况",
            "台风天居家指南，记得囤水和食物",
        ],
    },
    "幽灵外卖平台被罚": {
        "positive": [
            "终于出手了！这些幽灵店铺早该整治了[打call]",
            "35.97亿！这罚款力度可以，平台肉疼了吧",
            "支持市场监管局！外卖行业确实该好好管管",
            "罚得好！连法人一起罚，看以后还敢不敢",
            "之前点外卖踩过好几次雷，终于有人管了",
            "这次是动真格的了，点赞点赞[点赞]",
            "希望长期执行下去，别只是一阵风",
            "建议消费者也多举报，大家一起监督",
        ],
        "negative": [
            "罚了35亿消费者能得到赔偿吗？最后还不是涨价",
            "早干嘛去了？幽灵外卖都存在好几年了才查",
            "平台赚了那么多黑心钱，罚这点根本不算什么",
            "我上次点外卖食物中毒投诉了一个月都没人理",
            "最恶心的是幽灵店铺评分还特别高，全是刷的",
            "只罚7家？还有多少没查出来的？",
            "罚款最后还不是转嫁到商家和骑手身上",
            "查完罚完，过几个月又死灰复燃，有什么用",
        ],
        "neutral": [
            "有没有人科普一下什么叫幽灵外卖？",
            "35亿罚款会怎么分配？会退还给消费者吗？",
            "等一个详细通报，看看有哪些平台",
            "建议建立外卖店铺实名认证+定期巡查机制",
            "这次整改对正常经营的店铺有影响吗？",
            "作为路人，觉得外卖行业规范是迟早的事",
        ],
    },
    "摆拍浸猪笼被刑拘": {
        "positive": [
            "支持严惩！低俗摆拍终于有人管了[点赞]",
            "刑事拘留！这个信号很明确，摆拍不是小事",
            "干得好，这些博眼球的早该整治了",
            "希望这次能形成判例，以后都有法可依",
            "为公安部门的果断行动点赞[给力]",
            "网络不是法外之地，这次震慑效果应该会很好",
            "之前那些摆拍的现在该慌了吧[滑稽]",
        ],
        "negative": [
            "太恶心了这种人，为了流量什么都干得出来",
            "这年头为了红真的没有底线了……",
            "摆拍也就算了，还搞这种侮辱女性的内容[怒]",
            "参与的那些人也都该抓，不是只抓策划者",
            "平台也有责任吧？这种视频怎么过审的",
            "现在网上全是剧本，真假都分不清了",
            "之前那么多摆拍为什么不查？就查这一个？",
        ],
        "neutral": [
            "刑拘和行拘的区别是什么？有没有法律大佬科普",
            "这个案例值得讨论：摆拍到什么程度才算违法",
            "等后续审判结果出来再评价",
            "摆拍和创作的区别边界在哪里？",
            "建议出台更明确的网络内容管理规范",
        ],
    },
    "鹿晗工作室被踢出超话": {
        "positive": [
            "粉丝做得对！工作室不作为就该被抵制",
            "支持粉丝维权，明星工作室不能只会发声明",
            "大吧这一手操作可以的，给其他粉丝团体打了个样",
            "粉丝经济终于开始倒逼工作室提升服务质量了",
            "有一说一，这次站粉丝这边，工作室太敷衍了",
            "希望这件事能让更多艺人团队重视粉丝沟通",
        ],
        "negative": [
            "饭圈撕逼又来了……这也能上热搜？",
            "造谣的人不追究，反过来撕工作室？逻辑呢",
            "粉丝管太宽了吧，工作室怎么做还要你们教",
            "这届粉丝戏真多，鹿晗都没说话你们急什么",
            "明星和粉丝的关系越来越畸形了[笑哭]",
            "工作室被踢出超话是什么操作……第一次听说",
        ],
        "neutral": [
            "有没有课代表总结一下前因后果？",
            "第一次看到粉丝把工作室踢出超话的[吃瓜]",
            "理性讨论：粉丝到底有没有权利这样对工作室",
            "内娱现在的生态确实需要好好反思一下了",
            "等鹿晗本人回应吧，现在信息不够全",
        ],
    },
    "热搜泛娱乐化争议": {
        "positive": [
            "说得太对了！公共议题确实应该占据更多热搜",
            "浙江日报这篇文章写得好，一针见血",
            "支持媒体发声，不能只让算法决定我们看什么",
            "终于有人站出来说这个事了[给力]",
            "热搜应该回归公共属性，而不是纯娱乐",
            "建议平台调整算法权重，给公共议题更多曝光",
        ],
        "negative": [
            "平台才不会改呢，娱乐内容流量大广告多",
            "热搜本来就是看大家关注什么，凭什么强行干预",
            "媒体自己不也天天发娱乐新闻？双标了吧",
            "说得好听，你们媒体不也靠娱乐新闻蹭流量",
            "与其骂平台不如想想为什么大家只看娱乐",
            "管天管地还管大家爱看什么？太闲了吧",
        ],
        "neutral": [
            "热搜到底应该是自然形成的还是需要引导的？",
            "这个问题在学界已经讨论很久了，没定论",
            "娱乐和公共议题的平衡确实很难把握",
            "看了一圈评论，感觉两边都有道理",
            "建议看看国外怎么处理类似问题的",
        ],
    },
}

# 微博风格评论 (简短、话题标签、情绪化)
WEIBO_COMMENTS = {
    kw: {
        "positive": [f"#{kw}# 支持！希望妥善解决[加油]", f"感谢关注#{kw}# 总算有进展了[赞]", f"#{kw}# 这件事处理得还不错", f"支持正义[拳头] #{kw}#", f"终于有人发声了#{kw}#[good]"],
        "negative": [f"#{kw}# 太让人气愤了[怒]", f"又是{kw}，什么时候是个头", f"#{kw}# 忍不了了，必须给个说法", f"无语死了{kw}[吐]", f"这处理态度我真的会谢#{kw}#"],
        "neutral": [f"#{kw}# 观望中……", f"关于{kw}，等一个官方通报", f"#{kw}# 理性吃瓜[吃瓜]", f"有没有人了解{kw}具体情况的？", f"{kw}这件事，信息还不够全面"],
    }
    for kw in ["台风巴威登陆", "幽灵外卖平台被罚", "摆拍浸猪笼被刑拘", "鹿晗工作室被踢出超话", "热搜泛娱乐化争议"]
}

# 今日头条风格评论 (偏中老年用户、较长、理性讨论)
TOUTIAO_COMMENTS = {
    kw: {
        "positive": [
            f"关于{kw}事件，从目前的情况来看已经有了积极进展。希望相关部门能够认真对待，给公众一个满意的答复。",
            f"作为长期关注此事的网友，我认为这次的{kw}处理方式值得肯定。社会在进步，问题总会被解决。",
        ],
        "negative": [
            f"{kw}这件事暴露出很多深层次的问题。如果不从根本上解决，类似的事情还会再次发生。",
            f"说实话，{kw}已经不是第一次发生了。每次都是雷声大雨点小，老百姓的权益谁来保障？",
        ],
        "neutral": [
            f"关于{kw}事件，目前各方的说法还不完全一致。建议大家保持理性，等待权威部门的最终调查结果。",
            f"{kw}这个事件确实值得深思。从某种程度上说，它是社会发展过程中必然会遇到的问题。",
        ],
    }
    for kw in ["台风巴威登陆", "幽灵外卖平台被罚", "摆拍浸猪笼被刑拘", "鹿晗工作室被踢出超话", "热搜泛娱乐化争议"]
}

# 小红书风格评论 (短句、emoji、"姐妹们"体、消费视角)
XIAOHONGSHU_COMMENTS = {
    kw: {
        "positive": [
            f"姐妹们！这个真的要支持[点赞] {kw}，终于有人发声了！",
            f"说得太对了！{kw}就是要这样[加油][加油] 给博主点赞",
            f"狠狠赞同了[爱心] {kw}这件事真的有在变好",
            f"已收藏✅ 关于{kw}，希望更多姐妹看到",
            f"👏👏👏 {kw}有进展了！姐妹们一起关注",
            f"感谢科普[玫瑰R] {kw}这次的处理还是很及时的",
        ],
        "negative": [
            f"救命🆘 {kw}这也太离谱了吧……真的无语了",
            f"姐妹们避雷⚠️ 关于{kw}，我真的忍不了了[发怒R]",
            f"谁懂啊……{kw}这件事越想越气[哭惹R][哭惹R]",
            f"真的栓Q了[微笑R] {kw}，这个处理态度我真的会谢",
            f"避雷避雷‼️ {kw}千万别踩坑[心碎R]",
            f"不敢说话了[捂脸R] {kw}懂的都懂……只能说很失望",
        ],
        "neutral": [
            f"蹲一个后续📌 {kw}，有姐妹了解内幕吗？",
            f"观望ing……{kw}到底是什么情况啊[疑问R]",
            f"理性讨论🔍 {kw}这件事，大家怎么看？",
            f"有没有课代表总结一下{kw}来龙去脉？[皱眉R]",
            f"先马住🐎 {kw}，等更多信息出来再说",
            f"刷到了好多{kw}的笔记……评论区好热闹[吃瓜R]",
        ],
    }
    for kw in ["台风巴威登陆", "幽灵外卖平台被罚", "摆拍浸猪笼被刑拘", "鹿晗工作室被踢出超话", "热搜泛娱乐化争议"]
}

# 用户名池
BILIBILI_USER_POOL = [
    "吃瓜群众甲", "弹幕护体", "阿婆主加油", "三连已投", "硬币收割机",
    "老二次元了", "深夜肝帝", "咕咕咕", "弹幕发来贺电", "前排留名",
    "技术宅拯救世界", "肝就完了", "下次一定", "白嫖使我快乐", "学分已到账",
    "课代表来了", "前方高能", "弹幕礼仪", "催更小助手", "空耳君",
    "考据党", "科普君", "野生字幕菌", "剪辑鬼才", "鬼畜区在逃素材",
    "每日一乐", "评论区区长", "经典咏流传", "名场面打卡", "热乎的",
]

WEIBO_USER_POOL = [
    "小明今天很开心", "吃瓜少女小陈", "北方的狼", "阳光灿烂的日子",
    "小确幸生活家", "追风少年", "夜空中最亮的星", "路人甲9527",
    "岁月静好", "春风十里不如你", "平凡之路", "梦想还是要有的",
    "生活观察员", "行走的弹幕", "热点追踪者", "心有灵犀",
    "城市漫游者", "时间的朋友", "午后红茶", "日落大道",
]

TOUTIAO_USER_POOL = [
    "老张看世界", "岁月如歌", "平凡人生", "知足常乐", "清风明月",
    "向阳花", "大海无边", "脚踏实地", "诚实守信人", "厚德载物",
    "山清水秀", "天道酬勤", "人生感悟", "知无不言", "行者无疆",
    "时光漫步者", "理性的声音", "深度思考者", "社会观察家", "冷暖自知",
]

# 小红书用户名池
XIAOHONGSHU_USER_POOL = [
    "小红薯Momo", "一只小可爱呀", "是XX吖", "今天也要加油鸭", "不会飞的蝴蝶",
    "爱分享的小王", "美妆课代表", "好物挖掘机", "就是爱吃怎么了", "每天都在买买买",
    "生活家小陈", "Momo酱", "小红薯用户001", "打工人的日常", "不瘦十斤不改名",
    "橙子味的夏天", "奶茶重度患者", "熬夜冠军选手", "在逃公主本人", "人间清醒bot",
    "种草达人小王", "买买买停不下来", "吃瓜第一线", "干货分享家", "避雷小能手",
]

# B站BV号池（扩充）
BVID_POOL = [
    "BV1GJ4m1Q7xN", "BV1Zx4y1t7Uk", "BV1Qa4y1c7Vp", "BV1Hm421A7Xq",
    "BV1Xr421m7Zw", "BV1Nm421K7Yt", "BV1Pw4m1y7Rs", "BV1Lv4y1m7Wu",
    "BV1Rt421w7Vx", "BV1Yu4y1c7Zq", "BV1Sz421z7Xa", "BV1Ty4m1i7Wb",
    "BV1Kw421n7Vc", "BV1Kx4y1o7Xd", "BV1Ny421p7Ye",
    "BV1fJ4m1Q7kN", "BV1Aa4y1c7Wq", "BV1Bm421K7Zr",
]

# B站视频标题模板
BILIBILI_TITLE_TEMPLATES = {
    "台风巴威登陆": [
        "【台风直播】超强台风巴威登陆全过程，现场画面",
        "17级台风巴威到底有多猛？实测风力对比",
        "台风巴威过后，浙江多地满目疮痍",
        "气象专家解读：为什么巴威来得这么猛？",
    ],
    "幽灵外卖平台被罚": [
        "【深度】幽灵外卖大起底！你点的外卖可能来自不存在店铺",
        "35.97亿！外卖平台被罚背后是什么逻辑？",
        "外卖平台幽灵店铺深度调查，触目惊心",
        "市场监管总局重拳出击，外卖行业要变天了",
    ],
    "摆拍浸猪笼被刑拘": [
        "【热点】摆拍\"浸猪笼\"事件全解析，为何被刑拘？",
        "为了流量什么都敢拍？深度分析摆拍产业链",
        "刑拘！摆拍终于有代价了，法律人解读",
    ],
    "鹿晗工作室被踢出超话": [
        "【吃瓜】鹿晗粉丝把工作室踢出超话，这操作绝了",
        "内娱新物种！粉丝踢走工作室始末分析",
        "从鹿晗事件看粉丝经济的边界在哪里",
    ],
    "热搜泛娱乐化争议": [
        "【深度】热搜被娱乐占领？公共议题为何上不去",
        "谁在操控热搜？算法、资本还是我们自己",
        "浙江日报发声：夺回热搜C位",
    ],
}

# 小红书笔记ID池
XHS_NOTE_ID_POOL = [f"xhs_{i}" for i in range(600000000000000, 600000000000050)]

# 小红书笔记标题模板
XIAOHONGSHU_TITLE_TEMPLATES = {
    "台风巴威登陆": [
        "台风天居家囤货清单🧾 姐妹们快抄作业！",
        "台风巴威来了😱 浙江姐妹还好吗？",
        "防灾包里必须准备的5样东西⚠️ 少一样都不行",
    ],
    "幽灵外卖平台被罚": [
        "救命！这些外卖店居然是幽灵店铺👻 避雷指南",
        "外卖平台被罚35亿！以后点外卖要注意这些",
        "我的外卖维权经历💢 幽灵店铺退款全记录",
    ],
    "摆拍浸猪笼被刑拘": [
        "摆拍终于被刑拘了！聊聊短视频行业的\"演技派\"",
        "为了流量什么都拍？这次是真的进去了🚔",
    ],
    "鹿晗工作室被踢出超话": [
        "吃瓜🍉 鹿晗粉丝踢走工作室，饭圈新操作",
        "围观内娱drama：粉丝到底有没有权利踢工作室",
    ],
    "热搜泛娱乐化争议": [
        "姐妹们有没有发现热搜越来越没营养了🤔",
        "为什么重要新闻上不了热搜？算法揭秘🔍",
    ],
}


def _random_date(start_str: str, end_str: str) -> datetime:
    """在两个日期之间随机生成一个时间。"""
    start = datetime.strptime(start_str, "%Y-%m-%d")
    end = datetime.strptime(end_str, "%Y-%m-%d")
    delta = (end - start).days
    random_days = random.randint(0, max(delta, 1))
    random_seconds = random.randint(0, 86399)
    return start + timedelta(days=random_days, seconds=random_seconds)


def _generate_bilibili_comment(event_keyword: str, sentiment: str) -> Dict[str, Any]:
    """生成一条B站风格评论。"""
    templates = BILIBILI_COMMENTS.get(event_keyword, {})
    texts = templates.get(sentiment, ["关注一下这个事件。"])
    content = random.choice(texts)

    title_templates = BILIBILI_TITLE_TEMPLATES.get(event_keyword, [f"关于{event_keyword}的讨论"])
    source_title = random.choice(title_templates)

    event_config = next((e for e in EVENT_CONFIGS if e["keyword"] == event_keyword), EVENT_CONFIGS[0])
    ctime_dt = _random_date(event_config["date_start"], event_config["date_end"])

    return {
        "platform": "bilibili",
        "source_id": random.choice(BVID_POOL),
        "source_title": source_title,
        "content": content,
        "like_count": random.randint(0, 5000),
        "ctime": int(ctime_dt.timestamp()),
        "ctime_str": ctime_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "member_level": random.randint(0, 6),
        "reply_count": random.randint(0, 500),
        "page": random.randint(1, 20),
        "user_name": random.choice(BILIBILI_USER_POOL),
        "comment_id": f"rpid_{random.randint(10000000, 99999999)}",
    }


def _generate_weibo_comment(event_keyword: str, sentiment: str) -> Dict[str, Any]:
    """生成一条微博风格评论。"""
    templates = WEIBO_COMMENTS.get(event_keyword, {})
    texts = templates.get(sentiment, ["关注一下这件事。"])
    content = random.choice(texts)

    event_config = next((e for e in EVENT_CONFIGS if e["keyword"] == event_keyword), EVENT_CONFIGS[0])
    ctime_dt = _random_date(event_config["date_start"], event_config["date_end"])

    post_id = str(random.randint(4000000000000000, 5000000000000000))
    return {
        "platform": "weibo",
        "source_id": post_id,
        "source_title": f"微博热议-{event_keyword}",
        "content": content,
        "like_count": random.randint(0, 10000),
        "ctime": int(ctime_dt.timestamp()),
        "ctime_str": ctime_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "member_level": 0,
        "reply_count": random.randint(0, 1000),
        "page": random.randint(1, 10),
        "user_name": random.choice(WEIBO_USER_POOL),
        "comment_id": str(random.randint(4000000000000000, 5000000000000000)),
    }


def _generate_toutiao_comment(event_keyword: str, sentiment: str) -> Dict[str, Any]:
    """生成一条今日头条风格评论。"""
    templates = TOUTIAO_COMMENTS.get(event_keyword, {})
    texts = templates.get(sentiment, ["关注一下这个事件的发展。"])
    content = random.choice(texts)

    event_config = next((e for e in EVENT_CONFIGS if e["keyword"] == event_keyword), EVENT_CONFIGS[0])
    ctime_dt = _random_date(event_config["date_start"], event_config["date_end"])

    article_id = str(random.randint(7000000000000000, 8000000000000000))
    article_titles = [
        f"深度 | {event_keyword}事件始末，一文读懂",
        f"热议 | {event_keyword}引发全网关注，各方回应来了",
        f"{event_keyword}持续发酵，多方发声",
        f"【关注】{event_keyword}事件最新进展",
        f"专家解读 | {event_keyword}背后的深层问题",
    ]
    return {
        "platform": "toutiao",
        "source_id": article_id,
        "source_title": random.choice(article_titles),
        "content": content,
        "like_count": random.randint(0, 3000),
        "ctime": int(ctime_dt.timestamp()),
        "ctime_str": ctime_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "member_level": 0,
        "reply_count": random.randint(0, 300),
        "page": 1,
        "user_name": random.choice(TOUTIAO_USER_POOL),
        "comment_id": article_id,
    }


def _generate_xiaohongshu_comment(event_keyword: str, sentiment: str) -> Dict[str, Any]:
    """生成一条小红书风格评论。"""
    templates = XIAOHONGSHU_COMMENTS.get(event_keyword, {})
    texts = templates.get(sentiment, [f"关于{event_keyword}，持续关注中……"])
    content = random.choice(texts)

    title_templates = XIAOHONGSHU_TITLE_TEMPLATES.get(event_keyword, [f"关于{event_keyword}的讨论"])
    source_title = random.choice(title_templates)

    event_config = next((e for e in EVENT_CONFIGS if e["keyword"] == event_keyword), EVENT_CONFIGS[0])
    ctime_dt = _random_date(event_config["date_start"], event_config["date_end"])

    note_id = str(random.choice(XHS_NOTE_ID_POOL)) if XHS_NOTE_ID_POOL else f"xhs_{random.randint(600000000000000, 700000000000000)}"

    return {
        "platform": "xiaohongshu",
        "source_id": note_id,
        "source_title": source_title,
        "content": content,
        "like_count": random.randint(0, 8000),
        "ctime": int(ctime_dt.timestamp()),
        "ctime_str": ctime_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "member_level": 0,
        "reply_count": random.randint(0, 800),
        "page": 1,
        "user_name": random.choice(XIAOHONGSHU_USER_POOL),
        "comment_id": note_id,
    }


def generate_comments(
    event_keyword: str,
    total: int = 500,
    platform_ratio: Optional[Dict[str, float]] = None,
) -> List[Dict[str, Any]]:
    """
    为指定事件生成指定数量的评论，按平台比例分配。

    Args:
        event_keyword: 事件关键词
        total: 总评论数
        platform_ratio: 平台比例，默认 {'bilibili': 0.4, 'weibo': 0.4, 'toutiao': 0.2}

    Returns:
        评论列表
    """
    if platform_ratio is None:
        platform_ratio = {"bilibili": 0.25, "weibo": 0.25, "toutiao": 0.25, "xiaohongshu": 0.25}

    # 情感分布: 正面 25%, 负面 45%, 中性 30%
    sentiment_ratio = {"positive": 0.25, "negative": 0.45, "neutral": 0.30}

    comments: List[Dict[str, Any]] = []
    generators = {
        "bilibili": _generate_bilibili_comment,
        "weibo": _generate_weibo_comment,
        "toutiao": _generate_toutiao_comment,
        "xiaohongshu": _generate_xiaohongshu_comment,
    }

    for platform, ratio in platform_ratio.items():
        count = int(total * ratio)
        generator = generators.get(platform)
        if not generator:
            continue

        for _ in range(count):
            # 按概率选择情感
            sentiment = random.choices(
                list(sentiment_ratio.keys()),
                weights=list(sentiment_ratio.values()),
                k=1,
            )[0]
            comment = generator(event_keyword, sentiment)
            comment["keyword"] = event_keyword
            comments.append(comment)

    return comments


def generate_all_events(
    comments_per_event: int = 600,
    platform_ratio: Optional[Dict[str, float]] = None,
) -> List[Dict[str, Any]]:
    """
    为所有5个事件生成评论数据。

    Args:
        comments_per_event: 每个事件的评论数
        platform_ratio: 平台比例

    Returns:
        所有评论的列表
    """
    all_comments: List[Dict[str, Any]] = []
    for event in EVENT_CONFIGS:
        print(f"生成事件数据: {event['event_title']} ({comments_per_event}条)")
        comments = generate_comments(
            event["keyword"],
            total=comments_per_event,
            platform_ratio=platform_ratio,
        )
        all_comments.extend(comments)
        print(f"  -> B站: {sum(1 for c in comments if c['platform'] == 'bilibili')}条, "
              f"微博: {sum(1 for c in comments if c['platform'] == 'weibo')}条, "
              f"头条: {sum(1 for c in comments if c['platform'] == 'toutiao')}条, "
              f"小红书: {sum(1 for c in comments if c['platform'] == 'xiaohongshu')}条")

    return all_comments


if __name__ == "__main__":
    random.seed(42)
    comments = generate_all_events(600)
    print(f"\n总共生成 {len(comments)} 条评论")
    # 统计
    for platform in ["bilibili", "weibo", "toutiao", "xiaohongshu"]:
        count = sum(1 for c in comments if c["platform"] == platform)
        print(f"  {platform}: {count}条")
