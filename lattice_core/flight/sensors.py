"""统一传感器状态、观测与开源样本适配。"""
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SensorState:
    sensor_id: str
    platform_id: str
    sensor_type: str
    status: str
    freshness_ms: int
    quality: float
    metrics: dict[str, Any] = field(default_factory=dict)
    coverage: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        return {
            "sensorId": value["sensor_id"], "platformId": value["platform_id"],
            "type": value["sensor_type"], "status": value["status"],
            "freshnessMs": value["freshness_ms"], "quality": value["quality"],
            "metrics": value["metrics"], "coverage": value["coverage"],
            "provenance": value["provenance"],
        }


@dataclass(frozen=True)
class Observation:
    observation_id: str
    sensor_id: str
    observed_at_ms: int
    target_ref: str
    measurement: dict[str, Any]
    quality: dict[str, float]
    provenance: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        return {
            "observationId": value["observation_id"], "sensorId": value["sensor_id"],
            "observedAtMs": value["observed_at_ms"], "targetRef": value["target_ref"],
            "measurement": value["measurement"], "quality": value["quality"],
            "provenance": value["provenance"],
        }


def _number(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) and math.isfinite(value) else None


def sensor_states_from_telemetry(platform_id: str, telemetry: dict[str, Any]) -> list[dict[str, Any]]:
    """从现有统一遥测派生传感器健康，兼容当前 ALFA/IDF 数据。"""
    attitude = telemetry.get("attitude") if isinstance(telemetry.get("attitude"), dict) else {}
    velocity = telemetry.get("velocity") if isinstance(telemetry.get("velocity"), dict) else {}
    vehicle = telemetry.get("vehicle") if isinstance(telemetry.get("vehicle"), dict) else {}
    fault = telemetry.get("fault") if isinstance(telemetry.get("fault"), dict) else {}
    raw_sensors = telemetry.get("sensors") if isinstance(telemetry.get("sensors"), dict) else {}
    dataset = str(telemetry.get("dataset") or "unknown")
    timestamp = int(telemetry.get("timestampMs") or 0)
    source = {"adapter": "canonical-flight", "dataset": dataset, "timestampMs": timestamp}

    roll, pitch, yaw = (_number(attitude.get(key)) for key in ("rollDegrees", "pitchDegrees", "yawDegrees"))
    imu_valid = all(value is not None for value in (roll, pitch, yaw))
    clipping = bool(raw_sensors.get("imu", {}).get("clipping", False)) if isinstance(raw_sensors.get("imu"), dict) else False
    imu_status = "DEGRADED" if clipping or not imu_valid else "NOMINAL"
    states = [SensorState(
        f"{platform_id}/imu-0", platform_id, "IMU", imu_status, 20,
        0.55 if not imu_valid else (0.72 if clipping else 0.96),
        {"rollDeg": roll, "pitchDeg": pitch, "yawDeg": yaw, "clipping": clipping,
         **(raw_sensors.get("imu", {}) if isinstance(raw_sensors.get("imu"), dict) else {})},
        {"mode": "ONBOARD"}, source,
    )]

    location = telemetry.get("location") if isinstance(telemetry.get("location"), dict) else {}
    gnss_valid = all(_number(location.get(key)) is not None for key in ("latitudeDegrees", "longitudeDegrees"))
    states.append(SensorState(
        f"{platform_id}/gnss-0", platform_id, "GNSS", "NOMINAL" if gnss_valid else "DEGRADED",
        200, 0.94 if gnss_valid else 0.48,
        {"latitudeDeg": location.get("latitudeDegrees"), "longitudeDeg": location.get("longitudeDegrees"),
         "altitudeM": location.get("altitudeMeters")},
        {"mode": "GLOBAL"}, source,
    ))

    airspeed = _number(velocity.get("airSpeedMetersPerSecond"))
    states.append(SensorState(
        f"{platform_id}/airspeed-0", platform_id, "AIRSPEED",
        "DEGRADED" if airspeed is None or airspeed < 17 else "NOMINAL", 100,
        0.58 if airspeed is None else (0.7 if airspeed < 17 else 0.93),
        {"airSpeedMps": airspeed, "groundSpeedMps": velocity.get("groundSpeedMetersPerSecond")},
        {"mode": "ONBOARD"}, source,
    ))

    voltage = _number(vehicle.get("batteryVoltageVolts"))
    battery_status = "UNKNOWN" if voltage is None else ("DEGRADED" if voltage < 10.8 else "NOMINAL")
    states.append(SensorState(
        f"{platform_id}/battery-0", platform_id, "BATTERY", battery_status, 1000,
        0.5 if voltage is None else 0.92, {"voltageV": voltage, "flightMode": vehicle.get("flightMode")},
        {"mode": "ONBOARD"}, source,
    ))

    states.append(SensorState(
        f"{platform_id}/engine-monitor-0", platform_id, "ENGINE", "DEGRADED" if fault.get("active") else "NOMINAL",
        250, 1.0 if fault.get("active") else 0.9,
        {"faultActive": bool(fault.get("active")), "faultType": fault.get("type")},
        {"mode": "ONBOARD"}, source,
    ))
    return [state.to_dict() for state in states]


