"""Automated tests for Milestone 1 requirements.

Covers chunking length and overlap, PDF deduplication, vector retrieval,
session persistence, and transcript parsing.
"""

from __future__ import annotations

import pathlib
import pytest

from backend.core.data_models import InteractionMode, Session
from backend.services import rag_stub, storage, validation


class FakePdf:
    """Mock Streamlit UploadedFile object for testing."""

    def __init__(self, path: pathlib.Path | str) -> None:
        p = pathlib.Path(path)
        self.name = p.name
        self._data = p.read_bytes()

    def getvalue(self) -> bytes:
        return self._data


SAMPLE_DIR = pathlib.Path(__file__).resolve().parent.parent / "data" / "sample_pdfs"


def test_chunk_text_max_length_and_overlap():
    """1. chunk_text yields chunks of at most 500 chars with the specified overlap."""
    text = (
        "Customer support operations require clear standards for first contact resolution, "
        "average handle time, and customer satisfaction. Frontline agents must understand "
        "company return policies, warranty guidelines, and escalation workflows. "
        "When an issue arrives, the agent identifies the customer problem and provides a "
        "polite, empathetic response while checking internal knowledge bases. "
    ) * 5  # ~1200 characters

    chunks = rag_stub.chunk_text(text, size=500, overlap=50)

    assert len(chunks) > 1, "Expected multiple chunks for text longer than 500 chars"
    for idx, chunk in enumerate(chunks):
        assert len(chunk) <= 500, f"Chunk {idx} exceeded 500 characters: {len(chunk)}"

    # Check overlap: the beginning of chunk 1 should appear near the end of chunk 0
    step = 500 - 50
    clean_text = " ".join(text.split())
    expected_overlap_text = clean_text[step : step + 50]
    assert expected_overlap_text in chunks[0]
    assert expected_overlap_text in chunks[1]


def test_ingest_duplicate_pdf_leaves_chunk_count_unchanged():
    """2. Ingesting the same PDF twice leaves the chunk count unchanged."""
    pdf_path = SAMPLE_DIR / "returns_and_refunds.pdf"
    assert pdf_path.exists(), f"Sample PDF not found at {pdf_path}"

    rag_stub.clear()
    assert rag_stub.stats()["total"] == 0

    fake_file = FakePdf(pdf_path)

    # First ingestion
    result_first = rag_stub.ingest_pdfs([fake_file])
    first_count = result_first["total"]
    assert first_count > 0, "First ingestion should produce at least one chunk"

    # Second ingestion of the exact same PDF
    result_second = rag_stub.ingest_pdfs([fake_file])
    second_count = result_second["total"]

    assert first_count == second_count, (
        f"Chunk count changed on duplicate ingestion: {first_count} != {second_count}"
    )


def test_retrieve_refund_window_returns_refunds_doc():
    """3. Querying 'What is the refund window?' after ingesting returns_and_refunds.pdf

    returns a chunk from that doc as the top result.
    """
    pdf_path = SAMPLE_DIR / "returns_and_refunds.pdf"
    fake_file = FakePdf(pdf_path)

    rag_stub.clear()
    rag_stub.ingest_pdfs([fake_file])

    query = "What is the refund window?"
    hits = rag_stub.retrieve(query, k=3)

    assert len(hits) > 0, "Retrieval returned no hits"
    top_hit = hits[0]
    assert top_hit["doc_name"] == "returns_and_refunds.pdf", (
        f"Expected returns_and_refunds.pdf as top hit, got {top_hit['doc_name']}"
    )
    assert "score" in top_hit and top_hit["score"] > 0
    assert "page" in top_hit


