"""PDF discovery and page-by-page text extraction (pypdf)."""

import hashlib
import io
import re
from pathlib import Path
from typing import Iterable

from pypdf import PasswordType, PdfReader

from .models import (
    DocumentNotFoundError,
    EmptyDocumentError,
    InvalidInputError,
    LoadedDocument,
    NoExtractableTextError,
    PageText,
    RagError,
    UnreadableDocumentError,
)

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0e-\x1f\x7f]")
_INLINE_SPACE = re.compile(r"[ \t]+")
_BLANK_RUNS = re.compile(r"\n{3,}")


def clean_text(text: str) -> str:
    """Normalise whitespace without touching words, digits or punctuation.

    * strips NUL/control characters, converts form feeds and NBSP,
    * unifies line endings,
    * collapses runs of spaces/tabs and trims every line,
    * keeps single line breaks and paragraph breaks (3+ newlines -> 2).

    Hyphenated line-wraps are deliberately NOT re-joined: that would also
    damage legitimate hyphens such as "step-by-step".
    """
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\f", "\n").replace("\u00a0", " ")
    text = _CONTROL_CHARS.sub("", text)
    text = _INLINE_SPACE.sub(" ", text)
    text = "\n".join(line.strip() for line in text.split("\n"))
    text = _BLANK_RUNS.sub("\n\n", text)
    return text.strip()


def make_doc_id(filename: str) -> str:
    """Stable document id derived from the file name (case-insensitive).

    The id only depends on the *name*, so a changed file keeps its id and
    re-ingestion can replace its old chunks. Characters are limited to
    ``[a-z0-9-]`` so the id also satisfies the team's ``validate_id``.
    """
    slug = re.sub(r"[^a-z0-9]+", "-", Path(filename).stem.lower()).strip("-")[:40] or "doc"
    digest = hashlib.sha256(filename.casefold().encode("utf-8")).hexdigest()[:10]
    return f"doc-{slug}-{digest}"


class PdfDocumentLoader:
    """Finds PDFs and extracts cleaned text per page."""

    def __init__(self, extensions: Iterable[str] = (".pdf",)):
        self.extensions = tuple(e.lower() for e in extensions)

    # ------------------------------------------------------------ discovery
    def find_pdfs(self, directory: str | Path, recursive: bool = False) -> list[Path]:
        """Return supported files in ``directory`` sorted by name."""
        folder = _as_path(directory, "directory")
        if not folder.is_dir():
            raise DocumentNotFoundError(folder, "Directory does not exist")
        iterator = folder.rglob("*") if recursive else folder.iterdir()
        found = [
            p for p in iterator if p.is_file() and p.suffix.lower() in self.extensions
        ]
        return sorted(found, key=lambda p: str(p).casefold())

    # ----------------------------------------------------------- extraction
    def load(self, path: str | Path) -> LoadedDocument:
        """Extract text from one PDF.

        Raises a :class:`DocumentLoadError` subclass for missing, corrupted,
        encrypted, empty or image-only (scanned) files.
        """
        file_path = _as_path(path, "path")
        if not file_path.is_file():
            raise DocumentNotFoundError(file_path, "File does not exist")
        if file_path.suffix.lower() not in self.extensions:
            raise UnreadableDocumentError(file_path, "Unsupported file type (expected .pdf)")

        try:
            data = file_path.read_bytes()
        except OSError as exc:
            raise UnreadableDocumentError(file_path, f"Cannot read file ({exc})") from exc
        if not data:
            raise EmptyDocumentError(file_path, "File is empty (0 bytes)")

        content_hash = hashlib.sha256(data).hexdigest()

        try:
            reader = PdfReader(io.BytesIO(data), strict=False)
            if reader.is_encrypted and reader.decrypt("") == PasswordType.NOT_DECRYPTED:
                raise UnreadableDocumentError(file_path, "PDF is password-protected")
            page_total = len(reader.pages)
        except RagError:
            raise
        except Exception as exc:  # pypdf raises many unrelated types on bad input
            raise UnreadableDocumentError(
                file_path, f"Corrupted or unsupported PDF ({type(exc).__name__}: {exc})"
            ) from exc

        if page_total == 0:
            raise EmptyDocumentError(file_path, "PDF contains no pages")

        pages: list[PageText] = []
        failed: list[int] = []
        for index in range(page_total):
            number = index + 1
            try:
                raw = reader.pages[index].extract_text() or ""
            except Exception:  # one bad page must not abort the whole file
                raw = ""
                failed.append(number)
            pages.append(PageText(number, clean_text(raw)))

        if not any(p.text for p in pages):
            if len(failed) == page_total:
                raise UnreadableDocumentError(
                    file_path, "Text extraction failed on every page"
                )
            raise NoExtractableTextError(
                file_path,
                "No extractable text (likely a scanned/image-only PDF; OCR is not supported)",
            )

        return LoadedDocument(
            doc_id=make_doc_id(file_path.name),
            filename=file_path.name,
            content_hash=content_hash,
            pages=tuple(pages),
            failed_pages=tuple(failed),
        )


def _as_path(value: str | Path, name: str) -> Path:
    if isinstance(value, Path):
        return value
    if isinstance(value, str) and value.strip():
        return Path(value)
    raise InvalidInputError(f"{name} must be a non-empty string or Path.")
