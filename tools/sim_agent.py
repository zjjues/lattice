#!/usr/bin/env python3
"""本地模拟 agent / asset，自动接收并执行 mock tasks。"""

import argparse
import json
import random
import signal
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any


DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_ASSET_ID = "SIM_ASSET_001"
ACTIVE_TASK_STATUSES = {"CREATED", "ASSIGNED"}
TERMINAL_TASK_STATUSES = {"SUCCEEDED", "FAILED", "CANCELED"}

stop_requested = False
current_asset_id = DEFAULT_ASSET_ID


class AgentHttpError(Exception):
    """本地 agent HTTP 调用错误。"""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def utc_now_iso() -> str:
    """返回当前 UTC 时间字符串。"""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def log(asset_id: str, message: str) -> None:
    """输出本地 agent 日志。"""
    print(f"[{utc_now_iso()}] [agent {asset_id}] {message}", flush=True)


def normalize_base_url(base_url: str) -> str:
    """清理 base URL 末尾斜杠。"""
    return base_url.rstrip("/")


def request_json(url: str, *, method: str = "GET", payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """发送 HTTP 请求并解析 JSON 响应。"""
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=body, headers=headers, method=method)

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            response_body = response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise AgentHttpError(
            f"{method} {url} 返回 {error.code}: {detail}",
            status_code=error.code,
        ) from error
    except urllib.error.URLError as error:
        raise AgentHttpError(f"{method} {url} 连接失败: {error.reason}") from error

    try:
        return json.loads(response_body)
    except json.JSONDecodeError as error:
        raise AgentHttpError(f"{method} {url} JSON 解析失败: {error}") from error


def get_tasks(base_url: str) -> list[dict[str, Any]]:
    """查询 mock server 中的所有 tasks。"""
    payload = request_json(f"{normalize_base_url(base_url)}/api/v1/tasks")
    tasks = payload.get("tasks", [])
    if not isinstance(tasks, list):
        raise AgentHttpError("GET /api/v1/tasks 响应中的 tasks 必须是数组")
    return [task for task in tasks if isinstance(task, dict)]


def get_task(base_url: str, task_id: str) -> dict[str, Any]:
    """查询单个 task。"""
    task = request_json(f"{normalize_base_url(base_url)}/api/v1/tasks/{task_id}")
    if not isinstance(task, dict):
        raise AgentHttpError(f"GET /api/v1/tasks/{task_id} 响应必须是对象")
    return task


