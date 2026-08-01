from __future__ import annotations

import csv
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterator, Mapping

from .models import FlightFrame, Quaternion


def _first(row: Mapping[str, str], *names: str) -> str | None:
    lookup = {key.strip().lower(): value for key, value in row.items()}
    for name in names:
        value = lookup.get(name.lower())
        if value not in (None, ""):
            return value
    return None


def _float(row: Mapping[str, str], *names: str) -> float | None:
    value = _first(row, *names)
    try:
        return float(value) if value is not None else None
    except ValueError:
        return None


def _timestamp_ms(row: Mapping[str, str]) -> int:
    value = _float(row, "timestamp_ms", "time_ms", "timestamp", "time_usec", "time_us", "time")
    if value is None:
        raise ValueError("CSV row has no supported timestamp column")
    # PX4 timestamps are normally microseconds; Unix seconds may be decimal.
    if value > 10_000_000_000:
        return int(value / 1000)
    if value < 10_000_000:
        return int(value * 1000)
    return int(value)


class CsvFlightAdapter(ABC):
    dataset = "unknown"

    def __init__(self, path: str | Path, source_id: str | None = None):
        self.path = Path(path)
        self.source_id = source_id or self.path.stem

    def frames(self) -> Iterator[FlightFrame]:
        with self.path.open(encoding="utf-8-sig", newline="") as handle:
            for row_number, row in enumerate(csv.DictReader(handle), start=2):
                try:
                    yield self.from_row(row)
                except (TypeError, ValueError) as error:
                    raise ValueError(f"{self.path}:{row_number}: {error}") from error

    @abstractmethod
    def from_row(self, row: Mapping[str, str]) -> FlightFrame: ...

    def _common(self, row: Mapping[str, str]) -> dict:
        q_values = [_float(row, name) for name in ("q0", "q1", "q2", "q3")]
        quaternion = Quaternion(*q_values) if all(value is not None for value in q_values) else None
        roll = _float(row, "roll_deg", "roll", "phi")
        pitch = _float(row, "pitch_deg", "pitch", "theta")
        yaw = _float(row, "yaw_deg", "yaw", "psi", "heading_deg")
        if quaternion and any(value is None for value in (roll, pitch, yaw)):
            q_roll, q_pitch, q_yaw = quaternion.euler_degrees()
            roll, pitch, yaw = roll or q_roll, pitch or q_pitch, yaw or q_yaw
        return {
            "timestamp_ms": _timestamp_ms(row),
            "source_id": self.source_id,
            "dataset": self.dataset,
            "latitude_deg": _float(row, "latitude_deg", "latitude", "lat", "lat_deg"),
            "longitude_deg": _float(row, "longitude_deg", "longitude", "lon", "lng", "lon_deg"),
            "altitude_m": _float(row, "altitude_m", "altitude", "alt", "relative_alt_m"),
            "roll_deg": roll,
            "pitch_deg": pitch,
            "yaw_deg": yaw,
            "quaternion": quaternion,
            "north_velocity_mps": _float(row, "north_velocity_mps", "vn", "vx", "velocity_north"),
            "east_velocity_mps": _float(row, "east_velocity_mps", "ve", "vy", "velocity_east"),
            "down_velocity_mps": _float(row, "down_velocity_mps", "vd", "vz", "velocity_down"),
            "airspeed_mps": _float(row, "airspeed_mps", "airspeed", "true_airspeed_m_s"),
            "ground_speed_mps": _float(row, "ground_speed_mps", "groundspeed", "ground_speed"),
            "throttle": _float(row, "throttle", "throttle_command", "actuator_3"),
            "battery_voltage_v": _float(row, "battery_voltage_v", "voltage_v", "battery_voltage"),
            "flight_mode": _first(row, "flight_mode", "nav_state", "mode"),
            "raw": dict(row),
        }


class IdfDsAdapter(CsvFlightAdapter):
    """Adapter for IDF_DS grouped exports or topic-joined CSV files."""

    dataset = "IDF_DS"

    def from_row(self, row: Mapping[str, str]) -> FlightFrame:
        return FlightFrame(**self._common(row))


class AlfaAdapter(CsvFlightAdapter):
    """Adapter for ALFA processed fixed-wing CSV files."""

    dataset = "ALFA"

    def from_row(self, row: Mapping[str, str]) -> FlightFrame:
        values = self._common(row)
        fault = (_first(row, "fault_active", "failure_active", "fault") or "").strip().lower()
        values.update(
            fault_active=fault in {"1", "true", "yes", "active"},
            fault_type=_first(row, "fault_type", "failure_type", "anomaly_type"),
        )
        return FlightFrame(**values)
