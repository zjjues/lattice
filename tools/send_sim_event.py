#!/usr/bin/env python3
"""向本地 fake Lattice 注入一条模拟事件。"""

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone


DEFAULT_BASE_URL = "http://127.0.0.1:8000"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def build_payload(args: argparse.Namespace) -> dict:
    return {
        "sourceType": args.source_type,
        "sourceId": args.source_id,
        "eventType": "track_update",
        "timestamp": utc_now_iso(),
        "track": {
            "trackId": args.track_id,
            "name": args.name,
            "identity": args.identity,
            "platformType": args.platform_type,
            "speedMps": args.speed_mps,
            "headingDegrees": args.heading_degrees,
            "altitudeMeters": args.altitude_meters,
            "location": {
                "latitudeDegrees": args.lat,
                "longitudeDegrees": args.lon,
            },
        },
        "sensorContext": {
            "confidence": args.confidence,
            "zone": args.zone,
            "tags": args.tags,
        },
    }


def send_event(base_url: str, payload: dict) -> dict:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/v1/ingest/events",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="向本地 fake Lattice 注入单条模拟事件。")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="mock server base URL")
    parser.add_argument("--source-type", default="uav", help="数据来源类型")
    parser.add_argument("--source-id", default="SIM_UAV_001", help="数据来源 ID")
    parser.add_argument("--track-id", default="TRACK_UAV_001", help="目标 track ID")
    parser.add_argument("--name", default="Unknown UAV", help="目标名称")
    parser.add_argument("--identity", default="unknown", help="目标身份")
    parser.add_argument("--platform-type", default="UAV", help="目标平台类型")
    parser.add_argument("--speed-mps", type=float, default=22.0, help="目标速度 m/s")
    parser.add_argument("--heading-degrees", type=float, default=68.0, help="目标航向角")
    parser.add_argument("--altitude-meters", type=float, default=120.0, help="目标高度")
    parser.add_argument("--lat", type=float, default=31.2304, help="纬度")
    parser.add_argument("--lon", type=float, default=121.4737, help="经度")
    parser.add_argument("--confidence", type=float, default=0.88, help="置信度")
    parser.add_argument("--zone", default="ZONE_A", help="区域标识")
    parser.add_argument("--tags", nargs="*", default=["restricted_area_edge", "fast_approach"], help="标签列表")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    try:
        result = send_event(args.base_url, payload)
    except urllib.error.HTTPError as error:
        print(f"HTTPError: {error.code}", file=sys.stderr)
        print(error.read().decode("utf-8", errors="replace"), file=sys.stderr)
        return 1
    except urllib.error.URLError as error:
        print(f"URLError: {error}", file=sys.stderr)
        return 1

    print(json.dumps({"request": payload, "response": result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
