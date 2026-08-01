import json
import tempfile
import unittest
from pathlib import Path

from lattice_core.flight.mapping import frame_to_ingest_event
from lattice_core.flight.models import FlightFrame
from lattice_core.flight.sensors import (
    OpenSkySampleAdapter,
    SensorState,
    build_situation_snapshot,
    sensor_states_from_telemetry,
)


class SensorSituationTests(unittest.TestCase):
    def test_sensor_state_uses_public_contract(self):
        value = SensorState(
            "p/imu", "p", "IMU", "NOMINAL", 20, 0.96,
            {"clipping": False}, {"mode": "ONBOARD"}, {"dataset": "sample"},
        ).to_dict()
        self.assertEqual(value["sensorId"], "p/imu")
        self.assertEqual(value["type"], "IMU")
        self.assertEqual(value["quality"], 0.96)

    def test_existing_flight_frame_contains_sensor_states(self):
        event = frame_to_ingest_event(FlightFrame(
            timestamp_ms=1000, source_id="flight-1", dataset="ALFA",
            latitude_deg=39.9, longitude_deg=116.4, altitude_m=300,
            roll_deg=1, pitch_deg=2, yaw_deg=90, airspeed_mps=30,
            battery_voltage_v=12.1,
        ))
        sensors = event["flightTelemetry"]["sensorStates"]
        self.assertGreaterEqual(len(sensors), 5)
        self.assertEqual({item["type"] for item in sensors}, {"IMU", "GNSS", "AIRSPEED", "BATTERY", "ENGINE"})

    def test_low_airspeed_and_fault_are_degraded(self):
        sensors = sensor_states_from_telemetry("p", {
            "dataset": "ALFA", "timestampMs": 1,
            "attitude": {"rollDegrees": 1, "pitchDegrees": 2, "yawDegrees": 3},
            "velocity": {"airSpeedMetersPerSecond": 12},
            "vehicle": {"batteryVoltageVolts": 12},
            "fault": {"active": True, "type": "engine_failure"},
            "location": {"latitudeDegrees": 39, "longitudeDegrees": 116},
        })
        by_type = {item["type"]: item for item in sensors}
        self.assertEqual(by_type["AIRSPEED"]["status"], "DEGRADED")
        self.assertEqual(by_type["ENGINE"]["status"], "DEGRADED")

    def test_opensky_adapter_maps_state_vectors(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "states.json"
            path.write_text(json.dumps({"time": 100, "states": [[
                "abc123", "TEST1", "China", 99, 100, 116.5, 39.9, 1200,
                False, 88.2, 45.0, 1.2, None, 1250, "7000", False, 0,
            ]]}), encoding="utf-8")
            tracks = OpenSkySampleAdapter(path).tracks()
        self.assertEqual(tracks[0]["trackId"], "opensky-abc123")
        self.assertEqual(tracks[0]["source"], "OpenSky ADS-B")

    def test_situation_snapshot_combines_platform_sensors_and_targets(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "states.json"
            path.write_text(json.dumps({"time": 1, "states": []}), encoding="utf-8")
            entity = {
                "entityId": "aircraft-1",
                "location": {"position": {"latitudeDegrees": 39.9, "longitudeDegrees": 116.4}},
                "flightTelemetry": {
                    "dataset": "ALFA", "timestampMs": 1,
                    "attitude": {"rollDegrees": 0, "pitchDegrees": 0, "yawDegrees": 0},
                    "velocity": {"airSpeedMetersPerSecond": 22}, "vehicle": {}, "fault": {},
                },
            }
            snapshot = build_situation_snapshot(entity, path)
        self.assertEqual(snapshot["platformId"], "aircraft-1")
        self.assertEqual(snapshot["platform"]["sensorCount"], 5)
        self.assertEqual(snapshot["externalTargets"], [])


if __name__ == "__main__":
    unittest.main()
