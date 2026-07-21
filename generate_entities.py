#!/usr/bin/env python3
"""生成本地 Lattice-style 模拟 Surface Vessel entity JSON。"""

import argparse
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path


DEFAULT_CENTER_LAT = 33.69447852698943
DEFAULT_CENTER_LON = -117.9173785693163
DEFAULT_RADIUS_DEG = 0.05
DEFAULT_OUTPUT = "examples/entities.jsonl"
DEFAULT_SOURCE_NAME = "local_ais_simulator"
DEFAULT_START_MMSI = 366000000
NAVIGATION_STATUSES = [
    "UNDER_WAY_USING_ENGINE",
    "AT_ANCHOR",
    "NOT_UNDER_COMMAND",
    "MOORED",
]


def utc_now_iso():
    """返回当前 UTC 时间的 ISO 8601 字符串。"""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def future_utc_iso(hours):
    """返回当前 UTC 时间之后若干小时的 ISO 8601 字符串。"""
    return (
        datetime.now(timezone.utc) + timedelta(hours=hours)
    ).isoformat().replace("+00:00", "Z")


def generate_mmsi(start_mmsi, index):
    """按起始 MMSI 和序号生成稳定的模拟 MMSI。"""
    return start_mmsi + index


def generate_vessel_name(entity_number):
    """生成稳定的模拟 AIS 船名。"""
    return f"SIM AIS VESSEL {entity_number:04d}"


def random_ais_metadata(mmsi, vessel_name):
    """生成 AIS 风格的扩展元数据。"""
    return {
        "mmsi": str(mmsi),
        "vesselName": vessel_name,
        "speedKnots": round(random.uniform(0, 18), 1),
        "courseDegrees": round(random.uniform(0, 359.9), 1),
        "headingDegrees": random.randint(0, 359),
        "navigationStatus": random.choice(NAVIGATION_STATUSES),
    }


def random_position(center_lat, center_lon, radius_deg):
    """在给定中心点附近生成一个随机经纬度位置。"""
    latitude = center_lat + random.uniform(-radius_deg, radius_deg)
    longitude = center_lon + random.uniform(-radius_deg, radius_deg)

    # 将随机结果限制在合法经纬度范围内，避免中心点靠近边界时越界。
    latitude = max(-90.0, min(90.0, latitude))
    longitude = max(-180.0, min(180.0, longitude))

    return {
        "latitudeDegrees": latitude,
        "longitudeDegrees": longitude,
        "altitudeHaeMeters": 0,
    }


def build_surface_vessel_entity(
    index,
    center_lat,
    center_lon,
    radius_deg,
    source_name,
    start_mmsi,
    include_ais_metadata,
):
    """构建一个模拟的、非敏感的 Surface Vessel entity。"""
    entity_number = index + 1
    now = utc_now_iso()
    mmsi = generate_mmsi(start_mmsi, index)
    vessel_name = generate_vessel_name(entity_number)

    entity = {
        "entityId": f"AIS_SIM_MMSI_{mmsi}",
        "description": f"Simulated AIS surface vessel {entity_number}",
        "createdTime": now,
        "isLive": True,
        "expiryTime": future_utc_iso(1),
        "aliases": {
            "name": vessel_name,
            "alternateIds": [
                {
                    "id": str(mmsi),
                    "type": "ALT_ID_TYPE_MMSI_ID",
                }
            ],
        },
        "milView": {
            "disposition": "DISPOSITION_NEUTRAL",
            "environment": "ENVIRONMENT_SURFACE",
        },
        "location": {
            "position": random_position(center_lat, center_lon, radius_deg),
        },
        "ontology": {
            "template": "TEMPLATE_TRACK",
            "platformType": "Surface Vessel",
            "specificType": "SURFACE_VESSEL",
        },
        "provenance": {
            "integrationName": "local-entity-generator",
            "dataType": "SIMULATED_SURFACE_VESSEL",
            "sourceName": source_name,
            "sourceId": source_name,
            "sourceUpdateTime": now,
        },
        "dataClassification": {
            "default": {
                "level": "CLASSIFICATION_LEVELS_UNCLASSIFIED",
            }
        },
    }
    if include_ais_metadata:
        entity["metadata"] = {
            "ais": random_ais_metadata(mmsi, vessel_name),
        }
    return entity


def validate_args(args):
    """校验命令行参数是否合法。"""
    if args.count < 1:
        raise ValueError("--count 必须大于或等于 1")

    if not -90 <= args.center_lat <= 90:
        raise ValueError("--center-lat 必须在 -90 到 90 之间")

    if not -180 <= args.center_lon <= 180:
        raise ValueError("--center-lon 必须在 -180 到 180 之间")

    if args.radius_deg < 0:
        raise ValueError("--radius-deg 必须大于或等于 0")

    if args.start_mmsi < 0:
        raise ValueError("--start-mmsi 必须大于或等于 0")

    if not args.source_name:
        raise ValueError("--source-name 不能为空")


def write_output(entities, output_path, output_format):
    """按指定格式写出 entity 文件，并在需要时创建输出目录。"""
    path = Path(output_path)
    if path.parent != Path("."):
        path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as output_file:
        if output_format == "json":
            payload = entities[0] if len(entities) == 1 else entities
            json.dump(payload, output_file, ensure_ascii=False, indent=2)
            output_file.write("\n")
            return

        for entity in entities:
            output_file.write(json.dumps(entity, ensure_ascii=False))
            output_file.write("\n")


def parse_args():
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(
        description="生成本地 Lattice-style 模拟 Surface Vessel entity JSON。"
    )
    parser.add_argument("--count", type=int, default=1, help="生成 entity 的数量")
    parser.add_argument(
        "--center-lat",
        type=float,
        default=DEFAULT_CENTER_LAT,
        help="随机位置中心点纬度",
    )
    parser.add_argument(
        "--center-lon",
        type=float,
        default=DEFAULT_CENTER_LON,
        help="随机位置中心点经度",
    )
    parser.add_argument(
        "--radius-deg",
        type=float,
        default=DEFAULT_RADIUS_DEG,
        help="经纬度随机偏移半径",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help="输出文件路径",
    )
    parser.add_argument(
        "--format",
        choices=("json", "jsonl"),
        default="jsonl",
        help="输出格式",
    )
    parser.add_argument(
        "--source-name",
        default=DEFAULT_SOURCE_NAME,
        help="模拟 AIS 数据来源名称",
    )
    parser.add_argument(
        "--start-mmsi",
        type=int,
        default=DEFAULT_START_MMSI,
        help="模拟 MMSI 起始值",
    )
    ais_metadata_group = parser.add_mutually_exclusive_group()
    ais_metadata_group.add_argument(
        "--include-ais-metadata",
        dest="include_ais_metadata",
        action="store_true",
        help="是否输出 metadata.ais 扩展字段",
    )
    ais_metadata_group.add_argument(
        "--no-include-ais-metadata",
        dest="include_ais_metadata",
        action="store_false",
        help="不输出 metadata.ais 扩展字段",
    )
    parser.set_defaults(include_ais_metadata=True)
    return parser.parse_args()


def main():
    """程序入口。"""
    args = parse_args()
    try:
        validate_args(args)
    except ValueError as error:
        raise SystemExit(f"参数错误: {error}") from error

    entities = [
        build_surface_vessel_entity(
            index,
            args.center_lat,
            args.center_lon,
            args.radius_deg,
            args.source_name,
            args.start_mmsi,
            args.include_ais_metadata,
        )
        for index in range(args.count)
    ]
    write_output(entities, args.output, args.format)


if __name__ == "__main__":
    main()
