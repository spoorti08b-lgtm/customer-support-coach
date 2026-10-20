"""Boundary-aware text chunking with page tracking."""

import bisect
import re

from .models import Chunk, InvalidInputError, LoadedDocument

PAGE_SEPARATOR = "\n\n"
_SENTENCE_END = re.compile(r"[.!?][\"')\]]?\s")


def validate_chunk_params(chunk_size: int, chunk_overlap: int) -> None:
    """Raise :class:`InvalidInputError` for unusable chunk settings."""
    for name, value in (("chunk_size", chunk_size), ("chunk_overlap", chunk_overlap)):
        if isinstance(value, bool) or not isinstance(value, int):
            raise InvalidInputError(f"{name} must be an integer.")
    if chunk_size < 10:
        raise InvalidInputError("chunk_size must be at least 10 characters.")
    if chunk_overlap < 0:
        raise InvalidInputError("chunk_overlap cannot be negative.")
    if chunk_overlap >= chunk_size:
        raise InvalidInputError("chunk_overlap must be smaller than chunk_size.")


class TextChunker:
    """Splits documents into overlapping character windows.

    Windows end at the best natural boundary found in the second half of the
    window (paragraph > line > sentence > word) so answers are not cut
    mid-sentence. Sizes are measured in characters.
    """

    def __init__(self, chunk_size: int = 600, chunk_overlap: int = 100):
        validate_chunk_params(chunk_size, chunk_overlap)
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    # -------------------------------------------------------------- plain text
    def split_text(self, text: str) -> list[str]:
        """Split plain text into non-empty chunks."""
        return [text[s:e] for s, e in self._spans(text)]

    # --------------------------------------------------------------- documents
    def chunk_document(self, doc: LoadedDocument) -> list[Chunk]:
        """Chunk a loaded PDF, keeping page range and source metadata."""
        full = ""
        starts: list[int] = []
        page_numbers: list[int] = []
        for page in doc.pages:
            if not page.text:
                continue
            if full:
                full += PAGE_SEPARATOR
            starts.append(len(full))
            page_numbers.append(page.page_number)
            full += page.text

        spans = self._spans(full)
        total = len(spans)
        chunks: list[Chunk] = []
        for index, (start, end) in enumerate(spans):
            first = page_numbers[bisect.bisect_right(starts, start) - 1]
            last = page_numbers[bisect.bisect_right(starts, end - 1) - 1]
            chunks.append(
                Chunk(
                    chunk_id=f"{doc.doc_id}:c{index:05d}",
                    text=full[start:end],
                    metadata={
                        "doc_id": doc.doc_id,
                        "filename": doc.filename,
                        "page_start": first,
                        "page_end": last,
                        "chunk_index": index,
                        "chunk_count": total,
                        "char_start": start,
                        "char_end": end,
                        "content_hash": doc.content_hash,
                    },
                )
            )
        return chunks

    # ---------------------------------------------------------------- internals
    def _spans(self, text: str) -> list[tuple[int, int]]:
        n = len(text)
        spans: list[tuple[int, int]] = []
        start = 0
        while start < n:
            while start < n and text[start].isspace():
                start += 1
            if start >= n:
                break
            hard_end = min(start + self.chunk_size, n)
            end = hard_end if hard_end == n else self._find_break(text, start, hard_end)

            s, e = start, end
            while e > s and text[e - 1].isspace():
                e -= 1
            if e > s:
                spans.append((s, e))
            if end >= n:
                break

            nxt = end - self.chunk_overlap
            if nxt <= start:
                nxt = end  # overlap too large for this window: still make progress
            else:
                # begin the next chunk at a word start, never mid-word
                while nxt < end and not text[nxt - 1].isspace():
                    nxt += 1
            start = nxt
        return spans

    def _find_break(self, text: str, start: int, hard_end: int) -> int:
        low = start + max(self.chunk_size // 2, 1)
        idx = text.rfind("\n\n", low, hard_end)
        if idx != -1:
            return idx + 2
        idx = text.rfind("\n", low, hard_end)
        if idx != -1:
            return idx + 1
        last = None
        for last in _SENTENCE_END.finditer(text, low, hard_end):
            pass
        if last is not None:
            return last.end()
        idx = text.rfind(" ", low, hard_end)
        if idx != -1:
            return idx + 1
        return hard_end
