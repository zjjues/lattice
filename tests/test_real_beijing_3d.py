import json
import unittest
from pathlib import Path


class RealBeijing3DTests(unittest.TestCase):
    def test_fixed_3d_page_has_real_buildings_and_no_mode_switch(self):
        root = Path(__file__).parents[1]
        page = (root / "static/flight-monitor-3d-v3.html").read_text(encoding="utf-8")
        script = (root / "static/flight-monitor-3d.js").read_text(encoding="utf-8")
        buildings = json.loads((root / "static/maps/beijing-buildings.geojson").read_text(encoding="utf-8"))
        self.assertNotIn("data-mode", page)
        self.assertNotIn("2.5D", page)
        self.assertNotIn("二维", page)
        self.assertIn("beijing-buildings.geojson", script)
        self.assertIn("extrudedHeight", script)
        self.assertEqual(len(buildings["features"]), 238)


if __name__ == "__main__":
    unittest.main()
