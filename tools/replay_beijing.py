#!/usr/bin/env python3
"""Replay a tiny flight fixture around Beijing without changing its dynamics."""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lattice_core.flight.adapters import AlfaAdapter, IdfDsAdapter
from lattice_core.flight.mapping import frame_to_ingest_event


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay a sample around a Beijing demo origin")
    parser.add_argument("csv", type=Path)
    parser.add_argument("--dataset", choices=("idf_ds", "alfa"), required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--origin-lat", type=float, default=39.9042)
    parser.add_argument("--origin-lon", type=float, default=116.4074)
    parser.add_argument("--interval", type=float, default=0.5)
    parser.add_argument("--source-id", default="beijing-flight-demo")
    args = parser.parse_args()

    adapter_type = IdfDsAdapter if args.dataset == "idf_ds" else AlfaAdapter
    frames = list(adapter_type(args.csv, source_id=args.source_id).frames())
    if not frames:
        raise SystemExit("CSV contains no frames")
    first_lat = frames[0].latitude_deg or 0.0
    first_lon = frames[0].longitude_deg or 0.0
    for frame in frames:
        shifted = replace(
            frame,
            latitude_deg=args.origin_lat + ((frame.latitude_deg or first_lat) - first_lat),
            longitude_deg=args.origin_lon + ((frame.longitude_deg or first_lon) - first_lon),
        )
        payload = frame_to_ingest_event(shifted)
        request = urllib.request.Request(
            f"{args.base_url.rstrip('/')}/api/v1/ingest/events",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            result = json.load(response)
        print(shifted.timestamp_ms, shifted.latitude_deg, shifted.longitude_deg, result["entityId"])
        if args.interval:
            time.sleep(args.interval)


if __name__ == "__main__":
    main()
