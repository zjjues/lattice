import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app import app


class MinimalValidationTests(unittest.TestCase):
    def test_dataset_to_recommendation_scenario(self):
        response = TestClient(app).post("/api/v1/demo/minimal-validation")
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["dataset"], "ALFA")
        self.assertEqual(body["summary"]["framesIngested"], 3)
        self.assertIn("dataset_fault_annotation", body["ruleTypes"])
        self.assertIn("engine_failure", body["knowledgeReferences"])
        history_response = TestClient(app).get("/api/v1/tracks/beijing-flight-demo/history")
        self.assertEqual(history_response.status_code, 200, history_response.text)
        history = history_response.json()["history"]
        self.assertGreaterEqual(len(history), 3)
        history = history[-3:]
        self.assertEqual(history[0]["rollDegrees"], 1.2)
        self.assertEqual(history[1]["pitchDegrees"], 0.8)
        self.assertEqual(history[2]["yawDegrees"], 89.1)
        self.assertEqual(history[2]["altitudeMeters"], 163.7)

        self.assertTrue(all(body["checks"].values()), body["checks"])


if __name__ == "__main__":
    def test_monitor_bootstraps_demo_when_entity_is_missing(self):
        script = (Path(__file__).parents[1] / "static/flight-monitor-3d.js").read_text(encoding="utf-8")
        self.assertIn("async function ensureDemoData()", script)
        self.assertIn('fetch("/api/v1/demo/minimal-validation", {method: "POST"})', script)
        self.assertIn("lerpAngleDegrees", script)
        self.assertIn("start.rollDegrees", script)
        self.assertIn("start.altitudeMeters", script)


    unittest.main()
