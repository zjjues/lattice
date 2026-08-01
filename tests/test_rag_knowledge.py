import tempfile
import unittest
from pathlib import Path

from lattice_core.rag import LocalHashEmbedding, RagKnowledgeBase, split_text


class RagKnowledgeTests(unittest.TestCase):
    def test_upload_chunk_inspect_and_vector_search(self):
        with tempfile.TemporaryDirectory() as directory:
            kb = RagKnowledgeBase(Path(directory) / "rag.sqlite3", LocalHashEmbedding(128))
            document = kb.add_document(
                "发动机故障.md",
                "发动机故障时应核验空速并保持安全滑翔速度。\n操作员必须确认处置建议。".encode(),
                "text/markdown", 100, 10,
            )
            self.assertEqual(document["chunk_count"], 1)
            self.assertIn("核验空速", kb.chunks(document["id"])[0]["content"])
            results = kb.search("发动机故障空速", limit=1)
            self.assertEqual(results[0]["documentId"], document["id"])
            self.assertGreater(results[0]["score"], 0)

    def test_chunk_overlap_is_bounded(self):
        chunks = split_text("测试内容。" * 80, chunk_size=100, overlap=20)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk) <= 100 for chunk in chunks))


if __name__ == "__main__":
    unittest.main()
