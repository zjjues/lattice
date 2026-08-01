from __future__ import annotations

from math import atan2, degrees, hypot
from typing import Any

from .models import FlightFrame
from .sensors import sensor_states_from_telemetry


def frame_to_ingest_event(frame: FlightFrame) -> dict[str, Any]:
    """Map canonical telemetry into the existing Fake Lattice ingest contract."""
    latitude = frame.latitude_deg if frame.latitude_deg is not None else 0.0
    longitude = frame.longitude_deg if frame.longitude_deg is not None else 0.0
    ground_speed = frame.ground_speed_mps
    if ground_speed is None and frame.north_velocity_mps is not None and frame.east_velocity_mps is not None:
        ground_speed = hypot(frame.north_velocity_mps, frame.east_velocity_mps)
    heading = frame.yaw_deg
    if heading is None and frame.north_velocity_mps is not None and frame.east_velocity_mps is not None:
        heading = degrees(atan2(frame.east_velocity_mps, frame.north_velocity_mps)) % 360

    telemetry = {
        "dataset": frame.dataset,
        "timestampMs": frame.timestamp_ms,
        "attitude": {
            "rollDegrees": frame.roll_deg,
            "pitchDegrees": frame.pitch_deg,
            "yawDegrees": frame.yaw_deg,
            "frame": "NED",
        },
        "velocity": {
            "northMetersPerSecond": frame.north_velocity_mps,
            "eastMetersPerSecond": frame.east_velocity_mps,
            "downMetersPerSecond": frame.down_velocity_mps,
            "groundSpeedMetersPerSecond": ground_speed,
            "airSpeedMetersPerSecond": frame.airspeed_mps,
        },
        "controls": {"throttle": frame.throttle},
        "vehicle": {"batteryVoltageVolts": frame.battery_voltage_v, "flightMode": frame.flight_mode},
        "fault": {"active": frame.fault_active, "type": frame.fault_type},
        "location": {
            "latitudeDegrees": latitude,
            "longitudeDegrees": longitude,
            "altitudeMeters": frame.altitude_m,
        },
    }
    telemetry["sensorStates"] = sensor_states_from_telemetry(frame.source_id, telemetry)
    return {
        "sourceType": "flight-dataset",
        "sourceId": frame.source_id,
        "eventType": "track.updated",
        "timestamp": frame.timestamp_ms,
        "track": {
            "trackId": frame.source_id,
            "name": frame.source_id,
            "platformType": "UAV",
            "identity": "unknown",
            "speedMps": ground_speed or 0.0,
            "headingDegrees": heading or 0.0,
            "altitudeMeters": frame.altitude_m or 0.0,
            "location": {
                "latitudeDegrees": latitude,
                "longitudeDegrees": longitude,
            },
        },
        "sensorContext": {
            "confidence": 1.0,
            "tags": ["flight", frame.dataset.lower()],
        },
        "flightTelemetry": telemetry,
    }
