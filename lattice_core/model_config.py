"""本地模型供应商配置、发现与能力检测。"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

EMBEDDING_HINTS = ("embed", "embedding", "bge", "e5", "gte", "text2vec")


def validate_base_url(value: str) -> str:
    normalized = value.strip().rstrip("/")
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("服务地址必须是有效的 HTTP 或 HTTPS 地址")
    return normalized


def mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:3]}{'*' * 8}{value[-4:]}"


def classify_models(model_ids: list[str]) -> dict[str, list[str]]:
    embedding = sorted({item for item in model_ids if any(hint in item.lower() for hint in EMBEDDING_HINTS)})
    chat = sorted({item for item in model_ids if item not in embedding})
    return {"chat": chat, "embedding": embedding, "all": sorted(set(model_ids))}


class ModelProviderConfigStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def load_private(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"providerType": "openai-compatible", "baseUrl": "", "apiKey": "", "chatModel": "", "embeddingModel": "", "embeddingDimension": 0}
        value = json.loads(self.path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}

    def public(self) -> dict[str, Any]:
        value = self.load_private()
        return {
            "providerType": value.get("providerType", "openai-compatible"),
            "baseUrl": value.get("baseUrl", ""),
            "apiKeyConfigured": bool(value.get("apiKey")),
            "apiKeyMasked": mask_secret(str(value.get("apiKey", ""))),
            "chatModel": value.get("chatModel", ""),
            "embeddingModel": value.get("embeddingModel", ""),
            "embeddingDimension": value.get("embeddingDimension", 0),
        }

    def save(self, payload: dict[str, Any]) -> dict[str, Any]:
        previous = self.load_private()
        value = {
            "providerType": "openai-compatible",
            "baseUrl": validate_base_url(str(payload.get("baseUrl") or "")),
            "apiKey": str(payload.get("apiKey") or previous.get("apiKey") or ""),
            "chatModel": str(payload.get("chatModel") or ""),
            "embeddingModel": str(payload.get("embeddingModel") or ""),
            "embeddingDimension": int(payload.get("embeddingDimension") or 0),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.chmod(temporary, 0o600)
        temporary.replace(self.path)
        return self.public()


class OpenAICompatibleModelClient:
    def __init__(self, base_url: str, api_key: str, timeout: float = 20):
        self.base_url = validate_base_url(base_url)
        self.api_key = api_key
        self.timeout = timeout

    def _request(self, path: str, payload: dict | None = None) -> dict:
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        data, method = None, "GET"
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
            method = "POST"
        request = urllib.request.Request(f"{self.base_url}{path}", data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            detail = error.read(500).decode("utf-8", errors="replace")
            raise ValueError(f"模型服务返回 HTTP {error.code}: {detail}") from error
        except urllib.error.URLError as error:
            raise ValueError(f"无法连接模型服务: {error.reason}") from error

    def discover(self) -> dict[str, list[str]]:
        body = self._request("/models")
        ids = [str(item.get("id")) for item in body.get("data", []) if isinstance(item, dict) and item.get("id")]
        return classify_models(ids)

    def test_chat(self, model: str) -> dict[str, Any]:
        body = self._request("/chat/completions", {"model": model, "messages": [{"role": "user", "content": "只回答：连接正常"}], "temperature": 0, "max_tokens": 16})
        content = body["choices"][0]["message"]["content"]
        return {"ok": True, "capability": "chat", "model": model, "sample": str(content)[:120]}

    def test_embedding(self, model: str) -> dict[str, Any]:
        body = self._request("/embeddings", {"model": model, "input": ["飞行安全知识库连接测试"]})
        vector = body["data"][0]["embedding"]
        return {"ok": True, "capability": "embedding", "model": model, "dimension": len(vector)}
