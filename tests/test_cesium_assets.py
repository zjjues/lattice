import unittest
from pathlib import Path


class CesiumAssetsTests(unittest.TestCase):
    def test_local_cesium_runtime_and_monitor_exist(self):
        root = Path(__file__).parents[1]
        vendor = root / "static/vendor/cesium/1.143.0"
        self.assertTrue((vendor / "Cesium.js").is_file())
        self.assertTrue((vendor / "Workers").is_dir())
        self.assertTrue((vendor / "Assets/Textures/NaturalEarthII/tilemapresource.xml").is_file())
        self.assertTrue((root / "static/models/Cesium_Air.glb").is_file())
        script = (root / "static/flight-monitor-3d.js").read_text(encoding="utf-8")
        self.assertIn("morphTo2D", script)
        self.assertIn("morphToColumbusView", script)
        self.assertIn("morphTo3D", script)
        self.assertIn("Cesium_Air.glb", script)
        self.assertIn("/api/v1/tracks/", script)


if __name__ == "__main__":
    unittest.main()
