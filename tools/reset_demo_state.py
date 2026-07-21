#!/usr/bin/env python3
"""重置本地 fake Lattice 演示数据。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
OBJECTS_DIR = ROOT / "objects"

STORE_DEFAULTS = {
    DATA_DIR / "entities_store.json": {"entities": {}},
    DATA_DIR / "tasks_store.json": {"tasks": {}},
    DATA_DIR / "objects_store.json": {"objects": {}},
    DATA_DIR / "alerts_store.json": {"alerts": {}},
    DATA_DIR / "ingest_events_store.json": {"events": {}},
    DATA_DIR / "recommendations_store.json": {"recommendations": {}},
}


def reset_store_file(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def remove_object_files() -> list[str]:
    removed = []
    OBJECTS_DIR.mkdir(parents=True, exist_ok=True)
    for item in sorted(OBJECTS_DIR.iterdir()):
        if item.is_file():
            item.unlink()
            removed.append(item.name)
    return removed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="重置本地 fake Lattice 演示数据。")
    parser.add_argument(
        "--keep-objects",
        action="store_true",
        help="保留 objects/ 目录下的附件文件，只重置 JSON store",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    for path, payload in STORE_DEFAULTS.items():
        reset_store_file(path, payload)

    removed_files = []
    if not args.keep_objects:
        removed_files = remove_object_files()

    print("已重置以下 store 文件：")
    for path in STORE_DEFAULTS:
        print(f"- {path.relative_to(ROOT)}")

    if args.keep_objects:
        print("已保留 objects/ 目录下的附件文件")
    else:
        print(f"已删除 {len(removed_files)} 个附件文件")
        for name in removed_files[:10]:
            print(f"  - {name}")
        if len(removed_files) > 10:
            print(f"  - ... 共 {len(removed_files)} 个")

    print("当前演示环境已恢复到干净初始态。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
