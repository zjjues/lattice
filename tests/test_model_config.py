import tempfile
import unittest
from pathlib import Path

from lattice_core.model_config import ModelProviderConfigStore, classify_models, mask_secret
from lattice_core.rag import FastEmbedEmbedding, LOCAL_BGE_MODEL


class ModelConfigTests(unittest.TestCase):
    def test_classification_and_masking(self):
        models = classify_models(["chat-pro", "bge-m3", "text-embedding-3-small"])
        self.assertEqual(models["chat"], ["chat-pro"])
        self.assertEqual(models["embedding"], ["bge-m3", "text-embedding-3-small"])
        self.assertNotIn("secret-value", mask_secret("secret-value"))

    def test_local_bge_provider_has_stable_contract(self):
        provider = FastEmbedEmbedding("/tmp/lattice-test-model-cache")
        self.assertEqual(provider.model_name, LOCAL_BGE_MODEL)
        self.assertEqual(provider.dimension, 512)
        self.assertEqual(provider.name, "local-bge-small-zh-v1.5")

    def test_public_config_never_returns_plain_key(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ModelProviderConfigStore(Path(directory) / "provider.json")
            public = store.save({"baseUrl": "https://example.test/v1", "apiKey": "secret-value", "chatModel": "chat-pro", "embeddingModel": "bge-m3", "embeddingDimension": 1024})
            self.assertTrue(public["apiKeyConfigured"])
            self.assertNotIn("apiKey", public)
            self.assertNotIn("secret-value", str(public))
            self.assertEqual(store.load_private()["apiKey"], "secret-value")


if __name__ == "__main__":
    unittest.main()
