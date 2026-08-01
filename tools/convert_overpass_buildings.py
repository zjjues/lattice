#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def number(value: object) -> float | None:
    if not isinstance(value, str):
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", value)
    return float(match.group()) if match else None


def convert(source: Path) -> dict:
    payload = json.loads(source.read_text(encoding="utf-8"))
    features = []
    for element in payload.get("elements", []):
        geometry = element.get("geometry")
        if not isinstance(geometry, list) or len(geometry) < 4:
            continue
        coordinates = [[point["lon"], point["lat"]] for point in geometry]
        if coordinates[0] != coordinates[-1]:
            coordinates.append(coordinates[0])
        tags = element.get("tags", {})
        levels = number(tags.get("building:levels"))
        height = number(tags.get("height"))
        if height is None:
            height = levels * 3.2 if levels else 10.0 + (int(element["id"]) % 5) * 3.0
        min_height = number(tags.get("min_height"))
        if min_height is None:
            min_level = number(tags.get("building:min_level"))
            min_height = (min_level or 0) * 3.2
        features.append({
            "type": "Feature",
            "properties": {
                "osmId": element["id"], "name": tags.get("name"),
                "height": round(height, 2), "minHeight": round(min_height, 2),
                "levels": levels, "building": tags.get("building", "yes"),
            },
            "geometry": {"type": "Polygon", "coordinates": [coordinates]},
        })
    return {"type": "FeatureCollection", "features": features}


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert Overpass building ways to GeoJSON")
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result = convert(args.source)
    args.output.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {len(result['features'])} buildings to {args.output}")


if __name__ == "__main__":
    main()
