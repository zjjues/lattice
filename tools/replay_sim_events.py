#!/usr/bin/env python3
"""按时间顺序回放本地模拟事件轨迹。"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_INTERVAL_SECONDS = 1.0


def load_events(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"找不到轨迹文件: {path}")

    events = []
    for line_no, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"第 {line_no} 行不是合法 JSON") from error
        if not isinstance(payload, dict):
            raise ValueError(f"第 {line_no} 行必须是 JSON 对象")
        events.append(payload)
    return events


def post_event(base_url: str, payload: dict) -> dict:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/v1/ingest/events",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def print_event_result(index: int, total: int, payload: dict, response: dict) -> None:
    track = payload.get("track", {}) if isinstance(payload.get("track"), dict) else {}
    location = track.get("location", {}) if isinstance(track.get("location"), dict) else {}
    lat = location.get("latitudeDegrees")
    lon = location.get("longitudeDegrees")
    print(
        json.dumps(
            {
                "step": f"{index}/{total}",
                "trackId": track.get("trackId"),
                "speedMps": track.get("speedMps"),
                "location": {"lat": lat, "lon": lon},
                "entityId": response.get("entityId"),
                "alertsCreated": response.get("alertsCreated", []),
            },
            ensure_ascii=False,
        )
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="按顺序回放本地 ingest 轨迹事件。")
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help="mock server base URL",
    )
    parser.add_argument(
        "--input",
        default="fixtures/ingest/uav_intrusion.jsonl",
        help="输入的 JSONL 轨迹文件",
    )
    parser.add_argument(
        "--interval-seconds",
        type=float,
        default=DEFAULT_INTERVAL_SECONDS,
        help="两条事件之间的发送间隔秒数",
    )
    parser.add_argument(
        "--loop",
        action="store_true",
        help="循环回放",
    )
    return parser.parse_args()


def run_once(base_url: str, input_path: Path, interval_seconds: float) -> None:
    events = load_events(input_path)
    if not events:
        print("轨迹文件为空", file=sys.stderr)
        return

    total = len(events)
    for index, payload in enumerate(events, start=1):
        response = post_event(base_url, payload)
        print_event_result(index, total, payload, response)
        if index < total:
            time.sleep(max(0.0, interval_seconds))


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    try:
        while True:
            run_once(args.base_url, input_path, args.interval_seconds)
            if not args.loop:
                break
            time.sleep(max(0.0, args.interval_seconds))
    except FileNotFoundError as error:
        print(str(error), file=sys.stderr)
        return 1
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 1
    except urllib.error.HTTPError as error:
        print(f"HTTPError: {error.code}", file=sys.stderr)
        print(error.read().decode("utf-8", errors="replace"), file=sys.stderr)
        return 1
    except urllib.error.URLError as error:
        print(f"URLError: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
