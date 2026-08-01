import json
import inspect
import unittest
from unittest.mock import patch

from lattice_core.decision import RagRecommendationRetriever, RuleRagLlmRecommendationProvider


class _Rules:
    def recommend(self, context):
        return {
            "summary": "规则建议", "riskLevel": "HIGH", "actions": ["保持监控"],
            "recommendedAssetTypes": ["OPERATOR"], "confidence": 0.8,
            "references": [], "providerMetadata": {"humanConfirmationRequired": True},
        }


class _Rag:
    def search(self, query, limit):
        return [{
            "documentId": "doc-1", "documentName": "姿态限制预案",
            "chunkId": "chunk-1", "content": "超过姿态限制时应人工确认。", "score": 0.91,
        }]


class _FallbackRetriever:
    def search(self, query, *, filters=None, limit=5):
        return []


class DecisionLoopTests(unittest.TestCase):
    def setUp(self):
        self.context = {
            "alert": {"alertType": "flight_attitude_limit", "riskLevel": "HIGH"},
            "entity": {"entityId": "aircraft-1"},
            "flightTelemetry": {"attitude": {"rollDegrees": 48}},
            "knowledge": [{
                "docId": "doc-1", "title": "姿态限制预案",
                "excerpt": "超过姿态限制时应人工确认。", "score": 0.91,
            }],
        }
        self.config = lambda: {
            "baseUrl": "https://example.test/v1", "apiKey": "secret", "chatModel": "test-chat"
        }

    def test_embedding_retriever_adapts_chunks(self):
        retriever = RagRecommendationRetriever(_Rag(), _FallbackRetriever())
        hits = retriever.search("姿态异常", limit=3)
        self.assertEqual(hits[0]["docType"], "EMBEDDING_RAG")
        self.assertEqual(hits[0]["docId"], "doc-1")

    @patch("lattice_core.decision.OpenAICompatibleProvider.generate")
    def test_llm_enhances_but_cannot_lower_risk(self, generate):
        generate.return_value = json.dumps({
            "summary": "核验姿态并稳定飞行器", "riskLevel": "LOW",
            "actions": ["核验传感器", "人工确认后调整"], "confidence": 0.86,
        }, ensure_ascii=False)
        result = RuleRagLlmRecommendationProvider(_Rules(), self.config).recommend(self.context)
        self.assertEqual(result["riskLevel"], "HIGH")
        self.assertTrue(result["providerMetadata"]["llmUsed"])
        self.assertTrue(result["providerMetadata"]["ragUsed"])
        self.assertEqual(result["references"][0]["docId"], "doc-1")

    @patch("lattice_core.decision.OpenAICompatibleProvider.generate", side_effect=TimeoutError())
    def test_model_failure_degrades_to_rules(self, generate):
        result = RuleRagLlmRecommendationProvider(_Rules(), self.config).recommend(self.context)
        self.assertEqual(result["summary"], "规则建议")
        self.assertFalse(result["providerMetadata"]["llmUsed"])
        self.assertTrue(result["providerMetadata"]["degraded"])
        self.assertTrue(result["references"])

    def test_recommendation_service_offloads_blocking_work(self):
        from lattice_core.recommendations import RecommendationService
        source = inspect.getsource(RecommendationService.create_for_alert)
        self.assertIn("asyncio.to_thread", source)


if __name__ == "__main__":
    unittest.main()