def patch_task_status(
    base_url: str,
    task_id: str,
    status: str,
    *,
    result_summary: str | None = None,
    result_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """更新 task 状态。"""
    payload: dict[str, Any] = {"status": status}
    if result_summary is not None:
        payload["resultSummary"] = result_summary
    if result_metadata is not None:
        payload["resultMetadata"] = result_metadata

    task = request_json(
        f"{normalize_base_url(base_url)}/api/v1/tasks/{task_id}/status",
        method="PATCH",
        payload=payload,
    )
    if not isinstance(task, dict):
        raise AgentHttpError(f"PATCH /api/v1/tasks/{task_id}/status 响应必须是对象")
    return task


def find_candidate_tasks(tasks: list[dict[str, Any]], asset_id: str) -> list[dict[str, Any]]:
    """找出分配给当前 asset 且可处理的 tasks。"""
    candidates = [
        task
        for task in tasks
        if task.get("assignedAssetId") == asset_id
        and task.get("status") in ACTIVE_TASK_STATUSES
        and task.get("taskId")
    ]

    return sorted(candidates, key=lambda task: task.get("createdAt") or "")


def sleep_with_stop(seconds: float) -> bool:
    """可被退出信号打断的 sleep。"""
    deadline = time.monotonic() + max(seconds, 0)
    while time.monotonic() < deadline:
        if stop_requested:
            return False
        time.sleep(min(0.25, deadline - time.monotonic()))
    return not stop_requested


def set_task_status(
    base_url: str,
    task_id: str,
    status: str,
    asset_id: str,
    *,
    result_summary: str | None = None,
    result_metadata: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """设置 task 状态并打印日志，失败时不中断整个 agent。"""
    try:
        task = patch_task_status(
            base_url,
            task_id,
            status,
            result_summary=result_summary,
            result_metadata=result_metadata,
        )
    except AgentHttpError as error:
        log(asset_id, f"更新任务失败 {task_id} -> {status}：{error}")
        return None

    log(asset_id, f"{task_id} -> {status}")
    return task


def process_task(
    base_url: str,
    task: dict[str, Any],
    work_seconds: float,
    success_rate: float,
    asset_id: str = DEFAULT_ASSET_ID,
) -> bool:
    """处理单个 task，返回是否完成处理。"""
    task_id = str(task["taskId"])
    initial_status = task.get("status")
    log(asset_id, f"发现任务 {task_id}，当前状态 {initial_status}")

    try:
        latest_task = get_task(base_url, task_id)
    except AgentHttpError as error:
        log(asset_id, f"重新查询任务失败 {task_id}：{error}")
        return False

    latest_status = latest_task.get("status")
    if latest_task.get("assignedAssetId") != asset_id:
        log(asset_id, f"跳过任务 {task_id}：assignedAssetId 已变化")
        return False

    if latest_status not in ACTIVE_TASK_STATUSES:
        log(asset_id, f"跳过任务 {task_id}：状态已变为 {latest_status}")
        return False

    accepted_task = set_task_status(base_url, task_id, "ACCEPTED", asset_id)
    if accepted_task is None:
        return False

    if not sleep_with_stop(0.5):
        return False

    in_progress_task = set_task_status(base_url, task_id, "IN_PROGRESS", asset_id)
    if in_progress_task is None:
        return False

    if not sleep_with_stop(work_seconds):
        return False

    try:
        latest_task = get_task(base_url, task_id)
    except AgentHttpError as error:
        log(asset_id, f"最终状态前重新查询任务失败 {task_id}：{error}")
        return False

    latest_status = latest_task.get("status")
    if latest_status in TERMINAL_TASK_STATUSES:
        log(asset_id, f"任务 {task_id} 已是终态 {latest_status}，不再更新")
        return True

    final_status = "SUCCEEDED" if random.random() < success_rate else "FAILED"
    related_entity_id = latest_task.get("relatedEntityId")
    threat = latest_task.get("metadata", {}).get("threatAnalysis", {})
    recommendation = threat.get("recommendation") or "继续常规监控。"
    if final_status == "SUCCEEDED":
        result_summary = (
            f"处置完成：{asset_id} 已接收并执行威胁响应任务，"
            f"目标 {related_entity_id or 'UNKNOWN'} 的威胁等级为 {threat.get('threatLevel', 'UNKNOWN')}，"
            f"异常类型为 {threat.get('anomalyType', '未知')}。执行建议：{recommendation}"
        )
    else:
        result_summary = f"处置失败：{related_entity_id or '目标'} 的威胁响应任务未能完成，需要人工复核。"

    return set_task_status(
        base_url,
        task_id,
        final_status,
        asset_id,
        result_summary=result_summary,
        result_metadata={
            "agentId": asset_id,
            "relatedEntityId": related_entity_id,
            "threatAnalysis": threat,
            "completedAt": utc_now_iso(),
            "workflow": "SIMULATED_THREAT_RESPONSE",
        },
    ) is not None


def parse_success_rate(value: str) -> float:
    """解析并校验成功率。"""
    try:
        success_rate = float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("success-rate 必须是数字") from error

    if success_rate < 0 or success_rate > 1:
        raise argparse.ArgumentTypeError("success-rate 必须在 0 到 1 之间")
    return success_rate


def parse_positive_float(value: str) -> float:
    """解析非负浮点数。"""
    try:
        number = float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("必须是数字") from error

    if number < 0:
        raise argparse.ArgumentTypeError("必须大于或等于 0")
    return number


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(description="本地模拟 agent / asset 自动处理 tasks。")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="mock server base URL")
    parser.add_argument("--asset-id", default=DEFAULT_ASSET_ID, help="当前模拟 asset id")
    parser.add_argument("--poll-interval", type=parse_positive_float, default=3.0, help="轮询间隔秒数")
    parser.add_argument("--work-seconds", type=parse_positive_float, default=5.0, help="模拟任务执行秒数")
    parser.add_argument("--success-rate", type=parse_success_rate, default=0.9, help="任务成功概率，范围 0 到 1")
    parser.add_argument("--once", action="store_true", help="只处理一轮后退出")
    parser.add_argument("--verbose", action="store_true", help="输出详细日志")
    return parser.parse_args()


def handle_stop_signal(signum: int, frame: Any) -> None:
    """处理退出信号。"""
    del signum, frame
    global stop_requested
    stop_requested = True
    log(current_asset_id, "收到退出信号，准备停止")


def run_agent(args: argparse.Namespace) -> int:
    """运行本地模拟 agent 主循环。"""
    global current_asset_id
    current_asset_id = args.asset_id
    in_progress_task_ids: set[str] = set()
    completed_task_ids: set[str] = set()
    base_url = normalize_base_url(args.base_url)

    log(
        args.asset_id,
        (
            f"启动模拟 agent，base_url={base_url} "
            f"poll_interval={args.poll_interval}s work_seconds={args.work_seconds}s "
            f"success_rate={args.success_rate}"
        ),
    )

    while not stop_requested:
        try:
            if args.verbose:
                log(args.asset_id, "轮询 GET /api/v1/tasks")
            tasks = get_tasks(base_url)
        except AgentHttpError as error:
            log(args.asset_id, f"查询任务失败：{error}")
            if args.once:
                return 1
            sleep_with_stop(args.poll_interval)
            continue

        candidates = find_candidate_tasks(tasks, args.asset_id)
        candidates = [
            task
            for task in candidates
            if task["taskId"] not in in_progress_task_ids
            and task["taskId"] not in completed_task_ids
        ]

        if args.verbose and not candidates:
            log(args.asset_id, "本轮未发现待处理任务")

        for task in candidates:
            if stop_requested:
                break
            task_id = str(task["taskId"])
            in_progress_task_ids.add(task_id)
            try:
                if process_task(base_url, task, args.work_seconds, args.success_rate, args.asset_id):
                    completed_task_ids.add(task_id)
            finally:
                in_progress_task_ids.discard(task_id)

        if args.once:
            break

        sleep_with_stop(args.poll_interval)

    log(args.asset_id, "模拟 agent 已退出")
    return 0


def main() -> int:
    """程序入口。"""
    args = parse_args()
    signal.signal(signal.SIGTERM, handle_stop_signal)
    signal.signal(signal.SIGINT, handle_stop_signal)
    return run_agent(args)


if __name__ == "__main__":
    sys.exit(main())
