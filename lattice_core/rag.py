"""轻量 Embedding RAG 知识库。"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sqlite3
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class EmbeddingProvider(Protocol):
    name: str
    dimension: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class LocalHashEmbedding:
    """离线回退向量器；生产环境可切换到真实 Embedding API。"""

    name = "local-hash-v1"

    def __init__(self, dimension: int = 384):
        self.dimension = dimension

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._one(text) for text in texts]

    def _one(self, text: str) -> list[float]:
        normalized = re.sub(r"\s+", " ", text.lower()).strip()
        tokens = re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]", normalized)
        features = tokens + [normalized[index : index + 2] for index in range(max(0, len(normalized) - 1))]
        vector = [0.0] * self.dimension
        for feature in features:
            digest = hashlib.sha256(feature.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimension
            vector[index] += 1.0 if digest[4] & 1 else -1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]


class OpenAICompatibleEmbedding:
    name = "openai-compatible"

    def __init__(self, base_url: str, api_key: str, model: str, dimension: int = 0, timeout: float = 30):
        self.url = f"{base_url.rstrip('/')}/embeddings"
        self.api_key = api_key
        self.model = model
        self.dimension = dimension
        self.timeout = timeout

    def embed(self, texts: list[str]) -> list[list[float]]:
        request = urllib.request.Request(
            self.url,
            data=json.dumps({"model": self.model, "input": texts}).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            body = json.load(response)
        vectors = [item["embedding"] for item in sorted(body["data"], key=lambda item: item["index"])]
        if vectors:
            self.dimension = len(vectors[0])
        return vectors


LOCAL_BGE_MODEL = "BAAI/bge-small-zh-v1.5"


class FastEmbedEmbedding:
    """CPU 友好的本地中文 BGE Provider，模型缓存可放在 D 盘。"""

    name = "local-bge-small-zh-v1.5"
    dimension = 512

    def __init__(self, cache_dir: str | Path, model_name: str = LOCAL_BGE_MODEL):
        self.cache_dir = Path(cache_dir)
        self.model_name = model_name
        self._model = None

    def _load(self):
        if self._model is None:
            from fastembed import TextEmbedding
            from fastembed.common.model_description import ModelSource, PoolingType
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            extracted_model_dir = self.cache_dir / "tmp" / "fast-bge-small-zh-v1.5"
            runtime_name = "lattice/bge-small-zh-v1.5-url"
            if runtime_name not in {item["model"] for item in TextEmbedding.list_supported_models()}:
                TextEmbedding.add_custom_model(
                    model=runtime_name,
                    pooling=PoolingType.CLS,
                    normalization=True,
                    sources=ModelSource(
                        url="https://storage.googleapis.com/qdrant-fastembed/fast-bge-small-zh-v1.5.tar.gz",
                        _deprecated_tar_struct=True,
                    ),
                    dim=512,
                    model_file="model_optimized.onnx",
                    description="BGE small Chinese v1.5 via FastEmbed URL source",
                    license="mit",
                    size_in_gb=0.09,
                )
            # FastEmbed 的旧式 URL 下载器在 Windows 挂载盘上可能已完成解压，
            # 却在缓存目录重命名阶段失败。优先复用已解压的本地目录，
            # 避免每次启动都重新下载模型。
            local_model_path = None
            if (extracted_model_dir / "model_optimized.onnx").is_file():
                local_model_path = str(extracted_model_dir)
            self._model = TextEmbedding(
                model_name=runtime_name,
                cache_dir=str(self.cache_dir),
                specific_model_path=local_model_path,
            )
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [vector.tolist() for vector in self._load().embed(texts)]


def embedding_from_env() -> EmbeddingProvider:
    base_url = os.getenv("EMBEDDING_BASE_URL", "").strip()
    model = os.getenv("EMBEDDING_MODEL", "").strip()
    if base_url and model:
        return OpenAICompatibleEmbedding(
            base_url, os.getenv("EMBEDDING_API_KEY", ""), model,
            int(os.getenv("EMBEDDING_DIMENSION", "0") or 0),
        )
    return LocalHashEmbedding(int(os.getenv("EMBEDDING_DIMENSION", "384")))


def split_text(text: str, chunk_size: int = 600, overlap: int = 100) -> list[str]:
    text = re.sub(r"\r\n?", "\n", text).strip()
    if not text:
        return []
    chunk_size = max(100, min(chunk_size, 4000))
    overlap = max(0, min(overlap, chunk_size // 2))
    chunks, start = [], 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        if end < len(text):
            candidates = [text.rfind(mark, start + chunk_size // 2, end) for mark in ("\n", "。", "！", "？", ". ")]
            boundary = max(candidates)
            if boundary > start:
                end = boundary + 1
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(start + 1, end - overlap)
    return chunks


@dataclass
class RagKnowledgeBase:
    db_path: Path
    embedding: EmbeddingProvider

    def __post_init__(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as database:
            database.executescript("""
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, media_type TEXT,
                    size_bytes INTEGER NOT NULL, chunk_count INTEGER NOT NULL,
                    embedding_provider TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS chunks (
                    id TEXT PRIMARY KEY, document_id TEXT NOT NULL, chunk_index INTEGER NOT NULL,
                    content TEXT NOT NULL, vector TEXT NOT NULL,
                    FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(document_id, chunk_index);
            """)

    def _connect(self) -> sqlite3.Connection:
        database = sqlite3.connect(self.db_path)
        database.row_factory = sqlite3.Row
        database.execute("PRAGMA foreign_keys=ON")
        return database

    def add_document(self, name: str, content: bytes, media_type: str | None, chunk_size: int, overlap: int) -> dict:
        text = content.decode("utf-8-sig")
        chunks = split_text(text, chunk_size, overlap)
        if not chunks:
            raise ValueError("文档没有可索引的文本内容")
        vectors = self.embedding.embed(chunks)
        document_id = uuid.uuid4().hex
        with self._connect() as database:
            database.execute(
                "INSERT INTO documents(id,name,media_type,size_bytes,chunk_count,embedding_provider) VALUES(?,?,?,?,?,?)",
                (document_id, name, media_type, len(content), len(chunks), self.embedding.name),
            )
            database.executemany(
                "INSERT INTO chunks(id,document_id,chunk_index,content,vector) VALUES(?,?,?,?,?)",
                [(uuid.uuid4().hex, document_id, index, chunk, json.dumps(vector)) for index, (chunk, vector) in enumerate(zip(chunks, vectors))],
            )
        return self.get_document(document_id)

    def list_documents(self) -> list[dict]:
        with self._connect() as database:
            rows = database.execute("SELECT * FROM documents ORDER BY created_at DESC, id DESC").fetchall()
        return [dict(row) for row in rows]

    def get_document(self, document_id: str) -> dict:
        with self._connect() as database:
            row = database.execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone()
        if row is None:
            raise KeyError(document_id)
        return dict(row)

    def chunks(self, document_id: str) -> list[dict]:
        with self._connect() as database:
            rows = database.execute(
                "SELECT id,document_id,chunk_index,content FROM chunks WHERE document_id=? ORDER BY chunk_index", (document_id,)
            ).fetchall()
        return [dict(row) for row in rows]

    def search(self, query: str, limit: int = 5) -> list[dict]:
        query_vector = self.embedding.embed([query])[0]
        with self._connect() as database:
            rows = database.execute(
                "SELECT c.id,c.document_id,c.chunk_index,c.content,c.vector,d.name FROM chunks c JOIN documents d ON d.id=c.document_id"
            ).fetchall()
        results = []
        for row in rows:
            vector = json.loads(row["vector"])
            score = sum(left * right for left, right in zip(query_vector, vector))
            results.append({"chunkId": row["id"], "documentId": row["document_id"], "documentName": row["name"], "chunkIndex": row["chunk_index"], "content": row["content"], "score": round(score, 6)})
        return sorted(results, key=lambda item: item["score"], reverse=True)[: max(1, min(limit, 20))]