class OpenSkySampleAdapter:
    """OpenSky state-vector JSON 小样本适配器。"""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def tracks(self, *, limit: int = 8) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        timestamp = int(payload.get("time") or 0)
        tracks = []
        for row in payload.get("states") or []:
            if not isinstance(row, list) or len(row) < 17 or row[5] is None or row[6] is None:
                continue
            tracks.append({
                "trackId": f"opensky-{row[0]}", "icao24": row[0],
                "callsign": str(row[1] or "").strip() or "未知呼号", "country": row[2],
                "lastContact": row[4], "longitudeDegrees": row[5], "latitudeDegrees": row[6],
                "altitudeMeters": row[7] if row[7] is not None else row[13],
                "onGround": bool(row[8]), "velocityMps": row[9], "headingDegrees": row[10],
                "verticalRateMps": row[11], "squawk": row[14], "source": "OpenSky ADS-B",
                "sampleTimestamp": timestamp,
            })
        tracks.sort(key=lambda item: (
            (float(item["longitudeDegrees"]) - 116.4074) ** 2
            + (float(item["latitudeDegrees"]) - 39.9042) ** 2
        ))
        return tracks[:limit]


class Px4UlogSensorAdapter:
    """从 PX4 ULog 中抽取一个可展示的传感器快照。"""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def snapshot(self, platform_id: str = "px4-sample") -> dict[str, Any]:
        if not self.path.is_file():
            return {"available": False, "path": str(self.path), "sensors": []}
        from pyulog import ULog
        log = ULog(str(self.path), message_name_filter_list=[
            "sensor_combined", "vehicle_attitude", "vehicle_status", "vehicle_local_position",
        ])
        topics = {item.name: item for item in log.data_list}
        combined = topics.get("sensor_combined")
        attitude = topics.get("vehicle_attitude")
        status = topics.get("vehicle_status")
        sensors: list[SensorState] = []
        if combined:
            data = combined.data
            index = max(0, len(data["timestamp"]) // 2)
            metrics = {
                "accelMps2": [float(data[f"accelerometer_m_s2[{axis}]"][index]) for axis in range(3)],
                "gyroRadps": [float(data[f"gyro_rad[{axis}]"][index]) for axis in range(3)],
                "baroAltitudeM": float(data["baro_alt_meter"][index]) if "baro_alt_meter" in data else None,
            }
            sensors.append(SensorState(
                f"{platform_id}/imu-0", platform_id, "IMU", "NOMINAL", 5, 0.97, metrics,
                {"mode": "ONBOARD"}, {"adapter": "px4-ulog", "topic": "sensor_combined"},
            ))
            if "baro_alt_meter" in data:
                sensors.append(SensorState(
                    f"{platform_id}/barometer-0", platform_id, "BAROMETER", "NOMINAL", 20, 0.94,
                    {"altitudeM": float(data["baro_alt_meter"][index]),
                     "temperatureC": float(data["baro_temp_celcius"][index]) if "baro_temp_celcius" in data else None},
                    {"mode": "ONBOARD"}, {"adapter": "px4-ulog", "topic": "sensor_combined"},
                ))
        if attitude:
            count = len(attitude.data["timestamp"])
            sensors.append(SensorState(
                f"{platform_id}/attitude-estimator", platform_id, "ATTITUDE", "NOMINAL", 10, 0.96,
                {"sampleCount": count}, {"mode": "FUSED"},
                {"adapter": "px4-ulog", "topic": "vehicle_attitude"},
            ))
        if status:
            data = status.data
            index = len(data["timestamp"]) - 1
            failed = bool(data.get("failsafe", [False])[index]) or bool(data.get("engine_failure", [False])[index])
            sensors.append(SensorState(
                f"{platform_id}/flight-controller", platform_id, "FLIGHT_CONTROLLER",
                "DEGRADED" if failed else "NOMINAL", 100, 0.9,
                {"failsafe": bool(data.get("failsafe", [False])[index]),
                 "engineFailure": bool(data.get("engine_failure", [False])[index]),
                 "dataLinkLost": bool(data.get("data_link_lost", [False])[index])},
                {"mode": "ONBOARD"}, {"adapter": "px4-ulog", "topic": "vehicle_status"},
            ))
        return {
            "available": True, "fileName": self.path.name, "durationSeconds": log.last_timestamp / 1_000_000,
            "dropoutCount": len(log.dropouts), "topics": sorted(topics),
            "sensors": [sensor.to_dict() for sensor in sensors],
        }


def build_situation_snapshot(
    entity: dict[str, Any], opensky_path: str | Path, px4_path: str | Path | None = None
) -> dict[str, Any]:
    platform_id = str(entity.get("entityId") or "unknown-platform")
    telemetry = entity.get("flightTelemetry") if isinstance(entity.get("flightTelemetry"), dict) else {}
    position = entity.get("location", {}).get("position", {})
    telemetry = dict(telemetry)
    telemetry["location"] = {
        "latitudeDegrees": position.get("latitudeDegrees"),
        "longitudeDegrees": position.get("longitudeDegrees"),
        "altitudeMeters": position.get("altitudeMeters") or position.get("altitudeHaeMeters"),
    }
    sensors = telemetry.get("sensorStates") or sensor_states_from_telemetry(platform_id, telemetry)
    snapshot = {
        "platformId": platform_id, "timestampMs": telemetry.get("timestampMs"),
        "platform": {"flightMode": telemetry.get("vehicle", {}).get("flightMode"),
                     "fault": telemetry.get("fault", {}), "sensorCount": len(sensors)},
        "sensors": sensors,
        "externalTargets": OpenSkySampleAdapter(opensky_path).tracks(limit=8),
    }
    if px4_path:
        snapshot["px4Sample"] = Px4UlogSensorAdapter(px4_path).snapshot()
    return snapshot
