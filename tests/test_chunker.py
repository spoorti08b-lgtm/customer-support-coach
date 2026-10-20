"""Unit tests for chunking."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rag_test_support  # noqa: F401,E402

from customer_support_coach.rag import (  # noqa: E402
    InvalidInputError,
    LoadedDocument,
    PageText,
    TextChunker,
)

SENTENCES = " ".join(f"Sentence number {i} explains step {i} of the process." for i in range(60))


def make_doc(page_texts, name="manual.pdf"):
    pages = tuple(PageText(i + 1, t) for i, t in enumerate(page_texts))
    return LoadedDocument("doc-manual-abc", name, "h" * 64, pages)


class TestChunker(unittest.TestCase):
    def test_chunks_respect_size_and_are_never_empty(self):
        ch = TextChunker(200, 40)
        parts = ch.split_text(SENTENCES)
        self.assertGreater(len(parts), 3)
        for p in parts:
            self.assertTrue(p.strip())
            self.assertLessEqual(len(p), 200)

    def test_overlap_present_between_neighbours(self):
        ch = TextChunker(200, 50)
        spans = ch._spans(SENTENCES)
        for (s1, e1), (s2, e2) in zip(spans, spans[1:]):
            self.assertLess(s2, e1, "next chunk must start before previous one ends")
            self.assertGreater(s2, s1)

    def test_all_text_is_covered(self):
        ch = TextChunker(150, 30)
        covered = set()
        for s, e in ch._spans(SENTENCES):
            covered.update(range(s, e))
        missing = [i for i, c in enumerate(SENTENCES) if not c.isspace() and i not in covered]
        self.assertEqual(missing, [])

    def test_short_text_single_chunk_and_blank_text_none(self):
        ch = TextChunker(500, 50)
        self.assertEqual(ch.split_text("  Hello world.  "), ["Hello world."])
        self.assertEqual(ch.split_text("   \n\n "), [])

    def test_prefers_paragraph_boundary(self):
        text = ("A" * 60 + " word.\n\n") + ("B" * 60 + " word.")
        parts = TextChunker(100, 10).split_text(text)
        self.assertTrue(parts[0].endswith("A word.") or parts[0].endswith("word."))
        self.assertNotIn("B", parts[0])

    def test_unbroken_text_still_progresses(self):
        parts = TextChunker(50, 10).split_text("x" * 500)
        self.assertGreaterEqual(len(parts), 10)
        self.assertTrue(all(len(p) <= 50 for p in parts))

    def test_deterministic(self):
        doc = make_doc([SENTENCES])
        a = TextChunker(200, 40).chunk_document(doc)
        b = TextChunker(200, 40).chunk_document(doc)
        self.assertEqual([(c.chunk_id, c.text) for c in a], [(c.chunk_id, c.text) for c in b])

    def test_metadata_and_ids(self):
        doc = make_doc(["Page one text. " * 20, "Page two text. " * 20])
        chunks = TextChunker(200, 40).chunk_document(doc)
        self.assertEqual(len({c.chunk_id for c in chunks}), len(chunks))
        for i, c in enumerate(chunks):
            m = c.metadata
            self.assertEqual(m["doc_id"], "doc-manual-abc")
            self.assertEqual(m["filename"], "manual.pdf")
            self.assertEqual(m["chunk_index"], i)
            self.assertEqual(m["chunk_count"], len(chunks))
            self.assertLessEqual(m["page_start"], m["page_end"])
            self.assertTrue(c.chunk_id.startswith("doc-manual-abc:c"))
            for v in m.values():  # ChromaDB-supported scalar types only
                self.assertIsInstance(v, (str, int, float, bool))

    def test_page_ranges(self):
        doc = make_doc(["alpha " * 20, "beta " * 20])  # ~120 chars per page
        chunks = TextChunker(100, 10).chunk_document(doc)
        self.assertEqual(chunks[0].metadata["page_start"], 1)
        self.assertEqual(chunks[-1].metadata["page_end"], 2)
        self.assertTrue(any(c.metadata["page_start"] != c.metadata["page_end"] for c in chunks))

    def test_blank_pages_are_skipped_but_numbers_kept(self):
        doc = make_doc(["First page text.", "", "Third page text."])
        chunks = TextChunker(500, 50).chunk_document(doc)
        self.assertEqual(len(chunks), 1)
        self.assertEqual((chunks[0].metadata["page_start"], chunks[0].metadata["page_end"]), (1, 3))

    def test_invalid_parameters(self):
        for size, overlap in [(100, 100), (100, 150), (5, 0), (100, -1), (True, 0), ("100", 10)]:
            with self.assertRaises(InvalidInputError):
                TextChunker(size, overlap)


if __name__ == "__main__":
    unittest.main()
