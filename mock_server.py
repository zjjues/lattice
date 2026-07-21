#!/usr/bin/env python3
"""本地 Lattice Entities mock API。"""

import asyncio
import hashlib
import json
import os
import re
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


STORE_PATH = Path("data/entities_store.json")
TASKS_STORE_PATH = Path("data/tasks_store.json")
OBJECTS_STORE_PATH = Path("data/objects_store.json")
ALERTS_STORE_PATH = Path("data/alerts_store.json")
INGEST_EVENTS_STORE_PATH = Path("data/ingest_events_store.json")
RECOMMENDATIONS_STORE_PATH = Path("data/recommendations_store.json")
KB_DIR = Path("kb")
KB_RAW_DIR = KB_DIR / "raw"
OBJECTS_DIR = Path("objects")
STATIC_DIR = Path("static")
MAX_OBJECT_SIZE_BYTES = 20 * 1024 * 1024
RESTRICTED_AREA = {
    "minLat": 31.2200,
    "maxLat": 31.2400,
    "minLon": 121.4600,
    "maxLon": 121.4900,
}
HIGH_SPEED_THRESHOLD_MPS = 18.0
LOITERING_SPEED_THRESHOLD_MPS = 10.0
LOITERING_MIN_SAMPLES = 3
LOITERING_MAX_POSITION_SPAN_DEG = 0.0012
LOITERING_MIN_DURATION_SECONDS = 5
ALLOWED_TASK_STATUSES = {
    "CREATED",
    "ASSIGNED",
    "ACCEPTED",
    "IN_PROGRESS",
    "SUCCEEDED",
    "FAILED",
    "CANCELED",
}
ALLOWED_ALERT_STATUSES = {
    "OPEN",
    "ACKNOWLEDGED",
    "RESOLVED",
    "DISMISSED",
}
DEFAULT_DIFY_TIMEOUT_SECONDS = 75

