#!/usr/bin/env python3
"""将 knowledge/sops 中的 Markdown 批量上传到 RAG API。"""
from __future__ import annotations

import argparse
import json
import mimetypes
import urllib.request
import uuid
from pathlib import Path


def multipart(path: Path, chunk_size: int, overlap: int) -> tuple[bytes, str]:
    boundary = f"----lattice-{uuid.uuid4().hex}"
    parts: list[bytes] = []
    for name, value in (("chunk_size", str(chunk_size)), ("overlap", str(overlap))):
        parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode())
    media_type = mimetypes.guess_type(path.name)[0] or "text/markdown"
    parts.append(
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{path.name}\"\r\nContent-Type: {media_type}\r\n\r\n".encode()
        + path.read_bytes()
        + b"\r\n"
    )
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), boundary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path, nargs="?", default=Path("knowledge/sops"))
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--chunk-size", type=int, default=500)
    parser.add_argument("--overlap", type=int, default=80)
    args = parser.parse_args()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for path in sorted(args.root.rglob("*.md")):
        body, boundary = multipart(path, args.chunk_size, args.overlap)
        request = urllib.request.Request(
            f"{args.base_url.rstrip('/')}/api/v1/rag/documents",
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )
        with opener.open(request, timeout=90) as response:
            result = json.load(response)
        print(f"{path}: {result['chunk_count']} chunks ({result['embedding_provider']})")


if __name__ == "__main__":
    main()
