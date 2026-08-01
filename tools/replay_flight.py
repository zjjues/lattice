#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lattice_core.flight.adapters import AlfaAdapter, IdfDsAdapter
from lattice_core.flight.mapping import frame_to_ingest_event


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay a flight CSV into Fake Lattice")
    parser.add_argument("csv", type=Path)
    parser.add_argument("--dataset", choices=("idf_ds", "alfa"), required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:8081")
    parser.add_argument("--interval", type=float, default=0.25)
    parser.add_argument("--max-frames", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    adapter_type = IdfDsAdapter if args.dataset == "idf_ds" else AlfaAdapter
    for index, frame in enumerate(adapter_type(args.csv).frames(), start=1):
        if args.max_frames and index > args.max_frames:
            break
        payload = frame_to_ingest_event(frame)
        if args.dry_run:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            request = urllib.request.Request(
                f"{args.base_url.rstrip('/')}/api/v1/ingest/events",
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=10) as response:
                print(response.status, frame.timestamp_ms, frame.source_id)
        if args.interval > 0:
            time.sleep(args.interval)


if __name__ == "__main__":
    main()
