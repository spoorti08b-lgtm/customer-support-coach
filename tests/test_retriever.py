"""Unit tests for top-k retrieval (hashing test embedder + real ChromaDB)."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rag_test_support import FailingEmbedder, HashingTestEmbedder  # noqa: E402

from customer_support_coach.rag import (  # noqa: E402
    Chunk,
    ChromaVectorStore,
    EmbeddingError,
    InvalidInputError,
    InvalidQueryError,
    Retriever,
)

TEXTS = {
    "pw": "To reset your password open Settings and choose Forgot Password then check your email.",
    "ship": "Standard shipping takes five business days and tracking numbers are emailed.",
    "ret": "Items can be returned within thirty days for a full refund with the receipt.",
    "bill": "Invoices are generated monthly and can be downloaded from the billing page.",
    "chat": "Live chat support is available from nine to five on weekdays.",
}


class RetrieverTestCase(unittest.TestCase):
    def build(self, keys):
        self.embedder = HashingTestEmbedder()
        chunks = []
        for i, k in enumerate(keys):
            chunks.append(Chunk(f"doc-{k}:c00000", TEXTS[k], {
                "doc_id": f"doc-{k}", "filename": f"{k}.pdf", "page_start": i + 1,
                "page_end": i + 2, "chunk_index": 0, "chunk_count": 1, "content_hash": k}))
        self.store.upsert_chunks(chunks, self.embedder.embed_documents([c.text for c in chunks]))
        return Retriever(self.embedder, self.store)

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.store = ChromaVectorStore(Path(self._tmp.name) / "c", "retr_tests", HashingTestEmbedder.name)

    def tearDown(self):
        self.store.close()
        self._tmp.cleanup()


class TestRetriever(RetrieverTestCase):
    def test_default_returns_three_best_first(self):
        r = self.build(list(TEXTS))
        res = r.search("how do I reset my password")
        self.assertEqual(len(res), 3)
        self.assertEqual(res[0].source_filename, "pw.pdf")
        self.assertEqual([x.rank for x in res], [1, 2, 3])
        self.assertEqual(sorted(x.distance for x in res), [x.distance for x in res])

    def test_fewer_results_when_fewer_chunks(self):
        r = self.build(["pw", "ship"])
        self.assertEqual(len(r.search("password")), 2)

    def test_top_k_configurable_and_never_exceeded(self):
        r = self.build(list(TEXTS))
        self.assertEqual(len(r.search("refund", top_k=1)), 1)
        self.assertEqual(len(r.search("refund", top_k=5)), 5)

    def test_empty_collection_returns_empty_list(self):
        r = Retriever(HashingTestEmbedder(), self.store)
        self.assertEqual(r.search("anything"), [])

    def test_invalid_queries(self):
        r = self.build(["pw"])
        for bad in ["", "   ", "\n\t", None, 42]:
            with self.assertRaises(InvalidQueryError):
                r.search(bad)

    def test_invalid_top_k(self):
        r = self.build(["pw"])
        for bad in [0, -1, True, "3", 2.5, 10_000]:
            with self.assertRaises(InvalidInputError):
                r.search("password", top_k=bad)

    def test_source_attribution_and_fields(self):
        r = self.build(["ret"])
        hit = r.search("refund policy")[0]
        self.assertEqual(hit.chunk_id, "doc-ret:c00000")
        self.assertEqual(hit.text, TEXTS["ret"])
        self.assertEqual((hit.page_start, hit.page_end, hit.chunk_index), (1, 2, 0))
        self.assertEqual(hit.distance_metric, "cosine")
        self.assertAlmostEqual(hit.cosine_similarity, 1 - hit.distance)
        self.assertEqual(hit.citation, "ret.pdf, pp. 1-2")
        self.assertEqual(hit.metadata["content_hash"], "ret")

    def test_citation_single_page(self):
        r = self.build(["ret"])
        hit = r.search("refund")[0]
        object.__setattr__(hit, "page_end", hit.page_start)
        self.assertEqual(hit.citation, "ret.pdf, p. 1")

    def test_to_dict_is_json_safe_and_fits_agent_result(self):
        r = self.build(["pw", "ship"])
        payload = [x.to_dict() for x in r.search("password")]
        json.dumps(payload, allow_nan=False)
        try:
            from customer_support_coach.data_models import AgentResult
        except ImportError:
            self.skipTest("shared data_models not present on this branch")
        AgentResult(session_id="sess-1", agent_type="rag", result={"retrieved_context": payload})

    def test_embedding_failure_propagates(self):
        self.build(["pw"])
        with self.assertRaises(EmbeddingError):
            Retriever(FailingEmbedder(), self.store).search("password")

    def test_embedder_returning_nan_is_rejected(self):
        self.build(["pw"])
        bad = HashingTestEmbedder()
        bad.embed_query = lambda t: [float("nan")] * 64
        with self.assertRaises(EmbeddingError):
            Retriever(bad, self.store).search("password")


if __name__ == "__main__":
    unittest.main()
