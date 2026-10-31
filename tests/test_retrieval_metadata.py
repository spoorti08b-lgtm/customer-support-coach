"""Focused tests for chunk ID extraction and metadata propagation in RAG retrieval.

Covers Step 3 requirements:
  1. A returned passage contains the exact ID supplied by ChromaDB.
  2. Multiple passages retain the correct ID-to-text and ID-to-metadata mapping.
  3. Empty results are handled safely.
  4. Missing optional metadata does not break retrieval.
  5. The Knowledge Recommendation Agent preserves the returned chunk ID.
  6. Existing retrieval and contract behavior remains backward-compatible.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest

from backend.orchestrator.knowledge_schemas import (
    KnowledgeExecutionStatus,
    KnowledgeRecommendationRequest,
)
from backend.services import rag_stub
from backend.services.knowledge_agent import KnowledgeRecommendationAgent


# ---------------------------------------------------------------------------
# 1. Exact ID Extraction from ChromaDB Query
# ---------------------------------------------------------------------------

def test_retrieve_extracts_exact_chromadb_id():
    """A returned passage contains the exact chunk ID stored in ChromaDB."""
    mock_results = {
        "ids": [["hash123_p1_c0"]],
        "documents": [["Policy text for return window."]],
        "metadatas": [[{"doc_name": "returns.pdf", "source": "returns.pdf", "page": 1}]],
        "distances": [[0.15]],
    }

    mock_collection = MagicMock()
    mock_collection.count.return_value = 1
    mock_collection.query.return_value = mock_results

    with patch("backend.services.rag_stub.get_collection", return_value=mock_collection), \
         patch("backend.services.rag_stub.get_embedding_model") as mock_model_getter:
        mock_model = MagicMock()
        mock_model.encode.return_value.tolist.return_value = [[0.1] * 384]
        mock_model_getter.return_value = mock_model

        hits = rag_stub.retrieve("return policy", k=1)

        assert len(hits) == 1
        assert hits[0]["chunk_id"] == "hash123_p1_c0"
        assert hits[0]["text"] == "Policy text for return window."
        assert hits[0]["doc_name"] == "returns.pdf"
        assert hits[0]["source"] == "returns.pdf"
        assert hits[0]["page"] == 1
        assert hits[0]["score"] == 0.85


# ---------------------------------------------------------------------------
# 2. Multiple Passages Retain Correct Alignment
# ---------------------------------------------------------------------------

def test_retrieve_multiple_passages_correct_alignment():
    """Multiple passages retain exact 1-to-1 mapping across ID, text, metadata, and score."""
    mock_results = {
        "ids": [["chunk_a_p1_c0", "chunk_b_p2_c1", "chunk_c_p1_c2"]],
        "documents": [["Snippet A", "Snippet B", "Snippet C"]],
        "metadatas": [[
            {"doc_name": "doc_a.pdf", "page": 1},
            {"doc_name": "doc_b.pdf", "page": 2},
            {"doc_name": "doc_c.pdf", "page": 1},
        ]],
        "distances": [[0.10, 0.20, 0.30]],  # scores: 0.9, 0.8, 0.7
    }

    mock_collection = MagicMock()
    mock_collection.count.return_value = 3
    mock_collection.query.return_value = mock_results

    with patch("backend.services.rag_stub.get_collection", return_value=mock_collection), \
         patch("backend.services.rag_stub.get_embedding_model") as mock_model_getter:
        mock_model = MagicMock()
        mock_model.encode.return_value.tolist.return_value = [[0.1] * 384]
        mock_model_getter.return_value = mock_model

        hits = rag_stub.retrieve("query", k=3)

        assert len(hits) == 3
        # Rank 1: distance 0.10 -> score 0.90
        assert hits[0]["chunk_id"] == "chunk_a_p1_c0"
        assert hits[0]["text"] == "Snippet A"
        assert hits[0]["doc_name"] == "doc_a.pdf"
        assert hits[0]["score"] == 0.90

        # Rank 2: distance 0.20 -> score 0.80
        assert hits[1]["chunk_id"] == "chunk_b_p2_c1"
        assert hits[1]["text"] == "Snippet B"
        assert hits[1]["doc_name"] == "doc_b.pdf"
        assert hits[1]["score"] == 0.80

        # Rank 3: distance 0.30 -> score 0.70
        assert hits[2]["chunk_id"] == "chunk_c_p1_c2"
        assert hits[2]["text"] == "Snippet C"
        assert hits[2]["doc_name"] == "doc_c.pdf"
        assert hits[2]["score"] == 0.70


# ---------------------------------------------------------------------------
# 3. Empty Results Handled Safely
# ---------------------------------------------------------------------------

def test_retrieve_empty_results_safe():
    """Empty query string, zero collection count, or empty query results return []."""
    # Empty query
    assert rag_stub.retrieve("") == []
    assert rag_stub.retrieve("   ") == []

    # Zero collection count
    mock_empty_coll = MagicMock()
    mock_empty_coll.count.return_value = 0
    with patch("backend.services.rag_stub.get_collection", return_value=mock_empty_coll):
        assert rag_stub.retrieve("valid query") == []

    # Non-zero count but Chroma query returns empty lists
    mock_coll_empty_query = MagicMock()
    mock_coll_empty_query.count.return_value = 5
    mock_coll_empty_query.query.return_value = {
        "ids": [[]],
        "documents": [[]],
        "metadatas": [[]],
        "distances": [[]],
    }
    with patch("backend.services.rag_stub.get_collection", return_value=mock_coll_empty_query), \
         patch("backend.services.rag_stub.get_embedding_model") as mock_model_getter:
        mock_model = MagicMock()
        mock_model.encode.return_value.tolist.return_value = [[0.1] * 384]
        mock_model_getter.return_value = mock_model

        assert rag_stub.retrieve("valid query") == []


# ---------------------------------------------------------------------------
# 4. Missing Optional Metadata Does Not Break Retrieval
# ---------------------------------------------------------------------------

def test_retrieve_handles_missing_or_malformed_metadata():
    """Handles None or empty dict metadata entries gracefully with fallback defaults."""
    mock_results = {
        "ids": [["id_no_meta", "id_empty_meta"]],
        "documents": [["Document without metadata", "Document with empty metadata"]],
        "metadatas": [[None, {}]],
        "distances": [[0.12, 0.18]],
    }

    mock_collection = MagicMock()
    mock_collection.count.return_value = 2
    mock_collection.query.return_value = mock_results

    with patch("backend.services.rag_stub.get_collection", return_value=mock_collection), \
         patch("backend.services.rag_stub.get_embedding_model") as mock_model_getter:
        mock_model = MagicMock()
        mock_model.encode.return_value.tolist.return_value = [[0.1] * 384]
        mock_model_getter.return_value = mock_model

        hits = rag_stub.retrieve("test query", k=2)

        assert len(hits) == 2
        assert hits[0]["chunk_id"] == "id_no_meta"
        assert hits[0]["doc_name"] == "Unknown"
        assert hits[0]["page"] == 1
        assert hits[0]["score"] == 0.88

        assert hits[1]["chunk_id"] == "id_empty_meta"
        assert hits[1]["doc_name"] == "Unknown"
        assert hits[1]["page"] == 1


# ---------------------------------------------------------------------------
# 5. Knowledge Recommendation Agent Preserves chunk_id
# ---------------------------------------------------------------------------

def test_knowledge_agent_populates_retrieved_passage_chunk_id():
    """KnowledgeRecommendationAgent maps chunk_id from retrieve() to RetrievedPassage.chunk_id."""
    fake_hits = [
        {
            "chunk_id": "sha256abc_p1_c0",
            "text": "Unused items can be returned within 30 days.",
            "doc_name": "returns_and_refunds.pdf",
            "source": "returns_and_refunds.pdf",
            "page": 1,
            "score": 0.88,
        }
    ]

    agent = KnowledgeRecommendationAgent()
    with patch("backend.services.rag_stub.retrieve", return_value=fake_hits):
        req = KnowledgeRecommendationRequest(message="What is the return window?")
        response = agent.recommend(req)

        assert response.status == KnowledgeExecutionStatus.SUCCESS
        assert len(response.passages) == 1
        passage = response.passages[0]
        assert passage.chunk_id == "sha256abc_p1_c0"
        assert passage.source == "returns_and_refunds.pdf"
        assert passage.doc_name == "returns_and_refunds.pdf"
        assert passage.rank == 1
        assert passage.score == 0.88


# ---------------------------------------------------------------------------
# 6. Backward Compatibility with Existing Callers
# ---------------------------------------------------------------------------

def test_retrieve_backward_compatible_keys():
    """Hits contain all previously expected keys (text, doc_name, source, page, score)."""
    mock_results = {
        "ids": [["compat_id"]],
        "documents": [["Compatibility sample text"]],
        "metadatas": [[{"doc_name": "compat.pdf", "source": "compat.pdf", "page": 3}]],
        "distances": [[0.25]],
    }

    mock_collection = MagicMock()
    mock_collection.count.return_value = 1
    mock_collection.query.return_value = mock_results

    with patch("backend.services.rag_stub.get_collection", return_value=mock_collection), \
         patch("backend.services.rag_stub.get_embedding_model") as mock_model_getter:
        mock_model = MagicMock()
        mock_model.encode.return_value.tolist.return_value = [[0.1] * 384]
        mock_model_getter.return_value = mock_model

        hits = rag_stub.retrieve("compat query", k=1)
        hit = hits[0]

        expected_keys = {"chunk_id", "text", "doc_name", "source", "page", "score"}
        assert expected_keys.issubset(hit.keys())
        assert isinstance(hit["score"], float)
        assert isinstance(hit["page"], int)
