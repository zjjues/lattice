import unittest

from fastapi.testclient import TestClient

from app import app, mission_scenario


class MissionScenarioTests(unittest.TestCase):
    def setUp(self):
        mission_scenario.reset()
        self.client = TestClient(app)

    def test_multi_domain_scenario_exposes_platform_sensors(self):
        body = self.client.get("/api/v1/mission-scenario").json()
        self.assertEqual(body["domain"], "AIR_SEA")
        self.assertGreaterEqual(len(body["platforms"]), 5)
        self.assertLessEqual(len(body["platforms"]), 10)
        self.assertTrue(all(platform["sensors"] for platform in body["platforms"]))
        self.assertEqual(body["integration"]["eventTransportContract"], "FastDDS MissionEvent/v1")

    def test_scenario_advances_through_visible_stages(self):
        idle = self.client.get("/api/v1/mission-scenario").json()
        first = self.client.post("/api/v1/mission-scenario/trigger", json={"triggerType": "spectrum_anomaly"}).json()
        second = self.client.post("/api/v1/mission-scenario/advance").json()
        self.assertEqual(idle["mode"], "MONITORING")
        self.assertEqual(first["activeStage"]["stageId"], "detect")
        self.assertEqual(first["trigger"]["name"], "发现异常电磁辐射")
        self.assertEqual(second["activeStage"]["stageId"], "task")
        self.assertGreater(second["activeStage"]["confidence"], first["activeStage"]["confidence"])

    def test_unified_console_uses_system_operations_view(self):
        html = self.client.get("/monitor").text
        self.assertIn("/static/system-operations-v2.html", html)
        self.assertIn("体系任务监控台", html)


if __name__ == "__main__":
    unittest.main()
