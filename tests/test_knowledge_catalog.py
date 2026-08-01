import tempfile
import unittest
from pathlib import Path

from lattice_core.knowledge.catalog import KnowledgeBaseCatalog


class KnowledgeBaseCatalogTests(unittest.TestCase):
    def test_folders_are_knowledge_bases_and_existing_docs_are_mapped(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "knowledge"
            flight = root / "flight"
            flight.mkdir(parents=True)
            (flight / "engine.md").write_text("发动机处置", encoding="utf-8")
            catalog = KnowledgeBaseCatalog(root, Path(directory) / "index.json")
            docs = [{"id": "doc-1", "name": "engine.md", "chunk_count": 2}]
            bases = catalog.list(docs)
            self.assertEqual(bases[0]["id"], "flight")
            self.assertEqual(bases[0]["documentCount"], 1)
            self.assertEqual(bases[0]["chunkCount"], 2)

    def test_create_base_and_store_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "knowledge"
            catalog = KnowledgeBaseCatalog(root, Path(directory) / "index.json")
            created = catalog.create("飞行安全", "飞行处置规则")
            target = catalog.store_file(created["id"], "sop.md", b"sop")
            self.assertTrue(target.is_file())
            self.assertEqual(catalog.get(created["id"], [])["name"], "飞行安全")

    def test_register_document_scopes_search_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "knowledge"
            catalog = KnowledgeBaseCatalog(root, Path(directory) / "index.json")
            created = catalog.create("test")
            catalog.register_document("doc-1", created["id"])
            self.assertEqual(catalog.document_ids(created["id"]), {"doc-1"})

    def test_rejects_invalid_folder_id(self):
        with tempfile.TemporaryDirectory() as directory:
            catalog = KnowledgeBaseCatalog(Path(directory) / "knowledge", Path(directory) / "index.json")
            with self.assertRaises(KeyError):
                catalog.document_ids("../escape")


if __name__ == "__main__":
    unittest.main()
