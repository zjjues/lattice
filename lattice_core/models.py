"""跨 API、仿真适配器和智能服务共享的领域类型。

这些 TypedDict 只描述稳定边界，不强迫现有 JSON store 立即迁移。
运行时校验仍由 API/服务层负责，因此旧数据可以继续读取。
"""

from typing import Any, Literal, NotRequired, TypedDict


class GeoPosition(TypedDict):
    latitudeDegrees: float
    longitudeDegrees: float
    altitudeMeters: NotRequired[float]


class Attitude(TypedDict, total=False):
    rollDegrees: float
    pitchDegrees: float
    yawDegrees: float
    frame: Literal["NED", "ENU", "ECEF", "WGS84"]


class Kinematics(TypedDict, total=False):
    groundSpeedMps: float
    airSpeedMps: float
    verticalSpeedMps: float
    headingDegrees: float
    angularVelocityRadps: dict[str, float]


class Track(TypedDict):
    trackId: str
    name: str
    identity: str
    platformType: str
    location: GeoPosition
    speedMps: float
    headingDegrees: float
    altitudeMeters: float
    attitude: NotRequired[Attitude]
    kinematics: NotRequired[Kinematics]


class IngestEvent(TypedDict):
    eventId: str
    sourceType: str
    sourceId: str
    eventType: str
    timestamp: str
    track: Track
    sensorContext: dict[str, Any]
    raw: dict[str, Any]


class Entity(TypedDict, total=False):
    entityId: str
    description: str
    isLive: bool
    createdTime: str
    expiryTime: str
    aliases: dict[str, Any]
    location: dict[str, Any]
    metadata: dict[str, Any]
    provenance: dict[str, Any]


class Alert(TypedDict, total=False):
    alertId: str
    entityId: str
    alertType: str
    riskLevel: str
    title: str
    summary: str
    status: str
    evidence: list[str]
    metadata: dict[str, Any]
    createdAt: str
    updatedAt: str


class Recommendation(TypedDict, total=False):
    recommendationId: str
    alertId: str
    entityId: str
    provider: str
    summary: str
    actions: list[dict[str, Any]]
    references: list[dict[str, Any]]
    createdAt: str


class Task(TypedDict, total=False):
    taskId: str
    entityId: str
    status: str
    taskType: str
    description: str
    createdAt: str
    updatedAt: str
