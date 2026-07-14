"""Flask 后端主入口 — 网络舆情事件智能分析系统。

启动方式：
    pip install -r requirements.txt
    python data_import.py       # 仅首次运行，导入数据
    python app.py               # 启动服务 → http://localhost:5000
"""

import os
import sys

# 将 LLM 服务包所在目录加入搜索路径，使其可作为包导入
_llm_parent = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'LLM')
if os.path.isdir(_llm_parent):
    sys.path.insert(0, _llm_parent)

from flask import Flask, jsonify, request
from flask_cors import CORS

import models
from auth import auth_bp
from events import events_bp
from profile import profile_bp


def create_app() -> Flask:
    app = Flask(__name__)
    app.json.ensure_ascii = False

    CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

    # ── 注册核心 Blueprint ──
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(events_bp, url_prefix="/api")
    app.register_blueprint(profile_bp, url_prefix="/api/user")

    # ── 挂载成员 D 的 LLM 服务 ──
    try:
        from llm_service import api as _llm_api
        app.register_blueprint(_llm_api.create_llm_blueprint())
        print("[app] LLM 服务已挂载 → /api/llm/*")
    except ImportError as e:
        print(f"[app] LLM 服务未加载（成员D模块不可用）: {e}")
        # 提供兜底接口
        _register_llm_fallback(app)

    # ── 健康检查 ──
    @app.get("/api/health")
    def health():
        return jsonify({"success": True, "service": "opinion-backend"})

    # ── 初始化数据库 ──
    models.init_db()
    print("[app] 数据库已初始化")

    # ── 启动定时爬虫调度器（每 30 分钟）──
    try:
        import scheduler
        scheduler.start_scheduler()
        print("[app] 定时爬虫调度器已启动（每 30 分钟）")
    except Exception as e:
        print(f"[app] 调度器启动失败: {e}")

    # ── 手动触发爬取接口（异步：立即返回，后台执行）──
    @app.post("/api/crawl/trigger")
    def trigger_crawl():
        """异步触发爬虫流水线。返回 accepted=true 表示已启动。"""
        import json as _json
        import scheduler as _scheduler

        config = request.get_json(silent=True) or {}

        # 如果前端传了自定义配置，写入临时配置文件供 pipeline 读取
        if config:
            config_path = _scheduler.CRAWLER_DIR / "crawl_config.json"
            try:
                config_path.write_text(
                    _json.dumps(config, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                print(f"[app] 已写入爬取配置: {config_path}")
            except Exception as e:
                print(f"[app] 写入配置失败: {e}")

        accepted = _scheduler.trigger_async()
        if accepted:
            return jsonify({"success": True, "message": "爬取任务已启动，请轮询 /api/crawl/status 查看进度"})
        else:
            return jsonify({"success": False, "message": "已有爬取任务正在运行，请等待完成后再试"})

    @app.get("/api/crawl/status")
    def crawl_status():
        """查看调度器状态 + 当前爬取进度。"""
        import scheduler as _scheduler
        state = _scheduler.get_status()
        return jsonify({
            "interval_minutes": _scheduler.INTERVAL_SECONDS // 60,
            "crawler_dir": str(_scheduler.CRAWLER_DIR),
            **state,
        })

    return app


def _register_llm_fallback(app: Flask) -> None:
    """LLM 服务不可用时的兜底接口。"""
    from flask import Blueprint, request

    fallback = Blueprint("llm_fallback", __name__, url_prefix="/api/llm")

    @fallback.post("/ask")
    def ask():
        data = request.get_json(silent=True) or {}
        question = data.get("question", "")
        return jsonify({
            "success": True,
            "answer": f"这是对「{question[:50]}」的模拟回答。LLM 服务未配置，请联系管理员。",
            "mode": "fallback",
        })

    @fallback.post("/predict")
    def predict():
        return jsonify({
            "success": True,
            "method": "linear_regression",
            "trend": "平稳",
            "change_ratio": 0.0,
            "predictions": [],
            "lifecycle": {"stage": "成长期", "confidence": 0.4, "description": "LLM 服务未配置，使用默认生命周期阶段"},
        })

    @fallback.post("/report")
    def report():
        data = request.get_json(silent=True) or {}
        event = data.get("event_data", {})
        title = event.get("title", "未知事件")
        summary = event.get("summary", "暂无摘要")
        occur_time = event.get("occurTime", "暂无数据")
        source = event.get("source", "暂无数据")
        keywords = event.get("keywords", [])
        kw_text = "、".join(keywords) if isinstance(keywords, list) else str(keywords)
        sentiment = event.get("sentiment_distribution", "暂无数据")
        platforms = event.get("platform_distribution", "暂无数据")
        return jsonify({
            "success": True,
            "report": (
                f"# {title}舆情分析报告\n\n"
                f"## 一、事件概述\n\n"
                f"- **发生时间**：{occur_time}\n"
                f"- **首发平台**：{source}\n"
                f"- **事件起因**：{summary}\n"
                f"- **涉及人物/机构**：当前数据中暂无明确人物/机构信息。\n\n"
                f"关键词：{kw_text or '暂无'}。\n\n"
                f"## 二、传播趋势分析\n\n暂无数据\n\n"
                f"## 三、情感倾向分析\n\n{sentiment}\n\n"
                f"## 四、风险等级研判\n\n平台分布：{platforms}\n\n"
                f"## 五、处置建议\n\n"
                f"1. 持续监测高占比平台与热度异常增长时段。\n"
                f"2. 核验核心信息，及时发布权威说明。\n"
                f"3. 对集中出现的负面观点分类回应。\n"
                f"4. 设置热度和负面占比预警阈值。\n"
            ),
            "format": "markdown",
            "mode": "fallback",
        })

    app.register_blueprint(fallback)
    print("[app] LLM 兜底接口已注册（Mock 模式）")


if __name__ == "__main__":
    app = create_app()
    print("[app] 服务启动 → http://localhost:5000")
    print("[app] API 前缀: /api")
    app.run(host="0.0.0.0", port=5000, debug=False, load_dotenv=False)
