import unittest
from pathlib import Path

from tools.convert_overpass_buildings import convert


class BuildingConversionTests(unittest.TestCase):
    def test_downloaded_beijing_buildings_convert_to_extrudable_geojson(self):
        root = Path(__file__).parents[1]
        result = convert(root / "data/maps/beijing_buildings_overpass.json")
        self.assertGreater(len(result["features"]), 100)
        feature = result["features"][0]
        self.assertEqual(feature["geometry"]["type"], "Polygon")
        self.assertGreater(feature["properties"]["height"], 0)


if __name__ == "__main__":
    unittest.main()
