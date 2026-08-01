import unittest
from pathlib import Path

from lattice_core.flight.idf_topics import IdfDsTopicBundleAdapter


class IdfTopicAdapterTests(unittest.TestCase):
    def test_nearest_timestamp_join(self):
        root = Path(__file__).parents[1] / "fixtures/flight/idf_topics"
        frames = list(IdfDsTopicBundleAdapter(root, tolerance_ms=10).frames())
        self.assertEqual(len(frames), 2)
        self.assertEqual(frames[0].timestamp_ms, 1000)
        self.assertAlmostEqual(frames[0].latitude_deg, 39.9042)
        self.assertAlmostEqual(frames[0].airspeed_mps, 18.9)
        self.assertAlmostEqual(frames[0].battery_voltage_v, 15.8)
        self.assertAlmostEqual(frames[1].throttle, 0.55)

    def test_tolerance_can_exclude_unaligned_topics(self):
        root = Path(__file__).parents[1] / "fixtures/flight/idf_topics"
        frame = next(IdfDsTopicBundleAdapter(root, tolerance_ms=1).frames())
        self.assertIsNone(frame.latitude_deg)
        self.assertIsNone(frame.airspeed_mps)


if __name__ == "__main__":
    unittest.main()
