"""Smoke test with the REAL embedding model and persistent ChromaDB.

Skipped unless RAG_SMOKE=1 because the first run downloads the ONNX model
(~80 MB to ~/.cache/chroma) and needs internet access.

PowerShell:
    $env:RAG_SMOKE = "1"
    python -m unittest tests.test_rag_smoke_real_embeddings -v
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rag_test_support import write_pdf  # noqa: E402

from customer_support_coach.rag import RagConfig, RagPipeline  # noqa: E402


@unittest.skipUnless(os.environ.get("RAG_SMOKE") == "1", "set RAG_SMOKE=1 to run the real-model smoke test")
class TestRealModelSmoke(unittest.TestCase):
    def test_semantic_retrieval_with_real_model(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = Path(tmp)
            write_pdf(root / "account.pdf", ["If you forgot your login credentials, use the recovery link "
                                              "on the sign-in page and we will email you a way to choose a new secret."])
            write_pdf(root / "delivery.pdf", ["Parcels are dispatched from our warehouse and normally arrive "
                                               "within five working days."])
            write_pdf(root / "refunds.pdf", ["You can send a product back within thirty days to get your "
                                              "money returned."])
            config = RagConfig(persist_directory=root / "chroma")
            with RagPipeline(config) as rag:
                report = rag.ingest_directory(root)
                self.assertTrue(report.all_ok, report.summary())
                top = rag.search("I can't remember my password", top_k=3)
                self.assertEqual(len(top), 3)
                # synonyms only: no keyword overlap between query and best chunk
                self.assertEqual(top[0].source_filename, "account.pdf")
                self.assertEqual(rag.get_collection_stats()["embedding_model"], "onnx-all-MiniLM-L6-v2")


if __name__ == "__main__":
    unittest.main()
