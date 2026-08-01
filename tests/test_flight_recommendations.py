import unittest
from pathlib import Path

from lattice_core.flight.recommendations import (
    FlightRuleRecommendationProvider,
    LayeredFlightKnowledgeRetriever,
)


class FlightRecommendationTests(unittest.TestCase):
    def test_layered_retriever_finds_engine_failure_sop(self):
        root = Path(__file__).parents[1]
        retriever = LayeredFlightKnowledgeRetriever(lambda *_args, **_kwargs: [], root / "knowledge/sops")
        hits = retriever.search("engine failure", limit=3)
        self.assertEqual(hits[0]["docId"], "engine_failure")

    def test_flight_provider_is_deterministic_and_marks_human_review(self):
        provider = FlightRuleRecommendationProvider(lambda _context: {"unexpected": True})
        result = provider.recommend({
            "alert": {"alertType": "dataset_fault_annotation", "riskLevel": "HIGH"},
            "knowledge": [{"docId": "engine_failure", "title": "Engine failure"}],
        })
        self.assertEqual(result["provider"], "飞行规则与处置预案")
        self.assertTrue(result["providerMetadata"]["humanConfirmationRequired"])
        self.assertEqual(result["references"][0]["docId"], "engine_failure")


if __name__ == "__main__":
    unittest.main()
