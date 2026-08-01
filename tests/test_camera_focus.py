from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class CameraFocusTests(unittest.TestCase):
    def test_initial_camera_explicitly_targets_flight_area(self):
        script = (ROOT / "static" / "flight-monitor-3d.js").read_text(encoding="utf-8")
        self.assertIn("function focusScene()", script)
        self.assertIn("new C.HeadingPitchRange", script)
        self.assertIn("viewer.camera.lookAt(center, offset)", script)
        self.assertIn("const overview = () => focusScene();", script)
        self.assertIn("\n  focusScene();", script)
    def test_left_drag_pans_the_map(self):
        script = (ROOT / "static" / "flight-monitor-3d.js").read_text(encoding="utf-8")
        self.assertIn("cameraController.enableRotate = false", script)
        self.assertIn("ScreenSpaceEventType.LEFT_DOWN", script)
        self.assertIn("ScreenSpaceEventType.MOUSE_MOVE", script)
        self.assertIn("viewer.camera.pickEllipsoid", script)
        self.assertIn("viewer.camera.position = C.Cartesian3.add", script)



if __name__ == "__main__":
    unittest.main()
