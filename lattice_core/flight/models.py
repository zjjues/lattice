from __future__ import annotations

from dataclasses import asdict, dataclass
from math import asin, atan2, copysign, degrees
from typing import Any


@dataclass(frozen=True)
class Quaternion:
    w: float
    x: float
    y: float
    z: float

    def euler_degrees(self) -> tuple[float, float, float]:
        sinr = 2 * (self.w * self.x + self.y * self.z)
        cosr = 1 - 2 * (self.x * self.x + self.y * self.y)
        roll = atan2(sinr, cosr)
        sinp = 2 * (self.w * self.y - self.z * self.x)
        pitch = copysign(3.141592653589793 / 2, sinp) if abs(sinp) >= 1 else asin(sinp)
        siny = 2 * (self.w * self.z + self.x * self.y)
        cosy = 1 - 2 * (self.y * self.y + self.z * self.z)
        return tuple(degrees(value) for value in (roll, pitch, atan2(siny, cosy)))


@dataclass(frozen=True)
class FlightFrame:
    timestamp_ms: int
    source_id: str
    dataset: str
    latitude_deg: float | None = None
    longitude_deg: float | None = None
    altitude_m: float | None = None
    roll_deg: float | None = None
    pitch_deg: float | None = None
    yaw_deg: float | None = None
    quaternion: Quaternion | None = None
    north_velocity_mps: float | None = None
    east_velocity_mps: float | None = None
    down_velocity_mps: float | None = None
    airspeed_mps: float | None = None
    ground_speed_mps: float | None = None
    throttle: float | None = None
    battery_voltage_v: float | None = None
    flight_mode: str | None = None
    fault_active: bool = False
    fault_type: str | None = None
    raw: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.timestamp_ms < 0:
            raise ValueError("timestamp_ms must be non-negative")
        if self.latitude_deg is not None and not -90 <= self.latitude_deg <= 90:
            raise ValueError("latitude_deg is outside [-90, 90]")
        if self.longitude_deg is not None and not -180 <= self.longitude_deg <= 180:
            raise ValueError("longitude_deg is outside [-180, 180]")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
