#!/usr/bin/env python3
"""一键运行本地 fake Lattice 演示工作流。"""

import argparse
import json
import random
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any


DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_ASSET_ID = "SIM_ASSET_001"
DEFAULT_LATITUDE = 33.69447852698943
DEFAULT_LONGITUDE = -117.9173785693163
TERMINAL_STATUSES = {"SUCCEEDED", "FAILED", "CANCELED"}


class DemoHttpError(Exception):
    """HTTP 调用失败。"""


def utc_now_iso() -> str:
    """返回当前 UTC 时间字符串。"""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def future_utc_iso(hours: int) -> str:
    """返回未来 UTC 时间字符串。"""
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat().replace("+00:00", "Z")


def normalize_base_url(base_url: str) -> str:
    """移除 base URL 尾部斜杠。"""
    return base_url.rstrip("/")


def print_step(step: int, message: str) -> None:
    """输出演示步骤。"""
    print(f"[{step}] {message}", flush=True)


def request_json(
    base_url: str,
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | list[Any] | None = None,
    token: str | None = None,
) -> dict[str, Any]:
    """发送 JSON HTTP 请求并解析 JSON 响应。"""
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(
        f"{normalize_base_url(base_url)}{path}",
        data=body,
        headers=headers,
        method=method,
    )

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            response_body = response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise DemoHttpError(f"{method} {path} 返回 {error.code}: {detail}") from error
    except urllib.error.URLError as error:
        raise DemoHttpError(f"{method} {path} 连接失败: {error.reason}") from error

    if not response_body:
        return {}
    try:
        decoded = json.loads(response_body)
    except json.JSONDecodeError as error:
        raise DemoHttpError(f"{method} {path} 响应不是合法 JSON: {error}") from error
    if not isinstance(decoded, dict):
        raise DemoHttpError(f"{method} {path} 响应必须是 JSON 对象")
    return decoded


