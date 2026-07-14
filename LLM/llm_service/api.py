"""Flask Blueprint，可直接注册到成员 A 的主应用。"""

from flask import Blueprint, jsonify, request

from .llm_service import ask_event_question
from .report_generator import generate_report
from .trend_predictor import predict_trend


def create_llm_blueprint() -> Blueprint:
    blueprint = Blueprint("llm", __name__, url_prefix="/api/llm")

    @blueprint.after_request
    def add_utf8_charset(response):
        """兼容 Windows PowerShell 5.1，避免中文 JSON 被按西文编码解析。"""
        if response.mimetype == "application/json":
            response.headers["Content-Type"] = "application/json; charset=utf-8"
        return response

    def body():
        data = request.get_json(silent=True)
        return data if isinstance(data, dict) else {}

    @blueprint.post("/ask")
    def ask():
        data = body()
        result = ask_event_question(data.get("event_data", {}), data.get("question", ""))
        return jsonify(result), 200 if result.get("success") else 400

    @blueprint.post("/predict")
    def predict():
        data = body()
        result = predict_trend(data.get("trend_data", []))
        return jsonify(result), 200 if result.get("success") else 400

    @blueprint.post("/report")
    def report():
        data = body()
        result = generate_report(data.get("event_data", {}))
        return jsonify(result), 200 if result.get("success") else 400

    return blueprint
