from __future__ import annotations

import csv
from bisect import bisect_left
from pathlib import Path
from typing import Iterator, Mapping

from .adapters import _first, _float
from .models import FlightFrame, Quaternion


TOPIC_PATTERNS = {
    "attitude": "*vehicle_attitude*.csv",
    "global": "*vehicle_global_position*.csv",
    "local": "*vehicle_local_position*.csv",
    "airspeed": "*airspeed*.csv",
    "battery": "*battery_status*.csv",
    "actuator": "*actuator_outputs*.csv",
}


def _idf_timestamp_ms(row: Mapping[str, str]) -> int:
    milliseconds = _float(row, "timestamp_ms", "time_ms")
    if milliseconds is not None:
        return int(milliseconds)
    microseconds = _float(row, "timestamp", "timestamp_sample", "time_usec", "time_us")
    if microseconds is None:
        raise ValueError("IDF_DS topic row has no timestamp")
    return int(microseconds / 1000)


def _read_topic(path: Path) -> list[tuple[int, dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = [(_idf_timestamp_ms(row), dict(row)) for row in csv.DictReader(handle)]
    rows.sort(key=lambda item: item[0])
    return rows


def _nearest(
    rows: list[tuple[int, dict[str, str]]], timestamp_ms: int, tolerance_ms: int
) -> dict[str, str]:
    if not rows:
        return {}
    timestamps = [item[0] for item in rows]
    index = bisect_left(timestamps, timestamp_ms)
    candidates = rows[max(0, index - 1):min(len(rows), index + 1)]
    nearest = min(candidates, key=lambda item: abs(item[0] - timestamp_ms))
    return nearest[1] if abs(nearest[0] - timestamp_ms) <= tolerance_ms else {}


class IdfDsTopicBundleAdapter:
    """Nearest-neighbour join for a small bundle of raw IDF_DS/PX4 topic CSVs."""

    def __init__(
        self, directory: str | Path, *, source_id: str | None = None,
        tolerance_ms: int = 100,
    ):
        self.directory = Path(directory)
        self.source_id = source_id or self.directory.name
        self.tolerance_ms = tolerance_ms

    def _paths(self) -> dict[str, Path]:
        paths: dict[str, Path] = {}
        for topic, pattern in TOPIC_PATTERNS.items():
            matches = sorted(self.directory.glob(pattern))
            if matches:
                paths[topic] = matches[0]
        if "attitude" not in paths:
            raise ValueError(f"No vehicle_attitude CSV found in {self.directory}")
        return paths

    def frames(self) -> Iterator[FlightFrame]:
        topics = {name: _read_topic(path) for name, path in self._paths().items()}
        for timestamp_ms, attitude in topics["attitude"]:
            rows = {
                name: _nearest(values, timestamp_ms, self.tolerance_ms)
                for name, values in topics.items() if name != "attitude"
            }
            q = Quaternion(
                _float(attitude, "q[0]", "q0") or 0.0,
                _float(attitude, "q[1]", "q1") or 0.0,
                _float(attitude, "q[2]", "q2") or 0.0,
                _float(attitude, "q[3]", "q3") or 0.0,
            )
            roll, pitch, yaw = q.euler_degrees()
            global_position, local, airspeed = rows.get("global", {}), rows.get("local", {}), rows.get("airspeed", {})
            battery, actuator = rows.get("battery", {}), rows.get("actuator", {})
            yield FlightFrame(
                timestamp_ms=timestamp_ms, source_id=self.source_id, dataset="IDF_DS",
                latitude_deg=_float(global_position, "lat", "latitude", "latitude_deg"),
                longitude_deg=_float(global_position, "lon", "longitude", "longitude_deg"),
                altitude_m=_float(global_position, "alt", "altitude", "altitude_m"),
                roll_deg=roll, pitch_deg=pitch, yaw_deg=yaw, quaternion=q,
                north_velocity_mps=_float(local, "vx", "vn"),
                east_velocity_mps=_float(local, "vy", "ve"),
                down_velocity_mps=_float(local, "vz", "vd"),
                airspeed_mps=_float(airspeed, "true_airspeed_m_s", "indicated_airspeed_m_s", "airspeed"),
                throttle=_float(actuator, "output[3]", "control[3]", "throttle"),
                battery_voltage_v=_float(battery, "voltage_v", "voltage_filtered_v"),
                flight_mode=_first(local, "nav_state", "flight_mode"),
                raw={"attitude": attitude, **rows},
            )
