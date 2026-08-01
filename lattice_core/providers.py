"""外部智能能力的端口定义，Dify 只是其中一种实现。"""

from typing import Any, Protocol, Sequence


class LLMProvider(Protocol):
    @property
    def name(self) -> str: ...

    def generate(self, messages: Sequence[dict[str, Any]], *, schema: dict[str, Any] | None = None) -> dict[str, Any]: ...


class KnowledgeRetriever(Protocol):
    @property
    def name(self) -> str: ...

    def search(
        self,
        query: str,
        *,
        filters: dict[str, Any] | None = None,
        limit: int = 5,
    ) -> list[dict[str, Any]]: ...


class RecommendationProvider(Protocol):
    @property
    def name(self) -> str: ...

    def recommend(self, context: dict[str, Any]) -> dict[str, Any]: ...