def upload_report_object(
    base_url: str,
    *,
    token: str,
    task_id: str,
    entity_id: str,
    task_status: str,
    result_summary: str,
    threat: dict[str, Any],
) -> dict[str, Any]:
    """用 multipart/form-data 上传一个任务报告 object。"""
    boundary = f"----fake-lattice-demo-{uuid.uuid4().hex}"
    report_text = (
        "Fake Lattice task report\n"
        f"createdAt: {utc_now_iso()}\n"
        f"entityId: {entity_id}\n"
        f"taskId: {task_id}\n"
        f"finalStatus: {task_status}\n"
        f"placeName: {threat.get('placeName', '-')}\n"
        f"threatLevel: {threat.get('threatLevel', '-')}\n"
        f"anomalyType: {threat.get('anomalyType', '-')}\n"
        f"sensorSources: {', '.join(threat.get('sensorSources', [])) if isinstance(threat.get('sensorSources'), list) else threat.get('sensorSources', '-')}\n"
        f"recommendation: {threat.get('recommendation', '-')}\n"
        f"resultSummary: {result_summary}\n"
    )
    fields = {
        "relatedTaskId": task_id,
        "relatedEntityId": entity_id,
        "description": "demo workflow generated task report",
        "metadata": json.dumps({"createdFrom": "tools/demo_workflow.py"}, ensure_ascii=False),
    }

    parts: list[bytes] = []
    for name, value in fields.items():
        parts.append(
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
                f"{value}\r\n"
            ).encode("utf-8")
        )

    parts.append(
        (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; filename="demo-task-report.txt"\r\n'
            "Content-Type: text/plain\r\n\r\n"
        ).encode("utf-8")
    )
    parts.append(report_text.encode("utf-8"))
    parts.append(f"\r\n--{boundary}--\r\n".encode("utf-8"))

    request = urllib.request.Request(
        f"{normalize_base_url(base_url)}/api/v1/objects",
        data=b"".join(parts),
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            response_body = response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise DemoHttpError(f"POST /api/v1/objects 返回 {error.code}: {detail}") from error
    except urllib.error.URLError as error:
        raise DemoHttpError(f"POST /api/v1/objects 连接失败: {error.reason}") from error

    decoded = json.loads(response_body)
    if not isinstance(decoded, dict):
        raise DemoHttpError("POST /api/v1/objects 响应必须是 JSON 对象")
    return decoded


def build_demo_entity(args: argparse.Namespace) -> dict[str, Any]:
    """构建一个带威胁分析的 AIS 风格 demo entity。"""
    suffix = random.randint(100000, 999999)
    mmsi = f"366{suffix}"
    now = utc_now_iso()
    latitude = args.lat + random.uniform(-args.radius_deg, args.radius_deg)
    longitude = args.lon + random.uniform(-args.radius_deg, args.radius_deg)
    speed_knots = round(random.uniform(16, 24), 1) if args.threat_level == "HIGH" else round(random.uniform(8, 15), 1)
    recommendation = (
        f"建议派遣 {args.asset_id} 对目标进行持续跟踪，保持安全距离，"
        "同步采集图像/航迹证据，并在威胁升级时转人工确认。"
    )
    return {
        "entityId": f"AIS_DEMO_MMSI_{mmsi}",
        "description": f"Demo threat track created near {args.place_name}",
        "createdTime": now,
        "isLive": True,
        "expiryTime": future_utc_iso(1),
        "aliases": {
            "name": f"DEMO AIS VESSEL {mmsi}",
            "alternateIds": [{"id": mmsi, "type": "ALT_ID_TYPE_MMSI_ID"}],
        },
        "milView": {
            "disposition": "DISPOSITION_NEUTRAL",
            "environment": "ENVIRONMENT_SURFACE",
        },
        "location": {
            "position": {
                "latitudeDegrees": latitude,
                "longitudeDegrees": longitude,
                "altitudeHaeMeters": 0,
            }
        },
        "ontology": {
            "template": "TEMPLATE_TRACK",
            "platformType": "Surface Vessel",
            "specificType": "SURFACE_VESSEL",
        },
        "provenance": {
            "integrationName": "fake-lattice-demo-workflow",
            "dataType": "SIMULATED_SURFACE_VESSEL",
            "sourceName": "demo_workflow",
            "sourceId": "demo_workflow",
            "sourceUpdateTime": now,
        },
        "dataClassification": {
            "default": {"level": "CLASSIFICATION_LEVELS_UNCLASSIFIED"}
        },
        "metadata": {
            "ais": {
                "mmsi": mmsi,
                "vesselName": f"DEMO AIS VESSEL {mmsi}",
                "speedKnots": speed_knots,
                "courseDegrees": round(random.uniform(0, 359.9), 1),
                "navigationStatus": "UNDER_WAY_USING_ENGINE",
            },
            "threat": {
                "scenario": args.scenario,
                "placeName": args.place_name,
                "threatLevel": args.threat_level,
                "anomalyType": args.anomaly_type,
                "sensorSources": ["AIS", "岸基雷达", "光电观察哨"],
                "detectedAt": now,
                "recommendation": recommendation,
            },
        },
    }


def create_demo_task(base_url: str, token: str, entity: dict[str, Any], asset_id: str) -> dict[str, Any]:
    """创建一个威胁处置任务。"""
    entity_id = str(entity["entityId"])
    threat = entity.get("metadata", {}).get("threat", {})
    payload = {
        "taskType": "RESPOND_TO_THREAT",
        "title": "处置疑似威胁目标",
        "description": threat.get("recommendation", "demo workflow created threat response task"),
        "priority": "HIGH" if threat.get("threatLevel") == "HIGH" else "NORMAL",
        "relatedEntityId": entity_id,
        "assignedAssetId": asset_id,
        "metadata": {
            "createdFrom": "tools/demo_workflow.py",
            "threatAnalysis": threat,
        },
    }
    return request_json(base_url, "/api/v1/tasks", method="POST", payload=payload, token=token)


def advance_task_inline(base_url: str, token: str, task_id: str, work_seconds: float) -> dict[str, Any]:
    """在 demo 脚本内推进任务状态。"""
    task: dict[str, Any] = {}
    for status in ("ACCEPTED", "IN_PROGRESS", "SUCCEEDED"):
        if status == "SUCCEEDED" and work_seconds > 0:
            time.sleep(work_seconds)
        payload: dict[str, Any] = {"status": status}
        if status == "SUCCEEDED":
            current_task = request_json(base_url, f"/api/v1/tasks/{urllib.parse.quote(task_id)}", token=token)
            threat = current_task.get("metadata", {}).get("threatAnalysis", {})
            payload["resultSummary"] = (
                f"处置完成：已根据传感器告警对 {current_task.get('relatedEntityId')} 建立跟踪，"
                f"威胁等级 {threat.get('threatLevel', 'UNKNOWN')}，建议继续执行："
                f"{threat.get('recommendation', '常规监控')} "
            )
            payload["resultMetadata"] = {
                "agentId": "demo_workflow_inline_agent",
                "completedAt": utc_now_iso(),
                "workflow": "SIMULATED_THREAT_RESPONSE",
            }
        task = request_json(
            base_url,
            f"/api/v1/tasks/{urllib.parse.quote(task_id)}/status",
            method="PATCH",
            payload=payload,
            token=token,
        )
        print_step(5, f"task status -> {status}")
    return task


def wait_for_task_terminal(base_url: str, token: str, task_id: str, timeout_seconds: float) -> dict[str, Any]:
    """等待外部 sim_agent 把任务推进到终态。"""
    deadline = time.monotonic() + timeout_seconds
    last_status = None
    while time.monotonic() < deadline:
        task = request_json(base_url, f"/api/v1/tasks/{urllib.parse.quote(task_id)}", token=token)
        status = task.get("status")
        if status != last_status:
            print_step(5, f"task status -> {status}")
            last_status = status
        if status in TERMINAL_STATUSES:
            return task
        time.sleep(1)
    raise DemoHttpError(f"等待任务进入终态超时: {task_id}")


def run_demo(args: argparse.Namespace) -> int:
    """执行完整 fake Lattice demo workflow。"""
    base_url = normalize_base_url(args.base_url)

    token_payload = request_json(
        base_url,
        "/api/v1/oauth/token",
        method="POST",
        payload={
            "grant_type": "client_credentials",
            "client_id": "fake-demo-client",
            "client_secret": "fake-demo-secret",
            "scope": "entities tasks objects",
        },
    )
    token = str(token_payload.get("access_token") or "")
    if not token:
        raise DemoHttpError("fake OAuth 响应缺少 access_token")
    print_step(1, "fake auth ok")

    entity = build_demo_entity(args)
    entity_id = str(entity["entityId"])
    request_json(base_url, "/api/v1/entities", method="PUT", payload=entity, token=token)
    threat = entity["metadata"]["threat"]
    print_step(2, f"threat entity created: {entity_id} level={threat['threatLevel']} place={threat['placeName']}")

    task = create_demo_task(base_url, token, entity, args.asset_id)
    task_id = str(task["taskId"])
    print_step(3, f"response task created: {task_id}")
    print_step(3, f"recommendation: {threat['recommendation']}")

    if args.use_external_agent:
        print_step(4, f"waiting for external agent asset_id={args.asset_id}")
        final_task = wait_for_task_terminal(base_url, token, task_id, args.timeout_seconds)
    else:
        print_step(4, "advancing task inline")
        final_task = advance_task_inline(base_url, token, task_id, args.work_seconds)

    final_status = str(final_task.get("status"))
    result_summary = str(final_task.get("resultSummary") or "")
    report = upload_report_object(
        base_url,
        token=token,
        task_id=task_id,
        entity_id=entity_id,
        task_status=final_status,
        result_summary=result_summary,
        threat=threat,
    )
    print_step(6, f"report object uploaded: {report.get('objectId')}")
    print_step(7, f"workflow complete: entity={entity_id} task={task_id} status={final_status}")
    return 0


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(description="一键运行本地 fake Lattice demo workflow。")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="mock server base URL")
    parser.add_argument("--asset-id", default=DEFAULT_ASSET_ID, help="任务分配的模拟 asset id")
    parser.add_argument("--work-seconds", type=float, default=1.0, help="inline 模式模拟执行秒数")
    parser.add_argument("--timeout-seconds", type=float, default=30.0, help="等待外部 agent 的超时时间")
    parser.add_argument("--lat", type=float, default=DEFAULT_LATITUDE, help="威胁事件中心纬度")
    parser.add_argument("--lon", type=float, default=DEFAULT_LONGITUDE, help="威胁事件中心经度")
    parser.add_argument("--radius-deg", type=float, default=0.01, help="威胁目标随机偏移半径")
    parser.add_argument("--place-name", default="Orange County coast", help="演示地点名称")
    parser.add_argument("--scenario", default="coastal_monitoring", help="演示场景名称")
    parser.add_argument("--threat-level", choices=("LOW", "MEDIUM", "HIGH"), default="HIGH", help="模拟威胁等级")
    parser.add_argument("--anomaly-type", default="高速接近限制区域", help="模拟异常类型")
    parser.add_argument(
        "--use-external-agent",
        action="store_true",
        help="不在脚本内推进任务状态，改为等待 tools/sim_agent.py 处理",
    )
    return parser.parse_args()


def main() -> int:
    """程序入口。"""
    args = parse_args()
    try:
        return run_demo(args)
    except (DemoHttpError, ValueError, KeyError) as error:
        print(f"demo workflow failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
