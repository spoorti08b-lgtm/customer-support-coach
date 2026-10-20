"""Unit tests for PDF discovery and extraction."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rag_test_support import build_pdf, write_pdf  # noqa: E402

from customer_support_coach.rag import (  # noqa: E402
    DocumentNotFoundError,
    EmptyDocumentError,
    InvalidInputError,
    NoExtractableTextError,
    PdfDocumentLoader,
    UnreadableDocumentError,
    clean_text,
    make_doc_id,
)


class TestLoader(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.dir = Path(self._tmp.name)
        self.loader = PdfDocumentLoader()

    def tearDown(self):
        self._tmp.cleanup()

    def test_extracts_pages_with_numbers_and_filename(self):
        f = write_pdf(self.dir / "guide.pdf", ["Reset your password here.", "Contact support (24/7)."])
        doc = self.loader.load(f)
        self.assertEqual(doc.filename, "guide.pdf")
        self.assertEqual([p.page_number for p in doc.pages], [1, 2])
        self.assertIn("Reset your password", doc.pages[0].text)
        self.assertIn("(24/7)", doc.pages[1].text)
        self.assertEqual(len(doc.content_hash), 64)

    def test_missing_file(self):
        with self.assertRaises(DocumentNotFoundError):
            self.loader.load(self.dir / "nope.pdf")

    def test_corrupted_file(self):
        f = self.dir / "bad.pdf"
        f.write_bytes(b"this is definitely not a pdf")
        with self.assertRaises(UnreadableDocumentError):
            self.loader.load(f)

    def test_wrong_extension(self):
        f = self.dir / "notes.txt"
        f.write_text("hello")
        with self.assertRaises(UnreadableDocumentError):
            self.loader.load(f)

    def test_zero_byte_file(self):
        f = self.dir / "empty.pdf"
        f.write_bytes(b"")
        with self.assertRaises(EmptyDocumentError):
            self.loader.load(f)

    def test_pdf_with_no_pages(self):
        f = self.dir / "nopages.pdf"
        f.write_bytes(build_pdf([]))
        with self.assertRaises(EmptyDocumentError):
            self.loader.load(f)

    def test_scanned_pdf_is_not_silently_accepted(self):
        f = write_pdf(self.dir / "scan.pdf", ["", ""])
        with self.assertRaises(NoExtractableTextError):
            self.loader.load(f)

    def test_partially_scanned_pdf_reports_blank_pages(self):
        f = write_pdf(self.dir / "mixed.pdf", ["Some real text", "", "More text"])
        doc = self.loader.load(f)
        self.assertEqual(doc.pages_without_text, [2])

    def test_find_pdfs_sorted_case_insensitive_and_recursive(self):
        write_pdf(self.dir / "b.pdf", ["b"])
        write_pdf(self.dir / "A.PDF", ["a"])
        (self.dir / "x.txt").write_text("x")
        (self.dir / "sub").mkdir()
        write_pdf(self.dir / "sub" / "c.pdf", ["c"])
        flat = [p.name for p in self.loader.find_pdfs(self.dir)]
        deep = [p.name for p in self.loader.find_pdfs(self.dir, recursive=True)]
        self.assertEqual(flat, ["A.PDF", "b.pdf"])
        self.assertEqual(deep, ["A.PDF", "b.pdf", "c.pdf"])

    def test_find_pdfs_missing_directory(self):
        with self.assertRaises(DocumentNotFoundError):
            self.loader.find_pdfs(self.dir / "missing")

    def test_invalid_path_type(self):
        with self.assertRaises(InvalidInputError):
            self.loader.load("   ")
        with self.assertRaises(InvalidInputError):
            self.loader.load(None)

    def test_hash_and_id_stability(self):
        a = write_pdf(self.dir / "a.pdf", ["same"])
        d1, d2 = self.loader.load(a), self.loader.load(a)
        self.assertEqual(d1.content_hash, d2.content_hash)
        self.assertEqual(d1.doc_id, d2.doc_id)
        write_pdf(a, ["different"])
        self.assertNotEqual(self.loader.load(a).content_hash, d1.content_hash)
        self.assertEqual(self.loader.load(a).doc_id, d1.doc_id)  # id follows the name

    def test_doc_id_is_case_insensitive_and_valid(self):
        self.assertEqual(make_doc_id("Manual.PDF"), make_doc_id("manual.pdf"))
        self.assertRegex(make_doc_id("My Manual (v2).pdf"), r"^[A-Za-z0-9_.:-]{1,128}$")


class TestCleanText(unittest.TestCase):
    def test_whitespace_normalised_content_preserved(self):
        raw = "Step 1:\t  Open   Settings \r\n\r\n\r\n\r\nStep-by-step\u00a0guide\x00 costs $5.99 (approx.)"
        out = clean_text(raw)
        self.assertEqual(out, "Step 1: Open Settings\n\nStep-by-step guide costs $5.99 (approx.)")

    def test_empty(self):
        self.assertEqual(clean_text(""), "")
        self.assertEqual(clean_text("  \n\t "), "")


if __name__ == "__main__":
    unittest.main()
