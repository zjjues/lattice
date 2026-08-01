"""旧实现的 Provider 适配器，便于逐步替换 Dify 和文件知识库。"""

from typing import Any, Callable


class CallableKnowledgeRetriever:
    name = "local-file-kb"

    def __init__(self, search: Callable[..., list[dict[str, Any]]]) -> None:
        self._search = search

    def search(self, query: str, *, filters: dict[str, Any] | None = None, limit: int = 5) -> list[dict[str, Any]]:
        context = {"filters": filters or {}}
        return self._search(query, limit=limit, context=context)


class CallableRecommendationProvider:
    name = "dify-with-local-fallback"

    def __init__(self, recommend: Callable[[dict[str, Any]], dict[str, Any]]) -> None:
        self._recommend = recommend

    def recommend(self, context: dict[str, Any]) -> dict[str, Any]:
        return self._recommend(context)
