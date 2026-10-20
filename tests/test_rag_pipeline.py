"""End-to-end pipeline tests (real PDFs, real pypdf, real ChromaDB, test embedder)."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rag_test_support import FailingEmbedder, HashingTestEmbedder, write_pdf  # noqa: E402

from customer_support_coach.rag import (  # noqa: E402
    InvalidInputError,
    RagConfig,
    RagPipeline,
    VectorStoreError,
)

PASSWORD = ["To reset your password open Settings, choose Forgot Password and follow the email link. " * 3]
SHIPPING = ["Standard shipping takes five business days. Express shipping takes two days. " * 3,
            "Tracking numbers are emailed after dispatch and appear in your account. " * 3]
RETURNS = ["Items may be returned within thirty days for a full refund with the original receipt. " * 3]


class PipelineTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self._tmp.name)
        self.docs = self.root / "docs"
        self.docs.mkdir()
        self.embedder = HashingTestEmbedder()
        self.config = RagConfig(persist_directory=self.root / "chroma", chunk_size=200, chunk_overlap=40)
        self.rag = RagPipeline(self.config, embedder=self.embedder)

    def tearDown(self):
        self.rag.close()
        self._tmp.cleanup()

    def pdf(self, name, pages):
        return write_pdf(self.docs / name, pages)


class TestIngestion(PipelineTestCase):
    def test_ingest_single_pdf(self):
        r = self.rag.ingest_pdf(self.pdf("password.pdf", PASSWORD))
        self.assertTrue(r.ok)
        self.assertEqual(r.status, "ingested")
        self.assertGreater(r.chunks_added, 0)
        self.assertEqual(self.rag.get_collection_stats()["total_chunks"], r.chunks_added)

    def test_reingest_unchanged_is_skipped_without_embedding(self):
        f = self.pdf("password.pdf", PASSWORD)
        self.rag.ingest_pdf(f)
        calls = self.embedder.document_calls
        before = self.rag.get_collection_stats()["total_chunks"]
        again = self.rag.ingest_pdf(f)
        self.assertEqual(again.status, "skipped_unchanged")
        self.assertEqual(self.embedder.document_calls, calls)
        self.assertEqual(self.rag.get_collection_stats()["total_chunks"], before)

    def test_changed_document_replaces_only_its_own_chunks(self):
        other = self.pdf("returns.pdf", RETURNS)
        f = self.pdf("shipping.pdf", SHIPPING)
        self.rag.ingest_pdf(other)
        first = self.rag.ingest_pdf(f)
        returns_chunks = self.rag.get_collection_stats()["total_chunks"] - first.chunks_added

        write_pdf(f, ["Shipping is now free for every order over fifty dollars."])
        second = self.rag.ingest_pdf(f)
        self.assertEqual(second.status, "updated")
        self.assertGreater(second.chunks_removed, 0)

        stats = self.rag.get_collection_stats()
        by_name = {d["filename"]: d["chunk_count"] for d in stats["documents"]}
        self.assertEqual(by_name["returns.pdf"], returns_chunks)  # untouched
        self.assertEqual(by_name["shipping.pdf"], second.chunks_added)
        texts = " ".join(h.text for h in self.rag.search("shipping", top_k=10))
        self.assertNotIn("five business days", texts)
        self.assertIn("free for every order", texts)

    def test_identical_content_under_new_name_is_duplicate(self):
        self.rag.ingest_pdf(self.pdf("a.pdf", PASSWORD))
        r = self.rag.ingest_pdf(self.pdf("copy_of_a.pdf", PASSWORD))
        self.assertEqual(r.status, "skipped_duplicate")
        self.assertEqual(len(self.rag.get_collection_stats()["documents"]), 1)

    def test_failures_are_reported_not_raised(self):
        (self.docs / "bad.pdf").write_bytes(b"garbage")
        scan = self.pdf("scan.pdf", ["", ""])
        missing = self.rag.ingest_pdf(self.docs / "ghost.pdf")
        corrupt = self.rag.ingest_pdf(self.docs / "bad.pdf")
        scanned = self.rag.ingest_pdf(scan)
        self.assertEqual(missing.error_type, "DocumentNotFoundError")
        self.assertEqual(corrupt.error_type, "UnreadableDocumentError")
        self.assertEqual(scanned.error_type, "NoExtractableTextError")
        self.assertIn("OCR", scanned.message)
        self.assertTrue(all(not r.ok for r in (missing, corrupt, scanned)))
        self.assertEqual(self.rag.get_collection_stats()["total_chunks"], 0)

    def test_partial_scan_reports_blank_pages(self):
        r = self.rag.ingest_pdf(self.pdf("mixed.pdf", ["Real text on page one.", "", "Real text on page three."]))
        self.assertTrue(r.ok)
        self.assertEqual(r.pages_without_text, [2])

    def test_invalid_path_argument(self):
        for bad in [None, "", 5]:
            with self.assertRaises(InvalidInputError):
                self.rag.ingest_pdf(bad)

    def test_directory_ingestion_report(self):
        self.pdf("password.pdf", PASSWORD)
        self.pdf("returns.pdf", RETURNS)
        (self.docs / "bad.pdf").write_bytes(b"garbage")
        report = self.rag.ingest_directory(self.docs)
        self.assertEqual(len(report.succeeded), 2)
        self.assertEqual(len(report.failed), 1)
        self.assertFalse(report.all_ok)
        self.assertIn("bad.pdf", report.summary())
        json.dumps(report.to_dict())
        again = self.rag.ingest_directory(self.docs)
        self.assertEqual(len(again.skipped), 2)

    def test_empty_directory_and_missing_directory(self):
        self.assertEqual(self.rag.ingest_directory(self.docs).results, [])
        from customer_support_coach.rag import DocumentNotFoundError
        with self.assertRaises(DocumentNotFoundError):
            self.rag.ingest_directory(self.root / "nope")

    def test_filename_collision_in_recursive_scan(self):
        self.pdf("manual.pdf", PASSWORD)
        (self.docs / "sub").mkdir()
        write_pdf(self.docs / "sub" / "manual.pdf", RETURNS)
        report = self.rag.ingest_directory(self.docs, recursive=True)
        self.assertEqual(len(report.succeeded), 1)
        self.assertEqual(report.failed[0].error_type, "FilenameCollision")


class TestFailureSafety(PipelineTestCase):
    def test_embedding_failure_leaves_existing_data_intact(self):
        f = self.pdf("shipping.pdf", SHIPPING)
        self.rag.ingest_pdf(f)
        before = self.rag.get_collection_stats()
        write_pdf(f, ["Completely new shipping text that needs new vectors."])
        broken = RagPipeline(self.config, embedder=FailingEmbedder(), store=self.rag.store)
        r = broken.ingest_pdf(f)
        self.assertEqual(r.status, "failed")
        self.assertEqual(r.error_type, "EmbeddingError")
        self.assertEqual(self.rag.get_collection_stats()["total_chunks"], before["total_chunks"])

    def test_storage_failure_is_reported(self):
        f = self.pdf("password.pdf", PASSWORD)
        with mock.patch.object(self.rag.store, "upsert_chunks", side_effect=VectorStoreError("disk full")):
            r = self.rag.ingest_pdf(f)
        self.assertEqual((r.status, r.error_type), ("failed", "VectorStoreError"))
        self.assertTrue(self.rag.ingest_pdf(f).ok)  # recovers on retry


class TestSearchAndPersistence(PipelineTestCase):
    def test_end_to_end_top3_with_citations(self):
        for name, pages in [("password.pdf", PASSWORD), ("shipping.pdf", SHIPPING), ("returns.pdf", RETURNS)]:
            self.pdf(name, pages)
        self.rag.ingest_directory(self.docs)
        hits = self.rag.search("reset password forgot password email link")
        self.assertEqual(len(hits), 3)
        self.assertEqual(hits[0].source_filename, "password.pdf")
        self.assertEqual(hits[0].page_start, 1)
        ctx = self.rag.retrieve_context("refund within thirty days")
        self.assertEqual(ctx[0]["source_filename"], "returns.pdf")
        json.dumps(ctx, allow_nan=False)

    def test_search_on_empty_collection(self):
        self.assertEqual(self.rag.search("hello"), [])
        self.assertEqual(self.rag.get_collection_stats()["total_chunks"], 0)

    def test_persists_across_pipeline_instances(self):
        f = self.pdf("password.pdf", PASSWORD)
        self.rag.ingest_pdf(f)
        self.rag.close()
        second = RagPipeline(self.config, embedder=HashingTestEmbedder())
        try:
            self.assertGreater(second.get_collection_stats()["total_chunks"], 0)
            self.assertEqual(second.ingest_pdf(f).status, "skipped_unchanged")
            self.assertEqual(second.search("password")[0].source_filename, "password.pdf")
        finally:
            second.close()
            self.rag = RagPipeline(self.config, embedder=HashingTestEmbedder())  # for tearDown


class TestConfig(unittest.TestCase):
    def test_from_env(self):
        cfg = RagConfig.from_env({"RAG_CHUNK_SIZE": "500", "RAG_CHUNK_OVERLAP": "50", "RAG_TOP_K": "4",
                                  "RAG_PERSIST_DIR": "somewhere"})
        self.assertEqual((cfg.chunk_size, cfg.chunk_overlap, cfg.default_top_k), (500, 50, 4))
        self.assertEqual(cfg.persist_directory, Path("somewhere"))

    def test_defaults_and_validation(self):
        cfg = RagConfig()
        self.assertEqual((cfg.chunk_size, cfg.chunk_overlap, cfg.default_top_k), (600, 100, 3))
        with self.assertRaises(InvalidInputError):
            RagConfig(chunk_size=100, chunk_overlap=100)
        with self.assertRaises(InvalidInputError):
            RagConfig.from_env({"RAG_TOP_K": "three"})
        with self.assertRaises(InvalidInputError):
            RagConfig(default_top_k=0)


if __name__ == "__main__":
    unittest.main()
