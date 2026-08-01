from __future__ import annotations

import json
import urllib.request


class OpenAICompatibleProvider:
    """Minimal provider for OpenAI-compatible chat-completions endpoints."""

    def __init__(self, base_url: str, api_key: str, model: str, timeout: float = 20):
        self.url = f"{base_url.rstrip('/')}/chat/completions"
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def generate(self, prompt: str, *, system: str | None = None) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        request = urllib.request.Request(
            self.url,
            data=json.dumps({"model": self.model, "messages": messages, "temperature": 0.1}).encode(),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            body = json.load(response)
        return body["choices"][0]["message"]["content"]
