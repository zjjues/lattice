from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class KnowledgeHit:
    id: str
    title: str
    text: str
    score: float
    layer: str
    source: str


class LocalKnowledgeRetriever:
    """Dependency-free local retriever implementing the existing search concept."""

    def __init__(self, root: str | Path):
        self.root = Path(root)

    def search(self, query: str, *, limit: int = 3, layer: str | None = None) -> list[dict]:
        terms = {term.lower() for term in query.replace("_", " ").split() if term}
        hits: list[KnowledgeHit] = []
        for path in self.root.rglob("*.md"):
            text = path.read_text(encoding="utf-8")
            doc_layer = path.parent.name
            if layer and doc_layer != layer:
                continue
            haystack = text.lower()
            overlap = sum(term in haystack for term in terms)
            score = overlap / max(len(terms), 1)
            if score or not terms:
                title = next((line[2:].strip() for line in text.splitlines() if line.startswith("# ")), path.stem)
                hits.append(KnowledgeHit(path.stem, title, text, score, doc_layer, str(path)))
        hits.sort(key=lambda hit: (-hit.score, hit.id))
        return [hit.__dict__ for hit in hits[:limit]]
