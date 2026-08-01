"""以物理文件夹为边界的知识库目录。"""
from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any


class KnowledgeBaseCatalog:
    def __init__(self, root: str | Path, index_path: str | Path):
        self.root = Path(root)
        self.index_path = Path(index_path)
        self.root.mkdir(parents=True, exist_ok=True)
        self.index_path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict[str, Any]:
        if not self.index_path.is_file():
            return {"documentKnowledgeBases": {}}
        value = json.loads(self.index_path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {"documentKnowledgeBases": {}}

    def _save(self, value: dict[str, Any]) -> None:
        temporary = self.index_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(self.index_path)

    @staticmethod
    def _safe_id(value: str) -> str:
        slug = re.sub(r"[^a-z0-9_-]+", "-", value.strip().lower()).strip("-")
        return slug[:48] or f"kb-{uuid.uuid4().hex[:10]}"

    @staticmethod
    def _metadata(folder: Path) -> dict[str, Any]:
        defaults = {
            "airspace": {"name": "空域安全", "description": "禁限飞区域、入侵与空域冲突处置"},
            "flight": {"name": "飞行安全", "description": "姿态、空速、发动机与碰撞风险处置"},
            "governance": {"name": "审批与治理", "description": "人工确认、审批边界和安全约束"},
            "navigation": {"name": "导航与定位", "description": "GNSS退化、定位异常与导航处置"},
            "platform": {"name": "平台与数据", "description": "链路、电池、传感器与数据质量"},
        }
        path = folder / ".knowledge-base.json"
        if path.is_file():
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(value, dict):
                    return value
            except (OSError, json.JSONDecodeError):
                pass
        return defaults.get(folder.name, {"name": folder.name, "description": ""})

    def _folder(self, knowledge_base_id: str) -> Path:
        if not re.fullmatch(r"[a-zA-Z0-9_-]+", knowledge_base_id):
            raise KeyError(knowledge_base_id)
        folder = self.root / knowledge_base_id
        if not folder.is_dir():
            raise KeyError(knowledge_base_id)
        return folder

    def sync(self, documents: list[dict[str, Any]]) -> None:
        """将已有向量文档按同名源文件归入现有文件夹。"""
        index = self._load()
        mapping = index.setdefault("documentKnowledgeBases", {})
        by_name: dict[str, str] = {}
        for folder in self.root.iterdir():
            if not folder.is_dir() or folder.name.startswith("."):
                continue
            for path in folder.iterdir():
                if path.is_file() and not path.name.startswith("."):
                    by_name.setdefault(path.name, folder.name)
        changed = False
        for document in documents:
            document_id, name = str(document.get("id")), str(document.get("name"))
            if document_id not in mapping and name in by_name:
                mapping[document_id] = by_name[name]
                changed = True
        if changed or not self.index_path.exists():
            self._save(index)

    def list(self, documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
        self.sync(documents)
        mapping = self._load().get("documentKnowledgeBases", {})
        result = []
        for folder in sorted(self.root.iterdir(), key=lambda item: item.name):
            if not folder.is_dir() or folder.name.startswith("."):
                continue
            metadata = self._metadata(folder)
            matched = [doc for doc in documents if mapping.get(str(doc.get("id"))) == folder.name]
            result.append({
                "id": folder.name, "name": metadata.get("name") or folder.name,
                "description": metadata.get("description") or "",
                "folder": str(folder.relative_to(self.root.parent.parent)),
                "documentCount": len(matched),
                "chunkCount": sum(int(doc.get("chunk_count") or 0) for doc in matched),
                "documents": matched,
            })
        return result

    def get(self, knowledge_base_id: str, documents: list[dict[str, Any]]) -> dict[str, Any]:
        item = next((item for item in self.list(documents) if item["id"] == knowledge_base_id), None)
        if item is None:
            raise KeyError(knowledge_base_id)
        return item

    def create(self, name: str, description: str = "") -> dict[str, Any]:
        name = name.strip()
        if not name:
            raise ValueError("知识库名称不能为空")
        base_id = self._safe_id(name)
        candidate, suffix = base_id, 2
        while (self.root / candidate).exists():
            candidate, suffix = f"{base_id}-{suffix}", suffix + 1
        folder = self.root / candidate
        folder.mkdir()
        (folder / ".knowledge-base.json").write_text(json.dumps({
            "name": name, "description": description.strip(),
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return {"id": candidate, "name": name, "description": description.strip(), "documentCount": 0, "chunkCount": 0, "documents": []}

    def store_file(self, knowledge_base_id: str, name: str, content: bytes) -> Path:
        folder = self._folder(knowledge_base_id)
        safe_name = Path(name).name
        if not safe_name or safe_name.startswith("."):
            raise ValueError("文件名无效")
        target = folder / safe_name
        if target.exists():
            target = folder / f"{target.stem}-{uuid.uuid4().hex[:6]}{target.suffix}"
        target.write_bytes(content)
        return target

    def register_document(self, document_id: str, knowledge_base_id: str) -> None:
        self._folder(knowledge_base_id)
        index = self._load()
        index.setdefault("documentKnowledgeBases", {})[document_id] = knowledge_base_id
        self._save(index)

    def document_ids(self, knowledge_base_id: str) -> set[str]:
        self._folder(knowledge_base_id)
        mapping = self._load().get("documentKnowledgeBases", {})
        return {document_id for document_id, base_id in mapping.items() if base_id == knowledge_base_id}