app = FastAPI(
    title="Local Lattice Entities Mock",
    description="仅用于本地开发的 Lattice Entities mock API。",
    version="0.1.0",
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def utc_now_iso() -> str:
    """返回当前 UTC 时间的 ISO 8601 字符串。"""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class ConnectionManager:
    """管理本地 entity stream 的 WebSocket 连接。"""

    def __init__(self) -> None:
        self.active_connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        """接受客户端连接并加入连接集合。"""
        await websocket.accept()
        async with self._lock:
            self.active_connections.add(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        """移除已经断开的客户端连接。"""
        async with self._lock:
            self.active_connections.discard(websocket)

    async def broadcast(self, message: dict[str, Any]) -> None:
        """向所有已连接客户端广播消息，失败连接会自动移除。"""
        async with self._lock:
            connections = list(self.active_connections)

        disconnected_connections = []
        for websocket in connections:
            try:
                await websocket.send_json(message)
            except Exception:
                # 本地 mock 不打印 payload，避免日志中出现用户测试数据。
                disconnected_connections.append(websocket)

        if disconnected_connections:
            async with self._lock:
                for websocket in disconnected_connections:
                    self.active_connections.discard(websocket)


connection_manager = ConnectionManager()


def ensure_store_file() -> None:
    """确保本地 JSON 存储文件存在。"""
    STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not STORE_PATH.exists():
        write_store({"entities": {}})


def read_store() -> dict[str, Any]:
    """读取本地 entity 存储。"""
    ensure_store_file()
    try:
        with STORE_PATH.open("r", encoding="utf-8") as store_file:
            data = json.load(store_file)
    except json.JSONDecodeError as error:
        raise HTTPException(
            status_code=500,
            detail=f"本地存储文件不是合法 JSON: {STORE_PATH}",
        ) from error

    if not isinstance(data, dict):
        raise HTTPException(status_code=500, detail="本地存储根节点必须是对象")

    entities = data.setdefault("entities", {})
    if not isinstance(entities, dict):
        raise HTTPException(status_code=500, detail="本地存储 entities 必须是对象")

    return data


def write_store(data: dict[str, Any]) -> None:
    """写入本地 entity 存储。"""
    STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with STORE_PATH.open("w", encoding="utf-8") as store_file:
        json.dump(data, store_file, ensure_ascii=False, indent=2)
        store_file.write("\n")


def load_tasks_store() -> dict[str, Any]:
    """读取本地 task 存储，不存在时自动创建。"""
    TASKS_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not TASKS_STORE_PATH.exists():
        save_tasks_store({"tasks": {}})

    try:
        with TASKS_STORE_PATH.open("r", encoding="utf-8") as store_file:
            data = json.load(store_file)
    except json.JSONDecodeError as error:
        raise HTTPException(
            status_code=500,
            detail=f"本地 task 存储文件不是合法 JSON: {TASKS_STORE_PATH}",
        ) from error

    if not isinstance(data, dict):
        raise HTTPException(status_code=500, detail="本地 task 存储根节点必须是对象")

    tasks = data.setdefault("tasks", {})
    if not isinstance(tasks, dict):
        raise HTTPException(status_code=500, detail="本地 task 存储 tasks 必须是对象")

    return data


def save_tasks_store(store: dict[str, Any]) -> None:
    """写入本地 task 存储。"""
    TASKS_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with TASKS_STORE_PATH.open("w", encoding="utf-8") as store_file:
        json.dump(store, store_file, ensure_ascii=False, indent=2)
        store_file.write("\n")


def load_objects_store() -> dict[str, Any]:
    """读取本地 object 存储，不存在时自动创建。"""
    OBJECTS_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    OBJECTS_DIR.mkdir(parents=True, exist_ok=True)
    if not OBJECTS_STORE_PATH.exists():
        save_objects_store({"objects": {}})

    try:
        with OBJECTS_STORE_PATH.open("r", encoding="utf-8") as store_file:
            data = json.load(store_file)
    except json.JSONDecodeError as error:
        raise HTTPException(
            status_code=500,
            detail=f"本地 object 存储文件不是合法 JSON: {OBJECTS_STORE_PATH}",
        ) from error

    if not isinstance(data, dict):
        raise HTTPException(status_code=500, detail="本地 object 存储根节点必须是对象")

    objects = data.setdefault("objects", {})
    if not isinstance(objects, dict):
        raise HTTPException(status_code=500, detail="本地 object 存储 objects 必须是对象")

    return data


def save_objects_store(store: dict[str, Any]) -> None:
    """写入本地 object 存储。"""
    OBJECTS_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OBJECTS_STORE_PATH.open("w", encoding="utf-8") as store_file:
        json.dump(store, store_file, ensure_ascii=False, indent=2)
        store_file.write("\n")


def load_alerts_store() -> dict[str, Any]:
    """读取本地 alert 存储，不存在时自动创建。"""
    ALERTS_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not ALERTS_STORE_PATH.exists():
        save_alerts_store({"alerts": {}})

    try:
        with ALERTS_STORE_PATH.open("r", encoding="utf-8") as store_file:
            data = json.load(store_file)
    except json.JSONDecodeError as error:
        raise HTTPException(
            status_code=500,
            detail=f"本地 alert 存储文件不是合法 JSON: {ALERTS_STORE_PATH}",
        ) from error

    if not isinstance(data, dict):
        raise HTTPException(status_code=500, detail="本地 alert 存储根节点必须是对象")

    alerts = data.setdefault("alerts", {})
    if not isinstance(alerts, dict):
        raise HTTPException(status_code=500, detail="本地 alert 存储 alerts 必须是对象")

    return data


def save_alerts_store(store: dict[str, Any]) -> None:
    """写入本地 alert 存储。"""
    ALERTS_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with ALERTS_STORE_PATH.open("w", encoding="utf-8") as store_file:
        json.dump(store, store_file, ensure_ascii=False, indent=2)
        store_file.write("\n")


def load_ingest_events_store() -> dict[str, Any]:
    """读取本地 ingest 事件存储，不存在时自动创建。"""
    INGEST_EVENTS_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not INGEST_EVENTS_STORE_PATH.exists():
        save_ingest_events_store({"events": {}})

    try:
        with INGEST_EVENTS_STORE_PATH.open("r", encoding="utf-8") as store_file:
            data = json.load(store_file)
    except json.JSONDecodeError as error:
        raise HTTPException(
            status_code=500,
            detail=f"本地 ingest 存储文件不是合法 JSON: {INGEST_EVENTS_STORE_PATH}",
        ) from error

    if not isinstance(data, dict):
        raise HTTPException(status_code=500, detail="本地 ingest 存储根节点必须是对象")

    events = data.setdefault("events", {})
    if not isinstance(events, dict):
        raise HTTPException(status_code=500, detail="本地 ingest 存储 events 必须是对象")

    return data


def save_ingest_events_store(store: dict[str, Any]) -> None:
    """写入本地 ingest 事件存储。"""
    INGEST_EVENTS_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with INGEST_EVENTS_STORE_PATH.open("w", encoding="utf-8") as store_file:
        json.dump(store, store_file, ensure_ascii=False, indent=2)
        store_file.write("\n")


def load_recommendations_store() -> dict[str, Any]:
    """读取本地 recommendation 存储，不存在时自动创建。"""
    RECOMMENDATIONS_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not RECOMMENDATIONS_STORE_PATH.exists():
        save_recommendations_store({"recommendations": {}})

    try:
        with RECOMMENDATIONS_STORE_PATH.open("r", encoding="utf-8") as store_file:
            data = json.load(store_file)
    except json.JSONDecodeError as error:
        raise HTTPException(
            status_code=500,
            detail=f"本地 recommendation 存储文件不是合法 JSON: {RECOMMENDATIONS_STORE_PATH}",
        ) from error

    if not isinstance(data, dict):
        raise HTTPException(status_code=500, detail="本地 recommendation 存储根节点必须是对象")

    recommendations = data.setdefault("recommendations", {})
    if not isinstance(recommendations, dict):
        raise HTTPException(status_code=500, detail="本地 recommendation 存储 recommendations 必须是对象")

    migrated = False
    alerts_store: Optional[dict[str, Any]] = None
    entity_store: Optional[dict[str, Any]] = None
    for recommendation in recommendations.values():
        if not isinstance(recommendation, dict):
            continue
        if isinstance(recommendation.get("stateSignature"), str) and recommendation["stateSignature"]:
            continue
        alert_id = recommendation.get("alertId")
        entity_id = recommendation.get("entityId")
        if not isinstance(alert_id, str) or not isinstance(entity_id, str):
            continue
        if alerts_store is None:
            alerts_store = load_alerts_store()
        if entity_store is None:
            entity_store = read_store()
        alert = alerts_store["alerts"].get(alert_id)
        entity = entity_store["entities"].get(entity_id)
        if not isinstance(alert, dict) or not isinstance(entity, dict):
            continue
        recommendation["stateSignature"] = build_recommendation_state_signature(alert, entity)
        migrated = True

    if migrated:
        save_recommendations_store(data)

    return data


def save_recommendations_store(store: dict[str, Any]) -> None:
    """写入本地 recommendation 存储。"""
    RECOMMENDATIONS_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with RECOMMENDATIONS_STORE_PATH.open("w", encoding="utf-8") as store_file:
        json.dump(store, store_file, ensure_ascii=False, indent=2)
        store_file.write("\n")


def generate_task_id() -> str:
    """生成本地模拟 taskId。"""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    suffix = uuid.uuid4().hex[:6].upper()
    return f"TASK_{timestamp}_{suffix}"


def generate_object_id() -> str:
    """生成本地模拟 objectId。"""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    suffix = uuid.uuid4().hex[:6].upper()
    return f"OBJ_{timestamp}_{suffix}"


def generate_alert_id() -> str:
    """生成本地模拟 alertId。"""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    suffix = uuid.uuid4().hex[:6].upper()
    return f"ALERT_{timestamp}_{suffix}"


def generate_ingest_event_id() -> str:
    """生成本地 ingest event id。"""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    suffix = uuid.uuid4().hex[:6].upper()
    return f"INGEST_{timestamp}_{suffix}"


def generate_recommendation_id() -> str:
    """生成本地 recommendation id。"""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    suffix = uuid.uuid4().hex[:6].upper()
    return f"REC_{timestamp}_{suffix}"


def sanitize_filename(filename: str | None) -> str:
    """清理上传文件名，避免路径穿越和异常字符。"""
    candidate = Path(filename or "").name.strip()
    if not candidate:
        return "uploaded.bin"

    candidate = re.sub(r"[^A-Za-z0-9._-]+", "_", candidate)
    candidate = candidate.strip("._")
    return candidate or "uploaded.bin"


def calculate_sha256(path: Path) -> str:
    """计算本地文件的 sha256。"""
    digest = hashlib.sha256()
    with path.open("rb") as object_file:
        for chunk in iter(lambda: object_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_metadata_json(metadata_text: Optional[str]) -> dict[str, Any]:
    """解析 object metadata 表单字段。"""
    if metadata_text is None or metadata_text == "":
        return {}

    try:
        metadata = json.loads(metadata_text)
    except json.JSONDecodeError as error:
        raise HTTPException(status_code=400, detail="metadata 必须是合法 JSON 字符串") from error

    if not isinstance(metadata, dict):
        raise HTTPException(status_code=400, detail="metadata 必须是 JSON 对象")

    return metadata


def validate_task_status(status: Any) -> str:
    """校验 task 状态是否合法。"""
    if not isinstance(status, str) or not status:
        raise HTTPException(status_code=400, detail="status 必须是非空字符串")

    normalized_status = status.upper()
    if normalized_status not in ALLOWED_TASK_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"status 不合法: {status}",
        )
    return normalized_status


def validate_alert_status(status: Any) -> str:
    """校验 alert 状态是否合法。"""
    if not isinstance(status, str) or not status:
        raise HTTPException(status_code=400, detail="status 必须是非空字符串")

    normalized_status = status.upper()
    if normalized_status not in ALLOWED_ALERT_STATUSES:
        raise HTTPException(status_code=400, detail=f"alert status 不合法: {status}")
    return normalized_status


def build_task(create_payload: Any) -> dict[str, Any]:
    """根据创建请求构建本地 task。"""
    if not isinstance(create_payload, dict):
        raise HTTPException(status_code=400, detail="请求体必须是 JSON 对象")

    task_type = create_payload.get("taskType")
    if not isinstance(task_type, str) or not task_type:
        raise HTTPException(status_code=400, detail="taskType 必须是非空字符串")

    title = create_payload.get("title")
    if not isinstance(title, str) or not title:
        raise HTTPException(status_code=400, detail="title 必须是非空字符串")

    metadata = create_payload.get("metadata", {})
    if metadata is None:
        metadata = {}
    if not isinstance(metadata, dict):
        raise HTTPException(status_code=400, detail="metadata 必须是 JSON 对象")

    now = utc_now_iso()
    return {
        "taskId": generate_task_id(),
        "taskType": task_type,
        "title": title,
        "description": create_payload.get("description", ""),
        "status": "CREATED",
        "priority": create_payload.get("priority", "NORMAL"),
        "relatedEntityId": create_payload.get("relatedEntityId"),
        "assignedAssetId": create_payload.get("assignedAssetId"),
        "resultSummary": None,
        "createdAt": now,
        "updatedAt": now,
        "metadata": metadata,
    }


def build_object_metadata(
    *,
    object_id: str,
    filename: str,
    stored_filename: str,
    content_type: str,
    size_bytes: int,
    sha256: str,
    related_entity_id: Optional[str],
    related_task_id: Optional[str],
    description: Optional[str],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    """构建本地 object metadata。"""
    now = utc_now_iso()
    return {
        "objectId": object_id,
        "filename": filename,
        "storedFilename": stored_filename,
        "contentType": content_type,
        "sizeBytes": size_bytes,
        "sha256": sha256,
        "relatedEntityId": related_entity_id,
        "relatedTaskId": related_task_id,
        "description": description,
        "metadata": metadata,
        "createdAt": now,
        "updatedAt": now,
    }


async def broadcast_task_created(task: dict[str, Any]) -> None:
    """广播 task 创建事件。"""
    await connection_manager.broadcast(
        {
            "type": "task.created",
            "taskId": task["taskId"],
            "task": task,
            "timestamp": utc_now_iso(),
        }
    )


async def broadcast_task_status_updated(task: dict[str, Any]) -> None:
    """广播 task 状态更新事件。"""
    await connection_manager.broadcast(
        {
            "type": "task.status_updated",
            "taskId": task["taskId"],
            "status": task["status"],
            "task": task,
            "timestamp": utc_now_iso(),
        }
    )


async def broadcast_task_deleted(task_id: str) -> None:
    """广播 task 删除事件。"""
    await connection_manager.broadcast(
        {
            "type": "task.deleted",
            "taskId": task_id,
            "timestamp": utc_now_iso(),
        }
    )


async def broadcast_object_created(object_metadata: dict[str, Any]) -> None:
    """广播 object 创建事件。"""
    await connection_manager.broadcast(
        {
            "type": "object.created",
            "objectId": object_metadata["objectId"],
            "object": object_metadata,
            "timestamp": utc_now_iso(),
        }
    )


async def broadcast_object_deleted(object_id: str) -> None:
    """广播 object 删除事件。"""
    await connection_manager.broadcast(
        {
            "type": "object.deleted",
            "objectId": object_id,
            "timestamp": utc_now_iso(),
        }
    )


async def broadcast_alert_created(alert: dict[str, Any]) -> None:
    """广播 alert 创建事件。"""
    await connection_manager.broadcast(
        {
            "type": "alert.created",
            "alertId": alert["alertId"],
            "alert": alert,
            "timestamp": utc_now_iso(),
        }
    )


async def broadcast_alert_updated(alert: dict[str, Any]) -> None:
    """广播 alert 更新事件。"""
    await connection_manager.broadcast(
        {
            "type": "alert.updated",
            "alertId": alert["alertId"],
            "alert": alert,
            "timestamp": utc_now_iso(),
        }
    )


async def broadcast_recommendation_created(recommendation: dict[str, Any]) -> None:
    """广播 recommendation 创建事件。"""
    await connection_manager.broadcast(
        {
            "type": "recommendation.created",
            "recommendationId": recommendation["recommendationId"],
            "recommendation": recommendation,
            "timestamp": utc_now_iso(),
        }
    )


def parse_ingest_event(payload: Any) -> dict[str, Any]:
    """校验并标准化单条 ingest 事件。"""
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="请求体必须是 JSON 对象")

    source_type = payload.get("sourceType")
    source_id = payload.get("sourceId")
    event_type = payload.get("eventType")
    track = payload.get("track")
    sensor_context = payload.get("sensorContext", {})

    if not isinstance(source_type, str) or not source_type:
        raise HTTPException(status_code=400, detail="sourceType 必须是非空字符串")
    if not isinstance(source_id, str) or not source_id:
        raise HTTPException(status_code=400, detail="sourceId 必须是非空字符串")
    if not isinstance(event_type, str) or not event_type:
        raise HTTPException(status_code=400, detail="eventType 必须是非空字符串")
    if not isinstance(track, dict):
        raise HTTPException(status_code=400, detail="track 必须是 JSON 对象")
    if not isinstance(sensor_context, dict):
        raise HTTPException(status_code=400, detail="sensorContext 必须是 JSON 对象")

    track_id = track.get("trackId")
    name = track.get("name") or "Unknown Track"
    location = track.get("location")
    if not isinstance(track_id, str) or not track_id:
        raise HTTPException(status_code=400, detail="track.trackId 必须是非空字符串")
    if not isinstance(location, dict):
        raise HTTPException(status_code=400, detail="track.location 必须是 JSON 对象")

    latitude = location.get("latitudeDegrees")
    longitude = location.get("longitudeDegrees")
    if not isinstance(latitude, (int, float)) or not isinstance(longitude, (int, float)):
        raise HTTPException(status_code=400, detail="track.location 必须包含数值型 latitudeDegrees/longitudeDegrees")
    if latitude < -90 or latitude > 90 or longitude < -180 or longitude > 180:
        raise HTTPException(status_code=400, detail="track.location 经纬度范围不合法")

    altitude = track.get("altitudeMeters", 0)
    speed = track.get("speedMps", 0)
    heading = track.get("headingDegrees", 0)
    confidence = sensor_context.get("confidence", 0.0)
    tags = sensor_context.get("tags", [])
    if not isinstance(tags, list):
        tags = []

    return {
        "eventId": generate_ingest_event_id(),
        "sourceType": source_type,
        "sourceId": source_id,
        "eventType": event_type,
        "timestamp": payload.get("timestamp") if isinstance(payload.get("timestamp"), str) and payload.get("timestamp") else utc_now_iso(),
        "track": {
            "trackId": track_id,
            "name": str(name),
            "identity": str(track.get("identity") or "unknown"),
            "platformType": str(track.get("platformType") or "Unknown"),
            "speedMps": float(speed) if isinstance(speed, (int, float)) else 0.0,
            "headingDegrees": float(heading) if isinstance(heading, (int, float)) else 0.0,
            "altitudeMeters": float(altitude) if isinstance(altitude, (int, float)) else 0.0,
            "location": {
                "latitudeDegrees": float(latitude),
                "longitudeDegrees": float(longitude),
            },
        },
        "sensorContext": {
            "confidence": float(confidence) if isinstance(confidence, (int, float)) else 0.0,
            "zone": sensor_context.get("zone"),
            "tags": tags,
        },
        "raw": payload,
    }


def build_entity_from_ingest_event(event: dict[str, Any]) -> dict[str, Any]:
    """把统一 ingest event 映射为前端可显示的 entity。"""
    track = event["track"]
    latitude = track["location"]["latitudeDegrees"]
    longitude = track["location"]["longitudeDegrees"]
    threat_tags = event["sensorContext"].get("tags", [])
    zone = event["sensorContext"].get("zone")

    return {
        "entityId": track["trackId"],
        "description": f"Simulated {event['sourceType']} track ingested via local API",
        "isLive": True,
        "createdTime": event["timestamp"],
        "expiryTime": utc_now_iso(),
        "aliases": {
            "name": track["name"],
        },
        "milView": {
            "disposition": track["identity"],
            "environment": "air" if str(track["platformType"]).upper() == "UAV" else "surface",
        },
        "location": {
            "position": {
                "latitudeDegrees": latitude,
                "longitudeDegrees": longitude,
                "altitudeMeters": track["altitudeMeters"],
            }
        },
        "ontology": {
            "template": "TEMPLATE_TRACK",
            "platformType": "Air Vehicle" if str(track["platformType"]).upper() == "UAV" else str(track["platformType"]),
            "specificType": str(track["platformType"]),
        },
        "provenance": {
            "source": event["sourceId"],
            "sourceUpdateTime": event["timestamp"],
        },
        "dataClassification": {
            "level": "UNCLASSIFIED",
        },
        "metadata": {
            "sourceType": event["sourceType"],
            "sourceId": event["sourceId"],
            "sensorContext": event["sensorContext"],
            "track": {
                "speedMps": track["speedMps"],
                "headingDegrees": track["headingDegrees"],
                "identity": track["identity"],
                "platformType": track["platformType"],
            },
            "threat": {
                "threatLevel": "LOW",
                "anomalyType": "normal_track",
                "sensorSources": [event["sourceId"]],
                "recommendation": "继续观察目标动态",
                "zone": zone,
                "tags": threat_tags,
            },
        },
    }


def build_alert_from_rule(event: dict[str, Any], entity: dict[str, Any], rule: dict[str, Any]) -> dict[str, Any]:
    """构建本地 alert 对象。"""
    latitude = entity["location"]["position"]["latitudeDegrees"]
    longitude = entity["location"]["position"]["longitudeDegrees"]
    now = utc_now_iso()
    return {
        "alertId": generate_alert_id(),
        "entityId": entity["entityId"],
        "sourceType": event["sourceType"],
        "sourceId": event["sourceId"],
        "alertType": rule["alertType"],
        "riskLevel": rule["riskLevel"],
        "title": rule["title"],
        "summary": rule["summary"],
        "status": "OPEN",
        "location": {
            "latitudeDegrees": latitude,
            "longitudeDegrees": longitude,
        },
        "evidence": rule["evidence"],
        "metadata": {
            "eventId": event["eventId"],
            "zone": event["sensorContext"].get("zone"),
            "speedMps": entity.get("metadata", {}).get("track", {}).get("speedMps"),
            "tags": event["sensorContext"].get("tags", []),
        },
        "createdAt": now,
        "updatedAt": now,
    }


def evaluate_rules(event: dict[str, Any], entity: dict[str, Any]) -> list[dict[str, Any]]:
    """根据当前事件和 entity 生成 alerts。"""
    alerts = []
    position = entity["location"]["position"]
    latitude = position["latitudeDegrees"]
    longitude = position["longitudeDegrees"]
    speed_mps = entity.get("metadata", {}).get("track", {}).get("speedMps", 0.0)
    evidence_common = [
        f"来源: {event['sourceType']} / {event['sourceId']}",
        f"位置: {latitude:.5f}, {longitude:.5f}",
    ]

    if (
        RESTRICTED_AREA["minLat"] <= latitude <= RESTRICTED_AREA["maxLat"]
        and RESTRICTED_AREA["minLon"] <= longitude <= RESTRICTED_AREA["maxLon"]
    ):
        alerts.append(
            {
                "alertType": "restricted_area_intrusion",
                "riskLevel": "HIGH",
                "title": "疑似目标进入警戒区",
                "summary": "目标进入预设警戒区域，建议立即关注并确认身份。",
                "evidence": evidence_common + ["命中规则: restricted area intrusion"],
            }
        )

    if isinstance(speed_mps, (int, float)) and speed_mps >= HIGH_SPEED_THRESHOLD_MPS:
        alerts.append(
            {
                "alertType": "fast_approach",
                "riskLevel": "HIGH",
                "title": "目标高速接近",
                "summary": "目标速度超过阈值，存在快速逼近风险。",
                "evidence": evidence_common + [f"速度 {speed_mps:.1f} m/s 高于阈值 {HIGH_SPEED_THRESHOLD_MPS:.1f} m/s"],
            }
        )

    loitering = detect_loitering(entity["entityId"])
    if loitering is not None:
        alerts.append(
            {
                "alertType": "loitering",
                "riskLevel": "MEDIUM",
                "title": "目标疑似盘旋滞留",
                "summary": "目标在有限区域内持续低速活动，建议关注其观察或滞留意图。",
                "evidence": evidence_common
                + [
                    f"最近 {loitering['sampleCount']} 个点位范围较小",
                    f"持续时间约 {loitering['durationSeconds']:.1f} 秒",
                    f"最大速度 {loitering['maxSpeedMps']:.1f} m/s",
                ],
            }
        )

    return alerts


def update_entity_threat_from_alerts(entity: dict[str, Any], alert_candidates: list[dict[str, Any]]) -> dict[str, Any]:
    """把命中的规则回填到 entity threat 字段，便于现有前端复用。"""
    metadata = entity.setdefault("metadata", {})
    threat = metadata.setdefault("threat", {})

    if not alert_candidates:
        threat["threatLevel"] = "LOW"
        threat["anomalyType"] = "normal_track"
        threat["recommendation"] = "继续观察目标动态"
        return entity

    highest = next(
        (candidate for candidate in alert_candidates if candidate["riskLevel"] == "HIGH"),
        alert_candidates[0],
    )
    threat["threatLevel"] = highest["riskLevel"]
    threat["anomalyType"] = highest["alertType"]
    threat["recommendation"] = highest["summary"]
    return entity


def find_active_alert(existing_alerts: dict[str, Any], entity_id: str, alert_type: str) -> Optional[dict[str, Any]]:
    """查找同一实体/同一类型的活跃 alert。"""
    for alert in existing_alerts.values():
        if (
            isinstance(alert, dict)
            and alert.get("entityId") == entity_id
            and alert.get("alertType") == alert_type
            and alert.get("status") in {"OPEN", "ACKNOWLEDGED"}
        ):
            return alert
    return None


def timestamp_sort_key(item: dict[str, Any], key: str) -> str:
    """提取可用于降序排序的时间字符串键。"""
    value = item.get(key)
    if isinstance(value, str):
        return value
    return ""


def get_dify_settings() -> dict[str, Any]:
    """读取 Dify 相关配置。"""
    base_url = os.environ.get("DIFY_BASE_URL", "").strip().rstrip("/")
    api_key = os.environ.get("DIFY_API_KEY", "").strip()
    app_mode = os.environ.get("DIFY_APP_MODE", "workflow").strip().lower() or "workflow"
    user = os.environ.get("DIFY_USER", "fake-lattice-local").strip() or "fake-lattice-local"
    return {
        "enabled": bool(base_url and api_key),
        "baseUrl": base_url,
        "apiKey": api_key,
        "appMode": app_mode,
        "user": user,
    }


def build_recommendation_context(alert: dict[str, Any], entity: dict[str, Any]) -> dict[str, Any]:
    """构造 recommendation 输入上下文。"""
    track = entity.get("metadata", {}).get("track", {})
    threat = entity.get("metadata", {}).get("threat", {})
    position = entity.get("location", {}).get("position", {})
    return {
        "alert": {
            "alertId": alert.get("alertId"),
            "alertType": alert.get("alertType"),
            "riskLevel": alert.get("riskLevel"),
            "title": alert.get("title"),
            "summary": alert.get("summary"),
            "evidence": alert.get("evidence", []),
        },
        "entity": {
            "entityId": entity.get("entityId"),
            "name": entity.get("aliases", {}).get("name"),
            "platformType": entity.get("ontology", {}).get("specificType"),
            "environment": entity.get("milView", {}).get("environment"),
            "speedMps": track.get("speedMps"),
            "headingDegrees": track.get("headingDegrees"),
            "identity": track.get("identity"),
            "location": {
                "latitudeDegrees": position.get("latitudeDegrees"),
                "longitudeDegrees": position.get("longitudeDegrees"),
                "altitudeMeters": position.get("altitudeMeters"),
            },
        },
        "threat": threat,
        "knowledge": [],
    }


def build_dify_recommendation_inputs(context: dict[str, Any]) -> dict[str, str]:
    """把 recommendation 上下文整理成 Dify 适配层输入。"""
    alert = context.get("alert", {}) if isinstance(context.get("alert"), dict) else {}
    entity = context.get("entity", {}) if isinstance(context.get("entity"), dict) else {}
    knowledge = context.get("knowledge", []) if isinstance(context.get("knowledge"), list) else []
    threat = context.get("threat", {}) if isinstance(context.get("threat"), dict) else {}
    return {
        "context_json": json.dumps(context, ensure_ascii=False),
        "alert_json": json.dumps(alert, ensure_ascii=False),
        "entity_json": json.dumps(entity, ensure_ascii=False),
        "knowledge_json": json.dumps(knowledge, ensure_ascii=False),
        "threat_json": json.dumps(threat, ensure_ascii=False),
        "state_signature": build_recommendation_state_signature_from_context(context),
    }


def build_recommendation_state_signature_from_context(context: dict[str, Any]) -> str:
    """从上下文构造 recommendation 状态签名。"""
    snapshot = {
        "alert": context.get("alert") if isinstance(context.get("alert"), dict) else {},
        "entity": context.get("entity") if isinstance(context.get("entity"), dict) else {},
        "threat": context.get("threat") if isinstance(context.get("threat"), dict) else {},
    }
    canonical = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_recommendation_state_signature(alert: dict[str, Any], entity: dict[str, Any]) -> str:
    """构造 recommendation 去重用的状态签名。"""
    metadata = entity.get("metadata", {}) if isinstance(entity.get("metadata"), dict) else {}
    track = metadata.get("track", {}) if isinstance(metadata.get("track"), dict) else {}
    threat = metadata.get("threat", {}) if isinstance(metadata.get("threat"), dict) else {}
    position = entity.get("location", {}).get("position", {}) if isinstance(entity.get("location"), dict) else {}
    alert_metadata = alert.get("metadata", {}) if isinstance(alert.get("metadata"), dict) else {}
    snapshot = {
        "alert": {
            "alertId": alert.get("alertId"),
            "alertType": alert.get("alertType"),
            "riskLevel": alert.get("riskLevel"),
            "title": alert.get("title"),
            "summary": alert.get("summary"),
            "status": alert.get("status"),
            "evidence": [item for item in alert.get("evidence", []) if isinstance(item, str)],
            "zone": alert_metadata.get("zone"),
            "speedMps": alert_metadata.get("speedMps"),
            "tags": alert_metadata.get("tags", []),
            "operatorNote": alert_metadata.get("operatorNote"),
        },
        "entity": {
            "entityId": entity.get("entityId"),
            "specificType": entity.get("ontology", {}).get("specificType"),
            "environment": entity.get("milView", {}).get("environment"),
            "location": {
                "latitudeDegrees": position.get("latitudeDegrees"),
                "longitudeDegrees": position.get("longitudeDegrees"),
                "altitudeMeters": position.get("altitudeMeters"),
            },
            "track": {
                "speedMps": track.get("speedMps"),
                "headingDegrees": track.get("headingDegrees"),
                "identity": track.get("identity"),
            },
            "threat": {
                "threatLevel": threat.get("threatLevel"),
                "anomalyType": threat.get("anomalyType"),
                "recommendation": threat.get("recommendation"),
                "zone": threat.get("zone"),
                "tags": threat.get("tags", []),
            },
        },
    }
    canonical = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_local_recommendation_payload(context: dict[str, Any]) -> dict[str, Any]:
    """在未配置 Dify 时生成本地回退 recommendation。"""
    alert = context["alert"]
    entity = context["entity"]
    alert_type = alert.get("alertType")
    risk_level = alert.get("riskLevel", "MEDIUM")
    platform_type = entity.get("platformType") or "目标"
    speed_mps = entity.get("speedMps")
    knowledge = context.get("knowledge", [])
    knowledge_references = [
        {"docId": item.get("docId"), "title": item.get("title")}
        for item in knowledge[:3]
        if isinstance(item, dict)
    ]

    if alert_type == "restricted_area_intrusion":
        summary = "建议立即持续跟踪目标，并调用附近光电或无人机资源进行二次确认。"
        actions = [
            "持续跟踪目标当前位置与航向变化",
            "调度附近传感器对目标进行二次确认",
            "通知值班人员人工复核目标身份与意图",
        ]
        recommended_asset_types = ["EO_SENSOR", "UAV", "OPERATOR"]
        references = knowledge_references or [
            {"docId": "LOCAL-SOP-UAV-001", "title": "无人机进入警戒区处置预案"},
        ]
        confidence = 0.82
    elif alert_type == "fast_approach":
        summary = f"建议重点关注高速接近的{platform_type}目标，优先确认其轨迹意图。"
        actions = [
            "观察速度和航向是否持续指向敏感区域",
            "结合相邻传感器继续确认目标性质",
            "准备创建侦察或跟踪任务",
        ]
        recommended_asset_types = ["RADAR", "EO_SENSOR", "OPERATOR"]
        references = knowledge_references or [
            {"docId": "LOCAL-SOP-UAV-002", "title": "高速接近目标研判指引"},
        ]
        confidence = 0.76
    elif alert_type == "loitering":
        summary = f"建议持续观察盘旋滞留的{platform_type}目标，并结合周边敏感区域判断其观察意图。"
        actions = [
            "持续跟踪目标在小范围内的活动轨迹",
            "调用附近传感器补充身份与载荷信息",
            "由值班人员判断是否升级为侦察或驱离任务",
        ]
        recommended_asset_types = ["EO_SENSOR", "RADAR", "OPERATOR"]
        references = knowledge_references or [
            {"docId": "SOP_LOITERING_001", "title": "低空目标盘旋滞留处置指引"},
        ]
        confidence = 0.73
    else:
        summary = "建议保持监视，并根据后续告警变化决定是否下发任务。"
        actions = [
            "继续观察目标动态",
            "记录目标位置信息和传感器证据",
        ]
        recommended_asset_types = ["OPERATOR"]
        references = knowledge_references or [
            {"docId": "LOCAL-SOP-GENERIC-001", "title": "通用异常目标处置指引"},
        ]
        confidence = 0.65

    if isinstance(speed_mps, (int, float)) and speed_mps > HIGH_SPEED_THRESHOLD_MPS:
        actions.insert(0, f"目标当前速度约 {speed_mps:.1f} m/s，优先评估快速逼近风险")

    return {
        "summary": summary,
        "riskLevel": risk_level,
        "actions": actions,
        "recommendedAssetTypes": recommended_asset_types,
        "confidence": confidence,
        "references": references,
    }


def parse_json_object(raw_text: str, error_detail: str) -> dict[str, Any]:
    """解析 JSON 对象。"""
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as error:
        raise HTTPException(status_code=502, detail=error_detail) from error
    if not isinstance(data, dict):
        raise HTTPException(status_code=502, detail=error_detail)
    return data


def build_dify_prompt(context: dict[str, Any]) -> str:
    """构造给 Dify 的简要指令。"""
    return (
        "你是一个安防/低空监控指挥辅助系统。"
        "请基于 inputs 中的告警、目标、知识库内容，输出结构化处置建议。"
        "输出必须是 JSON 对象，且只包含 summary, riskLevel, actions, recommendedAssetTypes, confidence, references 这 6 个字段。"
    )


def extract_dify_text(response_payload: dict[str, Any]) -> str:
    """兼容不同 Dify 应用模式，提取文本输出。"""
    if isinstance(response_payload.get("answer"), str) and response_payload.get("answer"):
        return response_payload["answer"]

    data = response_payload.get("data")
    if isinstance(data, dict):
        outputs = data.get("outputs")
        if isinstance(outputs, dict):
            for candidate_key in ("text", "answer", "result", "output", "json"):
                candidate = outputs.get(candidate_key)
                if isinstance(candidate, str) and candidate.strip():
                    return candidate
                if isinstance(candidate, dict):
                    return json.dumps(candidate, ensure_ascii=False)
        for candidate_key in ("text", "answer"):
            candidate = data.get(candidate_key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate
    return ""


def call_dify_recommendation(context: dict[str, Any]) -> dict[str, Any]:
    """调用 Dify 生成 recommendation，失败时回退到本地规则模板。"""
    settings = get_dify_settings()
    fallback = build_local_recommendation_payload(context)
    dify_inputs = build_dify_recommendation_inputs(context)
    if not settings["enabled"]:
        return {
            **fallback,
            "provider": "local-fallback",
            "providerMetadata": {"reason": "Dify not configured"},
        }

    if settings["appMode"] == "chat":
        endpoint = f"{settings['baseUrl']}/v1/chat-messages"
        request_payload = {
            "inputs": dify_inputs,
            "query": build_dify_prompt(context),
            "response_mode": "blocking",
            "user": settings["user"],
        }
    else:
        endpoint = f"{settings['baseUrl']}/v1/workflows/run"
        request_payload = {
            "inputs": dify_inputs,
            "response_mode": "blocking",
            "user": settings["user"],
        }

    request_body = json.dumps(request_payload).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=request_body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings['apiKey']}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=DEFAULT_DIFY_TIMEOUT_SECONDS) as response:
            response_payload = parse_json_object(
                response.read().decode("utf-8"),
                "Dify 返回的不是合法 JSON 对象",
            )
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        return {
            **fallback,
            "provider": "local-fallback",
            "providerMetadata": {
                "reason": "Dify HTTPError",
                "statusCode": error.code,
                "detail": detail[:500],
            },
        }
    except urllib.error.URLError as error:
        return {
            **fallback,
            "provider": "local-fallback",
            "providerMetadata": {"reason": "Dify URLError", "detail": str(error)},
        }

    output_text = extract_dify_text(response_payload)
    if not output_text:
        return {
            **fallback,
            "provider": "local-fallback",
            "providerMetadata": {
                "reason": "Dify response missing text output",
                "rawResponse": response_payload,
            },
        }

    parsed_output = None
    try:
        parsed_output = json.loads(output_text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", output_text, re.DOTALL)
        if match:
            try:
                parsed_output = json.loads(match.group(0))
            except json.JSONDecodeError:
                parsed_output = None

    if not isinstance(parsed_output, dict):
        return {
            **fallback,
            "provider": "local-fallback",
            "providerMetadata": {
                "reason": "Dify output not parseable JSON",
                "rawOutput": output_text[:1000],
            },
        }

    return {
        "summary": parsed_output.get("summary") if isinstance(parsed_output.get("summary"), str) else fallback["summary"],
        "riskLevel": parsed_output.get("riskLevel") if isinstance(parsed_output.get("riskLevel"), str) else fallback["riskLevel"],
        "actions": parsed_output.get("actions") if isinstance(parsed_output.get("actions"), list) and parsed_output.get("actions") else fallback["actions"],
        "recommendedAssetTypes": (
            parsed_output.get("recommendedAssetTypes")
            if isinstance(parsed_output.get("recommendedAssetTypes"), list) and parsed_output.get("recommendedAssetTypes")
            else fallback["recommendedAssetTypes"]
        ),
        "confidence": (
            float(parsed_output.get("confidence"))
            if isinstance(parsed_output.get("confidence"), (int, float))
            else fallback["confidence"]
        ),
        "references": parsed_output.get("references") if isinstance(parsed_output.get("references"), list) else fallback["references"],
        "provider": "dify",
        "providerMetadata": {
            "appMode": settings["appMode"],
        },
    }


def build_recommendation_record(
    alert: dict[str, Any],
    entity: dict[str, Any],
    generated: dict[str, Any],
    *,
    state_signature: str,
) -> dict[str, Any]:
    """构造 recommendation 持久化记录。"""
    now = utc_now_iso()
    return {
        "recommendationId": generate_recommendation_id(),
        "alertId": alert["alertId"],
        "entityId": entity["entityId"],
        "stateSignature": state_signature,
        "summary": generated["summary"],
        "riskLevel": generated["riskLevel"],
        "actions": generated["actions"],
        "recommendedAssetTypes": generated["recommendedAssetTypes"],
        "confidence": generated["confidence"],
        "references": generated["references"],
        "provider": generated.get("provider", "local-fallback"),
        "providerMetadata": generated.get("providerMetadata", {}),
        "status": "GENERATED",
        "createdAt": now,
        "updatedAt": now,
    }


def load_knowledge_documents() -> list[dict[str, Any]]:
    """加载本地知识库原始文档。"""
    KB_RAW_DIR.mkdir(parents=True, exist_ok=True)
    documents = []
    for path in sorted(KB_RAW_DIR.glob("*.json")):
        try:
            with path.open("r", encoding="utf-8") as input_file:
                payload = json.load(input_file)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            payload = [payload]
        if not isinstance(payload, list):
            continue
        for item in payload:
            if not isinstance(item, dict):
                continue
            if not isinstance(item.get("docId"), str) or not isinstance(item.get("title"), str):
                continue
            documents.append(item)
    return documents


def tokenize_text(value: str) -> list[str]:
    """把文本切成简单 token，兼容英文和数字。"""
    return [token for token in re.split(r"[^A-Za-z0-9_\u4e00-\u9fff]+", value.lower()) if token]


def search_local_knowledge_base(query: str, *, limit: int = 5, context: Optional[dict[str, Any]] = None) -> list[dict[str, Any]]:
    """执行本地轻量知识库检索。"""
    documents = load_knowledge_documents()
    query_tokens = set(tokenize_text(query))
    if context:
        context_tokens = set(tokenize_text(json.dumps(context, ensure_ascii=False)))
        query_tokens.update(context_tokens)

    if not query_tokens:
        query_tokens = {"uav", "目标", "处置"}

    results = []
    for document in documents:
        title = str(document.get("title", ""))
        summary = str(document.get("summary", ""))
        content = str(document.get("content", ""))
        tags = document.get("tags", [])
        joined_tags = " ".join(str(tag) for tag in tags if isinstance(tag, str))
        indexed_text = " ".join([title, summary, content, joined_tags]).lower()
        tokens = set(tokenize_text(indexed_text))
        overlap = query_tokens.intersection(tokens)
        if not overlap:
            continue

        score = len(overlap)
        if document.get("docType") == "SOP":
            score += 1
        excerpt = summary or content[:180]
        results.append(
            {
                "docId": document["docId"],
                "title": title,
                "docType": document.get("docType", "DOC"),
                "tags": tags if isinstance(tags, list) else [],
                "summary": summary,
                "excerpt": excerpt[:240],
                "score": score,
            }
        )

    results.sort(key=lambda item: (item["score"], item["docType"] == "SOP"), reverse=True)
    return results[: max(1, min(limit, 10))]


def parse_iso_timestamp(value: Any) -> Optional[datetime]:
    """解析 ISO 时间字符串。"""
    if not isinstance(value, str) or not value:
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def get_recent_events_for_track(track_id: str, *, limit: int = 5) -> list[dict[str, Any]]:
    """获取同一 track 最近的 ingest 事件。"""
    store = load_ingest_events_store()
    events = []
    for event in store.get("events", {}).values():
        if not isinstance(event, dict):
            continue
        track = event.get("track")
        if not isinstance(track, dict):
            continue
        if track.get("trackId") != track_id:
            continue
        events.append(event)

    events.sort(
        key=lambda item: parse_iso_timestamp(item.get("timestamp")) or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    return events[:limit]


def build_track_history(track_id: str, *, limit: int = 20) -> list[dict[str, Any]]:
    """把 ingest 事件转换为前端可渲染的轨迹历史点。"""
    events = list(reversed(get_recent_events_for_track(track_id, limit=limit)))
    history = []
    for event in events:
        track = event.get("track", {})
        location = track.get("location", {})
        latitude = location.get("latitudeDegrees")
        longitude = location.get("longitudeDegrees")
        if not isinstance(latitude, (int, float)) or not isinstance(longitude, (int, float)):
            continue
        history.append(
            {
                "eventId": event.get("eventId"),
                "timestamp": event.get("timestamp"),
                "latitudeDegrees": float(latitude),
                "longitudeDegrees": float(longitude),
                "speedMps": track.get("speedMps"),
                "headingDegrees": track.get("headingDegrees"),
            }
        )
    return history


def detect_loitering(track_id: str) -> Optional[dict[str, Any]]:
    """基于最近几条轨迹点检测盘旋/滞留。"""
    recent_events = get_recent_events_for_track(track_id, limit=max(LOITERING_MIN_SAMPLES, 5))
    if len(recent_events) < LOITERING_MIN_SAMPLES:
        return None

    sample_events = list(reversed(recent_events[:LOITERING_MIN_SAMPLES]))
    latitudes = []
    longitudes = []
    speeds = []
    timestamps = []

    for event in sample_events:
        track = event.get("track", {})
        location = track.get("location", {})
        latitude = location.get("latitudeDegrees")
        longitude = location.get("longitudeDegrees")
        speed = track.get("speedMps")
        timestamp = parse_iso_timestamp(event.get("timestamp"))
        if not isinstance(latitude, (int, float)) or not isinstance(longitude, (int, float)):
            return None
        if not isinstance(speed, (int, float)):
            return None
        if timestamp is None:
            return None
        latitudes.append(float(latitude))
        longitudes.append(float(longitude))
        speeds.append(float(speed))
        timestamps.append(timestamp)

    lat_span = max(latitudes) - min(latitudes)
    lon_span = max(longitudes) - min(longitudes)
    max_speed = max(speeds)
    duration_seconds = (timestamps[-1] - timestamps[0]).total_seconds()

    if (
        lat_span <= LOITERING_MAX_POSITION_SPAN_DEG
        and lon_span <= LOITERING_MAX_POSITION_SPAN_DEG
        and max_speed <= LOITERING_SPEED_THRESHOLD_MPS
        and duration_seconds >= LOITERING_MIN_DURATION_SECONDS
    ):
        return {
            "latSpan": lat_span,
            "lonSpan": lon_span,
            "maxSpeedMps": max_speed,
            "durationSeconds": duration_seconds,
            "sampleCount": len(sample_events),
        }

    return None


def normalize_entities(payload: Any) -> list[dict[str, Any]]:
    """把请求体统一转换为 entity 列表并校验 entityId。"""
    if isinstance(payload, dict):
        entities = [payload]
    elif isinstance(payload, list):
        entities = payload
    else:
        raise HTTPException(
            status_code=400,
            detail="请求体必须是单个 entity JSON 对象或 entity JSON 数组",
        )

    normalized_entities = []
    for index, entity in enumerate(entities):
        if not isinstance(entity, dict):
            raise HTTPException(
                status_code=400,
                detail=f"第 {index} 个 entity 必须是 JSON 对象",
            )

        entity_id = entity.get("entityId")
        if not entity_id:
            raise HTTPException(
                status_code=400,
                detail=f"第 {index} 个 entity 缺少 entityId",
            )

        normalized_entities.append(entity)

    return normalized_entities


@app.on_event("startup")
def startup() -> None:
    """服务启动时初始化本地存储文件。"""
    ensure_store_file()
    load_tasks_store()
    load_objects_store()
    load_alerts_store()
    load_ingest_events_store()
    load_recommendations_store()


@app.get("/health")
def health() -> dict[str, str]:
    """返回本地 mock 服务状态。"""
    return {
        "status": "ok",
        "service": "local-lattice-entities-mock",
    }


@app.get("/api/v1/config/map-overlays")
def get_map_overlays() -> dict[str, Any]:
    """返回前端需要绘制的本地覆盖层配置。"""
    return {
        "restrictedArea": {
            "id": "restricted-area-primary",
            "name": "Primary Restricted Area",
            "minLat": RESTRICTED_AREA["minLat"],
            "maxLat": RESTRICTED_AREA["maxLat"],
            "minLon": RESTRICTED_AREA["minLon"],
            "maxLon": RESTRICTED_AREA["maxLon"],
        }
    }


@app.post("/api/v1/oauth/token")
async def create_oauth_token(request: Request) -> dict[str, Any]:
    """返回本地 fake OAuth token，方便演示认证到业务 API 的完整链路。"""
    content_type = request.headers.get("content-type", "")
    payload: dict[str, Any] = {}

    if "application/json" in content_type:
        try:
            raw_payload = await request.json()
        except json.JSONDecodeError as error:
            raise HTTPException(status_code=400, detail="请求体必须是合法 JSON") from error
        if not isinstance(raw_payload, dict):
            raise HTTPException(status_code=400, detail="请求体必须是 JSON 对象")
        payload = raw_payload
    elif "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
        form = await request.form()
        payload = dict(form)

    now = utc_now_iso()
    return {
        "access_token": "fake_lattice_token",
        "token_type": "Bearer",
        "expires_in": 3600,
        "scope": payload.get("scope", "entities tasks objects"),
        "issued_at": now,
    }


@app.get("/")
def index() -> FileResponse:
    """返回本地地图 UI 页面。"""
    return FileResponse(STATIC_DIR / "index.html")


@app.put("/api/v1/entities")
async def upsert_entities(request: Request) -> dict[str, Any]:
    """接收单个 entity 或 entity 数组，并按 entityId upsert 到本地文件。"""
    try:
        payload = await request.json()
    except json.JSONDecodeError as error:
        raise HTTPException(status_code=400, detail="请求体必须是合法 JSON") from error

    incoming_entities = normalize_entities(payload)
    store = read_store()
    stored_entities = store["entities"]

    entity_ids = []
    for entity in incoming_entities:
        entity_id = str(entity["entityId"])
        stored_entities[entity_id] = entity
        entity_ids.append(entity_id)

    write_store(store)
    for entity in incoming_entities:
        entity_id = str(entity["entityId"])
        await connection_manager.broadcast(
            {
                "type": "entity.upserted",
                "entityId": entity_id,
                "entity": entity,
                "timestamp": utc_now_iso(),
            }
        )

    return {
        "upserted": len(entity_ids),
        "entityIds": entity_ids,
    }


@app.post("/api/v1/ingest/events")
async def ingest_event(request: Request) -> dict[str, Any]:
    """接收模拟传感器/无人机事件，映射成 entity 并触发本地告警规则。"""
    try:
        payload = await request.json()
    except json.JSONDecodeError as error:
        raise HTTPException(status_code=400, detail="请求体必须是合法 JSON") from error

    event = parse_ingest_event(payload)
    ingest_store = load_ingest_events_store()
    ingest_store["events"][event["eventId"]] = event
    save_ingest_events_store(ingest_store)

    entity = build_entity_from_ingest_event(event)
    alert_candidates = evaluate_rules(event, entity)
    entity = update_entity_threat_from_alerts(entity, alert_candidates)

    entity_store = read_store()
    entity_store["entities"][entity["entityId"]] = entity
    write_store(entity_store)
    await connection_manager.broadcast(
        {
            "type": "entity.upserted",
            "entityId": entity["entityId"],
            "entity": entity,
            "timestamp": utc_now_iso(),
        }
    )

    created_or_updated_alert_ids: list[str] = []
    alerts_store = load_alerts_store()
    for rule in alert_candidates:
        existing_alert = find_active_alert(alerts_store["alerts"], entity["entityId"], rule["alertType"])
        if existing_alert is None:
            alert = build_alert_from_rule(event, entity, rule)
            alerts_store["alerts"][alert["alertId"]] = alert
            created_or_updated_alert_ids.append(alert["alertId"])
            await broadcast_alert_created(alert)
            continue

        existing_alert["riskLevel"] = rule["riskLevel"]
        existing_alert["title"] = rule["title"]
        existing_alert["summary"] = rule["summary"]
        existing_alert["location"] = {
            "latitudeDegrees": entity["location"]["position"]["latitudeDegrees"],
            "longitudeDegrees": entity["location"]["position"]["longitudeDegrees"],
        }
        existing_alert["evidence"] = rule["evidence"]
        existing_alert["metadata"] = {
            **(existing_alert.get("metadata") if isinstance(existing_alert.get("metadata"), dict) else {}),
            "eventId": event["eventId"],
            "zone": event["sensorContext"].get("zone"),
            "speedMps": entity.get("metadata", {}).get("track", {}).get("speedMps"),
            "tags": event["sensorContext"].get("tags", []),
        }
        existing_alert["updatedAt"] = utc_now_iso()
        created_or_updated_alert_ids.append(existing_alert["alertId"])
        await broadcast_alert_updated(existing_alert)

    save_alerts_store(alerts_store)

    return {
        "ok": True,
        "eventId": event["eventId"],
        "entityId": entity["entityId"],
        "alertsCreated": created_or_updated_alert_ids,
    }


@app.get("/api/v1/entities")
def list_entities() -> dict[str, Any]:
    """返回当前保存的所有 entities。"""
    store = read_store()
    entities = list(store["entities"].values())
    return {
        "count": len(entities),
        "entities": entities,
    }


@app.get("/api/v1/entities/{entity_id}")
def get_entity(entity_id: str) -> dict[str, Any]:
    """返回指定 entity。"""
    store = read_store()
    entity = store["entities"].get(entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail=f"entity 不存在: {entity_id}")
    return entity


@app.get("/api/v1/tracks/{track_id}/history")
def get_track_history(track_id: str, limit: int = 20) -> dict[str, Any]:
    """返回指定目标最近的轨迹历史点。"""
    normalized_limit = max(1, min(limit, 100))
    history = build_track_history(track_id, limit=normalized_limit)
    return {
        "trackId": track_id,
        "count": len(history),
        "history": history,
    }


@app.get("/api/v1/alerts")
def list_alerts(
    status: Optional[str] = None,
    relatedEntityId: Optional[str] = None,
) -> dict[str, Any]:
    """返回本地保存的 alerts。"""
    store = load_alerts_store()
    alerts = list(store["alerts"].values())

    if status is not None:
        normalized_status = validate_alert_status(status)
        alerts = [alert for alert in alerts if alert.get("status") == normalized_status]

    if relatedEntityId is not None:
        alerts = [alert for alert in alerts if alert.get("entityId") == relatedEntityId]

    alerts = sorted(alerts, key=lambda item: timestamp_sort_key(item, "updatedAt"), reverse=True)

    return {
        "count": len(alerts),
        "alerts": alerts,
    }


@app.get("/api/v1/alerts/{alert_id}")
def get_alert(alert_id: str) -> dict[str, Any]:
    """返回指定 alert。"""
    store = load_alerts_store()
    alert = store["alerts"].get(alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail=f"alert 不存在: {alert_id}")
    return alert


@app.patch("/api/v1/alerts/{alert_id}")
async def update_alert(alert_id: str, request: Request) -> dict[str, Any]:
    """更新指定 alert 状态或操作员备注。"""
    try:
        payload = await request.json()
    except json.JSONDecodeError as error:
        raise HTTPException(status_code=400, detail="请求体必须是合法 JSON") from error

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="请求体必须是 JSON 对象")

    store = load_alerts_store()
    alert = store["alerts"].get(alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail=f"alert 不存在: {alert_id}")

    if "status" in payload:
        alert["status"] = validate_alert_status(payload.get("status"))

    if "operatorNote" in payload:
        operator_note = payload.get("operatorNote")
        if operator_note is not None and not isinstance(operator_note, str):
            raise HTTPException(status_code=400, detail="operatorNote 必须是字符串")
        metadata = alert.setdefault("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}
            alert["metadata"] = metadata
        metadata["operatorNote"] = operator_note

    alert["updatedAt"] = utc_now_iso()
    save_alerts_store(store)
    await broadcast_alert_updated(alert)
    return alert


@app.post("/api/v1/alerts/{alert_id}/recommendation")
async def create_recommendation_for_alert(alert_id: str) -> dict[str, Any]:
    """基于 alert 和 entity 生成 recommendation。"""
    alerts_store = load_alerts_store()
    alert = alerts_store["alerts"].get(alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail=f"alert 不存在: {alert_id}")

    entity_store = read_store()
    entity = entity_store["entities"].get(alert.get("entityId"))
    if entity is None:
        raise HTTPException(status_code=404, detail=f"关联 entity 不存在: {alert.get('entityId')}")

    context = build_recommendation_context(alert, entity)
    state_signature = build_recommendation_state_signature(alert, entity)
    recommendations_store = load_recommendations_store()
    existing_recommendations = [
        item
        for item in recommendations_store["recommendations"].values()
        if isinstance(item, dict) and item.get("alertId") == alert_id
    ]
    existing_recommendation = next(
        (
            item
            for item in sorted(
                existing_recommendations,
                key=lambda item: timestamp_sort_key(item, "updatedAt"),
                reverse=True,
            )
            if item.get("stateSignature") == state_signature
        ),
        None,
    )
    if existing_recommendation is not None:
        metadata = alert.setdefault("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}
            alert["metadata"] = metadata
        if metadata.get("latestRecommendationId") != existing_recommendation["recommendationId"]:
            metadata["latestRecommendationId"] = existing_recommendation["recommendationId"]
            save_alerts_store(alerts_store)
            await broadcast_alert_updated(alert)
        return {
            "recommendationId": existing_recommendation["recommendationId"],
            "recommendation": existing_recommendation,
            "reused": True,
        }

    kb_query = " ".join(
        [
            str(alert.get("alertType") or ""),
            str(alert.get("title") or ""),
            str(entity.get("ontology", {}).get("specificType") or ""),
            str(entity.get("milView", {}).get("environment") or ""),
            " ".join(str(item) for item in alert.get("evidence", []) if isinstance(item, str)),
        ]
    ).strip()
    context["knowledge"] = search_local_knowledge_base(kb_query, limit=3, context=context)
    generated = call_dify_recommendation(context)
    recommendation = build_recommendation_record(alert, entity, generated, state_signature=state_signature)

    recommendations_store["recommendations"][recommendation["recommendationId"]] = recommendation
    save_recommendations_store(recommendations_store)

    metadata = alert.setdefault("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
        alert["metadata"] = metadata
    metadata["latestRecommendationId"] = recommendation["recommendationId"]
    alert["updatedAt"] = utc_now_iso()
    save_alerts_store(alerts_store)

    await broadcast_recommendation_created(recommendation)
    await broadcast_alert_updated(alert)
    return {
        "recommendationId": recommendation["recommendationId"],
        "recommendation": recommendation,
        "reused": False,
    }


@app.get("/api/v1/recommendations")
def list_recommendations(
    alertId: Optional[str] = None,
    relatedEntityId: Optional[str] = None,
) -> dict[str, Any]:
    """返回本地保存的 recommendations。"""
    store = load_recommendations_store()
    recommendations = list(store["recommendations"].values())

    if alertId is not None:
        recommendations = [item for item in recommendations if item.get("alertId") == alertId]
    if relatedEntityId is not None:
        recommendations = [item for item in recommendations if item.get("entityId") == relatedEntityId]

    recommendations = sorted(recommendations, key=lambda item: timestamp_sort_key(item, "updatedAt"), reverse=True)
    return {
        "count": len(recommendations),
        "recommendations": recommendations,
    }


@app.get("/api/v1/recommendations/{recommendation_id}")
def get_recommendation(recommendation_id: str) -> dict[str, Any]:
    """返回指定 recommendation。"""
    store = load_recommendations_store()
    recommendation = store["recommendations"].get(recommendation_id)
    if recommendation is None:
        raise HTTPException(status_code=404, detail=f"recommendation 不存在: {recommendation_id}")
    return recommendation


@app.get("/api/v1/kb/search")
def search_kb(
    q: str,
    limit: int = 5,
) -> dict[str, Any]:
    """搜索本地知识库。"""
    query = q.strip()
    if not query:
        raise HTTPException(status_code=400, detail="q 不能为空")
    results = search_local_knowledge_base(query, limit=limit)
    return {
        "query": query,
        "count": len(results),
        "results": results,
    }


@app.post("/api/v1/kb/search")
async def search_kb_post(request: Request) -> dict[str, Any]:
    """以 POST 方式搜索本地知识库，可带上下文。"""
    try:
        payload = await request.json()
    except json.JSONDecodeError as error:
        raise HTTPException(status_code=400, detail="请求体必须是合法 JSON") from error

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="请求体必须是 JSON 对象")

    query = payload.get("query")
    if not isinstance(query, str) or not query.strip():
        raise HTTPException(status_code=400, detail="query 必须是非空字符串")

    limit = payload.get("limit", 5)
    if not isinstance(limit, int):
        raise HTTPException(status_code=400, detail="limit 必须是整数")

    context = payload.get("context")
    if context is not None and not isinstance(context, dict):
        raise HTTPException(status_code=400, detail="context 必须是 JSON 对象")

    results = search_local_knowledge_base(query.strip(), limit=limit, context=context)
    return {
        "query": query.strip(),
        "count": len(results),
        "results": results,
    }


@app.post("/api/v1/recommendations/{recommendation_id}/create-task")
async def create_task_from_recommendation(recommendation_id: str, request: Request) -> dict[str, Any]:
    """从 recommendation 创建任务。"""
    try:
        payload = await request.json()
    except json.JSONDecodeError as error:
        raise HTTPException(status_code=400, detail="请求体必须是合法 JSON") from error

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="请求体必须是 JSON 对象")

    store = load_recommendations_store()
    recommendation = store["recommendations"].get(recommendation_id)
    if recommendation is None:
        raise HTTPException(status_code=404, detail=f"recommendation 不存在: {recommendation_id}")

    selected_action = payload.get("selectedAction")
    if selected_action is not None and not isinstance(selected_action, str):
        raise HTTPException(status_code=400, detail="selectedAction 必须是字符串")
    assigned_asset_id = payload.get("assignedAssetId", "SIM_ASSET_001")
    if not isinstance(assigned_asset_id, str) or not assigned_asset_id:
        raise HTTPException(status_code=400, detail="assignedAssetId 必须是非空字符串")

    task_payload = {
        "taskType": "RESPOND_TO_RECOMMENDATION",
        "title": "根据建议执行处置任务",
        "description": selected_action or recommendation["summary"],
        "priority": "HIGH" if recommendation.get("riskLevel") == "HIGH" else "NORMAL",
        "relatedEntityId": recommendation.get("entityId"),
        "assignedAssetId": assigned_asset_id,
        "metadata": {
            "createdFrom": "recommendation",
            "alertId": recommendation.get("alertId"),
            "recommendationId": recommendation_id,
            "selectedAction": selected_action or (recommendation.get("actions") or [recommendation.get("summary")])[0],
            "recommendedAssetTypes": recommendation.get("recommendedAssetTypes", []),
        },
    }
    task = build_task(task_payload)
    task["status"] = "ASSIGNED"

    tasks_store = load_tasks_store()
    tasks_store["tasks"][task["taskId"]] = task
    save_tasks_store(tasks_store)

    recommendation["status"] = "TASK_CREATED"
    recommendation["updatedAt"] = utc_now_iso()
    save_recommendations_store(store)

    await broadcast_task_created(task)
    return {
        "taskId": task["taskId"],
        "task": task,
    }


@app.post("/api/v1/tasks")
async def create_task(request: Request) -> dict[str, Any]:
    """创建本地模拟 task。"""
    try:
        payload = await request.json()
    except json.JSONDecodeError as error:
        raise HTTPException(status_code=400, detail="请求体必须是合法 JSON") from error

    task = build_task(payload)
    store = load_tasks_store()
    store["tasks"][task["taskId"]] = task
    save_tasks_store(store)
    await broadcast_task_created(task)
    return task


@app.get("/api/v1/tasks")
def list_tasks(
    status: Optional[str] = None,
    relatedEntityId: Optional[str] = None,
) -> dict[str, Any]:
    """返回本地保存的 tasks，支持按状态和 relatedEntityId 过滤。"""
    store = load_tasks_store()
    tasks = list(store["tasks"].values())

    if status is not None:
        normalized_status = validate_task_status(status)
        tasks = [task for task in tasks if task.get("status") == normalized_status]

    if relatedEntityId is not None:
        tasks = [
            task
            for task in tasks
            if task.get("relatedEntityId") == relatedEntityId
        ]

    return {
        "count": len(tasks),
        "tasks": tasks,
    }


@app.get("/api/v1/tasks/{task_id}")
def get_task(task_id: str) -> dict[str, Any]:
    """返回指定 task。"""
    store = load_tasks_store()
    task = store["tasks"].get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"task 不存在: {task_id}")
    return task


@app.patch("/api/v1/tasks/{task_id}/status")
async def update_task_status(task_id: str, request: Request) -> dict[str, Any]:
    """更新 task 状态。"""
    try:
        payload = await request.json()
    except json.JSONDecodeError as error:
        raise HTTPException(status_code=400, detail="请求体必须是合法 JSON") from error

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="请求体必须是 JSON 对象")

    new_status = validate_task_status(payload.get("status"))
    store = load_tasks_store()
    task = store["tasks"].get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"task 不存在: {task_id}")

    task["status"] = new_status
    result_summary = payload.get("resultSummary")
    if result_summary is not None:
        if not isinstance(result_summary, str):
            raise HTTPException(status_code=400, detail="resultSummary 必须是字符串")
        task["resultSummary"] = result_summary

    result_metadata = payload.get("resultMetadata")
    if result_metadata is not None:
        if not isinstance(result_metadata, dict):
            raise HTTPException(status_code=400, detail="resultMetadata 必须是 JSON 对象")
        metadata = task.setdefault("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}
            task["metadata"] = metadata
        metadata["result"] = result_metadata

    task["updatedAt"] = utc_now_iso()
    save_tasks_store(store)
    await broadcast_task_status_updated(task)
    return task


@app.delete("/api/v1/tasks/{task_id}")
async def delete_task(task_id: str) -> dict[str, Any]:
    """删除指定 task。"""
    store = load_tasks_store()
    if task_id not in store["tasks"]:
        raise HTTPException(status_code=404, detail=f"task 不存在: {task_id}")

    del store["tasks"][task_id]
    save_tasks_store(store)
    await broadcast_task_deleted(task_id)
    return {
        "deleted": True,
        "taskId": task_id,
    }


@app.post("/api/v1/objects")
async def create_object(
    file: UploadFile = File(...),
    relatedEntityId: Optional[str] = Form(default=None),
    relatedTaskId: Optional[str] = Form(default=None),
    description: Optional[str] = Form(default=None),
    metadata: Optional[str] = Form(default=None),
) -> dict[str, Any]:
    """上传本地 object 文件并保存 metadata。"""
    object_id = generate_object_id()
    safe_filename = sanitize_filename(file.filename)
    stored_filename = f"{object_id}_{safe_filename}"
    object_path = OBJECTS_DIR / stored_filename
    parsed_metadata = parse_metadata_json(metadata)

    OBJECTS_DIR.mkdir(parents=True, exist_ok=True)
    size_bytes = 0
    try:
        with object_path.open("wb") as output_file:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size_bytes += len(chunk)
                if size_bytes > MAX_OBJECT_SIZE_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail="上传文件大小不能超过 20MB",
                    )
                output_file.write(chunk)
    except HTTPException:
        if object_path.exists():
            object_path.unlink()
        raise
    finally:
        await file.close()

    if size_bytes > MAX_OBJECT_SIZE_BYTES:
        if object_path.exists():
            object_path.unlink()
        raise HTTPException(status_code=413, detail="上传文件大小不能超过 20MB")

    if not object_path.exists():
        raise HTTPException(status_code=500, detail="本地 object 文件写入失败")

    sha256 = calculate_sha256(object_path)
    object_metadata = build_object_metadata(
        object_id=object_id,
        filename=safe_filename,
        stored_filename=stored_filename,
        content_type=file.content_type or "application/octet-stream",
        size_bytes=size_bytes,
        sha256=sha256,
        related_entity_id=relatedEntityId,
        related_task_id=relatedTaskId,
        description=description,
        metadata=parsed_metadata,
    )

    store = load_objects_store()
    store["objects"][object_id] = object_metadata
    try:
        save_objects_store(store)
    except Exception:
        if object_path.exists():
            object_path.unlink()
        raise

    await broadcast_object_created(object_metadata)
    return object_metadata


