"""运行：python -m unittest llm_service.test_llm_service -v"""

import os
import unittest

os.environ["LLM_MOCK"] = "true"

from llm_service.app import create_app
from llm_service.llm_service import ask_event_question
from llm_service.report_generator import generate_report
from llm_service.trend_predictor import predict_trend


EVENT = {
    "id": 1,
    "title": "某品牌产品质量争议",
    "summary": "消费者发布产品质量问题视频，品牌方随后回应并启动调查。",
    "keywords": ["产品质量", "品牌回应", "消费者"],
    "sentiment_distribution": {"positive": 15, "neutral": 30, "negative": 55},
    "trend_data": [
        {"time": "2026-07-09T08:00:00+08:00", "value": 120},
        {"time": "2026-07-09T09:00:00+08:00", "value": 145},
        {"time": "2026-07-09T10:00:00+08:00", "value": 180},
    ],
    "platform_distribution": {"微博": 55, "抖音": 30, "新闻": 15},
}


class CoreFunctionTests(unittest.TestCase):
    def test_ask_mock(self):
        result = ask_event_question(EVENT, "当前事件的负面情感如何？")
        self.assertTrue(result["success"])
        self.assertEqual(result["mode"], "mock")
        self.assertIn("情感分布", result["answer"])

    def test_unrelated_question_is_blocked(self):
        result = ask_event_question(EVENT, "帮我写一道数学题")
        self.assertTrue(result["success"])
        self.assertEqual(result["mode"], "guard")

    def test_predict_24_hourly_points(self):
        result = predict_trend(EVENT["trend_data"])
        self.assertTrue(result["success"])
        self.assertEqual(result["trend"], "上升")
        self.assertEqual(len(result["predictions"]), 24)
        self.assertGreater(result["predictions"][-1]["value"], 180)

    def test_bad_trend(self):
        result = predict_trend([{"time": "bad", "value": 1}])
        self.assertFalse(result["success"])

    def test_report_markdown(self):
        result = generate_report(EVENT)
        self.assertTrue(result["success"])
        self.assertEqual(result["format"], "markdown")
        self.assertIn("## 五、处置建议", result["report"])


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = create_app().test_client()

    def test_ask_api(self):
        response = self.client.post(
            "/api/llm/ask",
            json={"event_data": EVENT, "question": "该事件风险如何？"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content_type, "application/json; charset=utf-8")
        self.assertTrue(response.get_json()["success"])
        self.assertIn("风险", response.get_json()["answer"])

    def test_predict_api_validation(self):
        response = self.client.post("/api/llm/predict", json={"trend_data": []})
        self.assertEqual(response.status_code, 400)

    def test_report_api(self):
        response = self.client.post("/api/llm/report", json={"event_data": EVENT})
        self.assertEqual(response.status_code, 200)
        self.assertIn("report", response.get_json())


if __name__ == "__main__":
    unittest.main()