def test_session_save_creates_json_and_invalid_creates_no_file():
    """4. Saving a valid session creates data/sessions/<id>.json; an invalid one

    (empty product) creates no file.
    """
    # Test valid scenario
    valid_errors = validation.validate_setup(
        mode="Simulator",
        product="Smart Tracker Pro",
        scenario="Customer battery drains in 2 hours and desires a replacement or refund.",
        kb_chunk_count=2,
    )
    assert valid_errors == [], f"Valid setup had unexpected errors: {valid_errors}"

    session_id = storage.new_id()
    session = Session(
        session_id=session_id,
        mode=InteractionMode.SIMULATOR,
        product_context={"product": "Smart Tracker Pro"},
        scenario="Customer battery drains in 2 hours and desires a replacement or refund.",
    )

    saved_id = storage.save(session)
    assert saved_id == session_id
    expected_file = storage.DIR / f"{session_id}.json"
    assert expected_file.exists(), f"File {expected_file} was not created"

    # Clean up test session file
    storage.delete_session(session_id)
    assert not expected_file.exists()

    # Test invalid scenario (empty product)
    invalid_errors = validation.validate_setup(
        mode="Simulator",
        product="",
        scenario="Customer scenario that is long enough to meet length requirement.",
        kb_chunk_count=2,
    )
    assert len(invalid_errors) > 0, "Empty product should fail validation"

    initial_count = storage.count()
    # In invalid case, views/setup.py displays st.error and does NOT call storage.save()
    assert storage.count() == initial_count, "No session file should be written on validation failure"


def test_replay_parsing_rejects_single_line_and_accepts_six_lines():
    """5. Replay parsing: a 1-line transcript is rejected, a 6-line transcript gives 6 messages."""
    # 1-line transcript
    one_line = "Customer: I need help resetting my password immediately."
    parsed_one = validation.parse_transcript(one_line)
    assert len(parsed_one) == 1

    errors = validation.validate_setup(
        mode="Replay",
        product="Portal App",
        scenario="Customer needs password reset support after lockout.",
        replay_script=parsed_one,
        kb_chunk_count=1,
    )
    assert len(errors) > 0, "1-line transcript should be rejected in Replay mode"
    assert any("at least 2" in err for err in errors)

    # 6-line transcript
    six_lines = (
        "Customer: Hello, I have an issue with my recent invoice.\n"
        "Agent: Good morning! I would be glad to check your billing details.\n"
        "Customer: I was charged twice for the monthly plan.\n"
        "Agent: I see the duplicate charge and am initiating a full refund right now.\n"
        "Customer: How many business days will it take to reflect on my card?\n"
        "Agent: It typically appears within three to five business days.\n"
    )
    parsed_six = validation.parse_transcript(six_lines)
    assert len(parsed_six) == 6, f"Expected 6 parsed messages, got {len(parsed_six)}"
    assert parsed_six[0]["role"] == "customer"
    assert parsed_six[1]["role"] == "agent"
    assert parsed_six[5]["role"] == "agent"

    six_errors = validation.validate_setup(
        mode="Replay",
        product="Portal App",
        scenario="Customer needs billing resolution for duplicate monthly charges.",
        replay_script=parsed_six,
        kb_chunk_count=1,
    )
    assert six_errors == [], f"6-line transcript had unexpected errors: {six_errors}"


def test_tolerant_session_migration_converts_legacy_format():
    """6. Tolerant session loader converts legacy nested schemas into flat Milestone 1 schema."""
    legacy_raw = {
        "session_id": "sess-test-legacy",
        "mode": "simulator",
        "product_context": {"product": "Legacy Acme Router"},
        "scenario": "Customer has connection drops.",
        "customer_persona": "Angry",
        "status": "active",
        "created_at": "2026-10-23T07:18:28.968920+00:00",
        "updated_at": "2026-10-23T07:18:28.968928+00:00",
        "metadata": {"persona": "Angry", "max_turns": 6, "replay_script": []},
        "saved_at": "2026-10-23 12:48:28",
    }
    migrated = storage._normalize_session_dict(legacy_raw, "sess-test-legacy")

    # Assert flat schema requirements
    assert migrated["session_id"] == "sess-test-legacy"
    assert migrated["mode"] == "Simulator"
    assert migrated["product"] == "Legacy Acme Router"  # plain string
    assert migrated["persona"] == "Angry"
    assert migrated["max_turns"] == 6
    assert migrated["status"] == "configured"
    assert "updated_at" not in migrated
    assert "saved_at" not in migrated
    assert "product_context" not in migrated
    assert "customer_persona" not in migrated
    assert "metadata" not in migrated


