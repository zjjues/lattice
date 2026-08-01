import unittest
from pathlib import Path


class MonitorVisualV2Tests(unittest.TestCase):
    def test_clean_monitor_uses_real_map_and_model(self):
        root = Path(__file__).parents[1]
        page = (root / "static/flight-monitor-3d-v2.html").read_text(encoding="utf-8")
        script = (root / "static/flight-monitor-3d.js").read_text(encoding="utf-8")
        self.assertIn("flight-monitor-3d-v2.css", page)
        self.assertIn("tile.openstreetmap.fr", script)
        self.assertIn("Cesium_Air.glb", script)
        self.assertIn("minimumPixelSize: 9", script)
        self.assertNotIn("addBuildings();", script)


if __name__ == "__main__":
    unittest.main()
