import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app import app


class UnifiedConsoleTests(unittest.TestCase):
    def test_monitor_is_single_entry_for_situation_and_knowledge(self):
        response = TestClient(app).get("/monitor")
        self.assertEqual(response.status_code, 200)
        self.assertIn("飞行任务监控台", response.text)
        self.assertIn("态势监控", response.text)
        self.assertIn("知识库", response.text)
        self.assertIn("flight-monitor-3d-v3.html", response.text)
        self.assertIn("knowledge-bases.html", response.text)
        self.assertIn("model-hub.html", response.text)

    def test_console_shell_exists(self):
        page = Path(__file__).parents[1] / "static/unified-console.html"
        self.assertTrue(page.is_file())


if __name__ == "__main__":
    unittest.main()
