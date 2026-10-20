"""Unit tests for the ChromaDB store (real ChromaDB, fake vectors)."""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rag_test_support  # noqa: F401,E402

from customer_support_coach.rag import (  # noqa: E402
    Chunk,
    ChromaVectorStore,
    EmbeddingModelMismatchError,
    InvalidInputError,
    VectorStoreError,
)


def chunk(doc, i, text="some text", **extra):
    meta = {"doc_id": doc, "filename": f"{doc}.pdf", "chunk_index": i, "chunk_count": 2,
            "page_start": 1, "page_end": 1, "content_hash": f"hash-{doc}"}
    meta.update(extra)
    return Chunk(f"{doc}:c{i}", text, meta)


class TestVectorStore(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.path = Path(self._tmp.name) / "chroma"
        self.store = ChromaVectorStore(self.path, "unit_tests", "model-a")

    def tearDown(self):
        self.store.close()
        self._tmp.cleanup()

    def test_empty_store(self):
        self.assertEqual(self.store.count(), 0)
        self.assertEqual(self.store.query([1.0, 0.0, 0.0], 3), [])
        s = self.store.stats()
        self.assertEqual((s["total_chunks"], s["total_documents"]), (0, 0))
        self.assertIsNone(self.store.get_document_info("nothing"))

    def test_upsert_is_idempotent(self):
        chunks = [chunk("a", 0), chunk("a", 1)]
        vecs = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
        self.store.upsert_chunks(chunks, vecs)
        self.store.upsert_chunks(chunks, vecs)
        self.assertEqual(self.store.count(), 2)

    def test_persistence_across_reopen(self):
        self.store.upsert_chunks([chunk("a", 0, "persist me")], [[1.0, 0.0, 0.0]])
        self.store.close()
        reopened = ChromaVectorStore(self.path, "unit_tests", "model-a")
        try:
            self.assertEqual(reopened.count(), 1)
            hit = reopened.query([1.0, 0.0, 0.0], 3)
            self.assertEqual(hit[0]["document"], "persist me")
            self.assertEqual(hit[0]["metadata"]["filename"], "a.pdf")
        finally:
            reopened.close()

    def test_query_orders_by_distance_and_clamps(self):
        self.store.upsert_chunks(
            [chunk("a", 0, "x"), chunk("b", 0, "y")], [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
        )
        rows = self.store.query([0.9, 0.1, 0.0], 10)
        self.assertEqual([r["id"] for r in rows], ["a:c0", "b:c0"])
        self.assertLess(rows[0]["distance"], rows[1]["distance"])
        self.assertEqual(len(self.store.query([0.9, 0.1, 0.0], 1)), 1)

    def test_delete_document_leaves_others(self):
        self.store.upsert_chunks(
            [chunk("a", 0), chunk("a", 1), chunk("b", 0)],
            [[1.0, 0, 0], [0.9, 0.1, 0], [0, 1.0, 0]],
        )
        self.assertEqual(self.store.delete_document("a"), 2)
        self.assertEqual(self.store.count(), 1)
        self.assertIsNone(self.store.get_document_info("a"))
        self.assertIsNotNone(self.store.get_document_info("b"))

    def test_stats_and_document_info(self):
        self.store.upsert_chunks([chunk("a", 0), chunk("a", 1), chunk("b", 0)],
                                 [[1.0, 0, 0], [0, 1.0, 0], [0, 0, 1.0]])
        s = self.store.stats()
        self.assertEqual(s["total_chunks"], 3)
        self.assertEqual(s["total_documents"], 2)
        self.assertEqual(s["embedding_model"], "model-a")
        self.assertEqual(s["distance_metric"], "cosine")
        info = self.store.get_document_info("a")
        self.assertEqual(sorted(info["chunk_ids"]), ["a:c0", "a:c1"])
        self.assertEqual(info["content_hashes"], {"hash-a"})
        self.assertEqual(self.store.find_filename_by_hash("hash-b"), "b.pdf")
        self.assertIsNone(self.store.find_filename_by_hash("hash-b", exclude_doc_id="b"))

    def test_embedding_model_mismatch(self):
        self.store.close()
        with self.assertRaises(EmbeddingModelMismatchError):
            ChromaVectorStore(self.path, "unit_tests", "model-b")
        self.store = ChromaVectorStore(self.path, "unit_tests", "model-a")  # still usable

    def test_input_validation(self):
        with self.assertRaises(InvalidInputError):
            ChromaVectorStore(self.path, "x", "m")  # name too short for Chroma
        with self.assertRaises(InvalidInputError):
            self.store.upsert_chunks([chunk("a", 0)], [])
        with self.assertRaises(InvalidInputError):
            self.store.upsert_chunks([chunk("a", 0, extra=None)], [[1.0, 0, 0]])  # None metadata
        with self.assertRaises(InvalidInputError):
            self.store.upsert_chunks([chunk("a", 0, text="   ")], [[1.0, 0, 0]])
        with self.assertRaises(InvalidInputError):
            self.store.upsert_chunks([chunk("a", 0), chunk("a", 0)], [[1.0, 0, 0]] * 2)
        with self.assertRaises(InvalidInputError):
            self.store.query([1.0, 0, 0], 0)

    def test_storage_errors_are_wrapped(self):
        with mock.patch.object(self.store._collection, "upsert", side_effect=RuntimeError("disk full")):
            with self.assertRaises(VectorStoreError):
                self.store.upsert_chunks([chunk("a", 0)], [[1.0, 0, 0]])
        with mock.patch.object(self.store._collection, "count", side_effect=RuntimeError("boom")):
            with self.assertRaises(VectorStoreError):
                self.store.count()

    def test_dimension_mismatch_is_wrapped(self):
        self.store.upsert_chunks([chunk("a", 0)], [[1.0, 0.0, 0.0]])
        with self.assertRaises(VectorStoreError):
            self.store.upsert_chunks([chunk("b", 0)], [[1.0, 0.0]])


if __name__ == "__main__":
    unittest.main()