@app.get("/api/v1/objects")
def list_objects(
    relatedEntityId: Optional[str] = None,
    relatedTaskId: Optional[str] = None,
    contentType: Optional[str] = None,
) -> dict[str, Any]:
    """返回本地保存的 objects，支持按关联字段和 contentType 过滤。"""
    store = load_objects_store()
    objects = list(store["objects"].values())

    if relatedEntityId is not None:
        objects = [
            object_metadata
            for object_metadata in objects
            if object_metadata.get("relatedEntityId") == relatedEntityId
        ]

    if relatedTaskId is not None:
        objects = [
            object_metadata
            for object_metadata in objects
            if object_metadata.get("relatedTaskId") == relatedTaskId
        ]

    if contentType is not None:
        objects = [
            object_metadata
            for object_metadata in objects
            if object_metadata.get("contentType") == contentType
        ]

    return {
        "count": len(objects),
        "objects": objects,
    }


@app.get("/api/v1/objects/{object_id}/download")
def download_object(object_id: str) -> FileResponse:
    """下载本地 object 原始文件。"""
    store = load_objects_store()
    object_metadata = store["objects"].get(object_id)
    if object_metadata is None:
        raise HTTPException(status_code=404, detail=f"object 不存在: {object_id}")

    object_path = OBJECTS_DIR / object_metadata["storedFilename"]
    if not object_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"本地 object 文件不存在: {object_id}",
        )

    return FileResponse(
        object_path,
        media_type=object_metadata.get("contentType") or "application/octet-stream",
        filename=object_metadata.get("filename") or object_metadata["storedFilename"],
    )