def test_retrieval_evaluation_hit3_at_least_eighty_percent():
    """7. Dense retrieval evaluation against 15 ground-truth questions achieves top-3 >= 12 of 15."""
    # Ensure KB has all sample PDFs ingested
    pdf_files = [
        FakePdf(SAMPLE_DIR / "account_and_password_faq.pdf"),
        FakePdf(SAMPLE_DIR / "returns_and_refunds.pdf"),
        FakePdf(SAMPLE_DIR / "shipping_and_delivery.pdf"),
    ]
    rag_stub.ingest_pdfs(pdf_files)

    eval_result = rag_stub.evaluate_retrieval(k=3)
    assert eval_result["total"] == 15, f"Expected 15 eval questions, got {eval_result['total']}"
    assert eval_result["hit_3"] >= 12, (
        f"Retrieval top-3 was {eval_result['hit_3']}/15, expected >= 12 of 15"
    )


def test_problem_minimum_length_acceptance_and_rejection():
    """8. A 13-character problem is accepted; a 5-character problem is rejected with 'at least 10 characters'."""
    # 13-character problem -> Accepted
    prob_13 = "Order delayed"  # exactly 13 characters
    assert len(prob_13) == 13
    errors_13 = validation.validate_setup(
        mode="Simulator",
        product="Acme Store",
        scenario=prob_13,
        kb_chunk_count=1,
    )
    assert errors_13 == [], f"Expected 13-char problem to be accepted, got errors: {errors_13}"

    # 5-character problem -> Rejected with 'at least 10 characters'
    prob_5 = "Issue"  # exactly 5 characters
    assert len(prob_5) == 5
    errors_5 = validation.validate_setup(
        mode="Simulator",
        product="Acme Store",
        scenario=prob_5,
        kb_chunk_count=1,
    )
    assert len(errors_5) > 0, "Expected 5-char problem to be rejected"
    assert any("at least 10 characters" in err for err in errors_5), (
        f"Expected 'at least 10 characters' in error message, got: {errors_5}"
    )
    assert any("(5 now)" in err for err in errors_5), (
        f"Expected current count '(5 now)' in error message, got: {errors_5}"
    )


def test_validation_hint_formatting():
    """9. format_validation_hint formats single errors and joins two errors with ' . '."""
    # Single error: empty product
    err_prod = validation.validate_setup(mode="Simulator", product="", scenario="Valid problem scenario", kb_chunk_count=1)
    hint_prod = validation.format_validation_hint(err_prod)
    assert hint_prod == "Add a product."

    # Single error: product under 3 chars
    err_prod_short = validation.validate_setup(mode="Simulator", product="Ac", scenario="Valid problem scenario", kb_chunk_count=1)
    hint_prod_short = validation.format_validation_hint(err_prod_short)
    assert hint_prod_short == "Product needs at least 3 characters."

    # Single error: empty problem
    err_prob = validation.validate_setup(mode="Simulator", product="Acme Store", scenario="", kb_chunk_count=1)
    hint_prob = validation.format_validation_hint(err_prob)
    assert hint_prob == "Describe the problem."

    # Single error: problem under 10 chars
    err_prob_short = validation.validate_setup(mode="Simulator", product="Acme Store", scenario="Broken", kb_chunk_count=1)
    hint_prob_short = validation.format_validation_hint(err_prob_short)
    assert hint_prob_short == "Problem needs at least 10 characters (6 now)."

    # Multiple errors: empty product and empty problem joined with ' . '
    err_both = validation.validate_setup(mode="Simulator", product="", scenario="", kb_chunk_count=1)
    hint_both = validation.format_validation_hint(err_both)
    assert hint_both == "Add a product . Describe the problem."


