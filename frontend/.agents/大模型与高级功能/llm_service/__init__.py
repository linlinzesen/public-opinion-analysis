"""网络舆情系统的大模型与高级功能模块。"""

from .api import create_llm_blueprint
from .llm_service import ask_event_question
from .report_generator import generate_report
from .trend_predictor import predict_trend

__all__ = [
    "ask_event_question",
    "predict_trend",
    "generate_report",
    "create_llm_blueprint",
]