@app.get("/api/v1/objects/{object_id}")
def get_object(object_id: str) -> dict[str, Any]:
    """返回指定 object metadata。"""
    store = load_objects_store()
    object_metadata = store["objects"].get(object_id)
    if object_metadata is None:
        raise HTTPException(status_code=404, detail=f"object 不存在: {object_id}")
    return object_metadata


@app.delete("/api/v1/objects/{object_id}")
async def delete_object(object_id: str) -> dict[str, Any]:
    """删除指定 object metadata 和本地文件。"""
    store = load_objects_store()
    object_metadata = store["objects"].get(object_id)
    if object_metadata is None:
        raise HTTPException(status_code=404, detail=f"object 不存在: {object_id}")

    object_path = OBJECTS_DIR / object_metadata["storedFilename"]
    del store["objects"][object_id]
    save_objects_store(store)

    if object_path.exists():
        object_path.unlink()

    await broadcast_object_deleted(object_id)
    return {
        "deleted": True,
        "objectId": object_id,
    }


@app.delete("/api/v1/entities/{entity_id}")
async def delete_entity(entity_id: str) -> dict[str, Any]:
    """删除指定 entity。"""
    store = read_store()
    if entity_id not in store["entities"]:
        raise HTTPException(status_code=404, detail=f"entity 不存在: {entity_id}")

    del store["entities"][entity_id]
    write_store(store)
    await connection_manager.broadcast(
        {
            "type": "entity.deleted",
            "entityId": entity_id,
            "timestamp": utc_now_iso(),
        }
    )
    return {
        "deleted": True,
        "entityId": entity_id,
    }


@app.websocket("/api/v1/entities/stream")
async def stream_entities(websocket: WebSocket) -> None:
    """建立本地 entity update stream。"""
    await connection_manager.connect(websocket)
    try:
        await websocket.send_json(
            {
                "type": "stream.connected",
                "message": "已连接到本地 entity stream",
                "timestamp": utc_now_iso(),
            }
        )
        while True:
            # 当前 stream 只由服务端推送；接收客户端消息用于感知断开。
            await websocket.receive_text()
    except WebSocketDisconnect:
        await connection_manager.disconnect(websocket)
    except Exception:
        await connection_manager.disconnect(websocket)
