#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def inspect(path: Path) -> dict:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        rows = list(reader)
    missing = {field: sum(row.get(field, "") == "" for row in rows) for field in fields}
    return {
        "path": str(path),
        "rowCount": len(rows),
        "columns": fields,
        "missingValues": missing,
        "firstTimestamp": rows[0].get(fields[0]) if rows and fields else None,
        "lastTimestamp": rows[-1].get(fields[0]) if rows and fields else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect a small flight telemetry CSV")
    parser.add_argument("csv", type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect(args.csv), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
