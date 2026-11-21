"""Unit tests for knowledge retrieval evaluation metrics.

Tests pure metric calculations against hand-checkable synthetic rankings and
verifies edge cases:
  - Empty retrieved rankings
  - Disjoint/non-relevant rankings
  - Partial rankings (< 3 results)
  - Duplicate retrieved identifiers
  - Multi-relevant expectations
  - Unanswerable queries & No-Match classification
  - Distinguishing ERROR from NO_MATCH
  - Latency statistics edge cases
"""

from __future__ import annotations

import math
import pytest

from backend.evaluation.eval_metrics import (
    compute_latency_statistics,
    compute_ndcg_at_k,
    compute_no_match_metrics,
    compute_precision_at_k,
    compute_recall_at_k,
    compute_reciprocal_rank,
    compute_source_attribution_accuracy,
)


# ---------------------------------------------------------------------------
# 1. Recall@K Tests
# ---------------------------------------------------------------------------

def test_recall_at_k_perfect():
    """Single relevant document retrieved at rank 1 gives Recall@3 = 1.0."""
    retrieved = ["doc_A", "doc_B", "doc_C"]
    relevant = {"doc_A"}
    assert compute_recall_at_k(retrieved, relevant, k=3) == 1.0


def test_recall_at_k_multi_relevant_partial_and_full():
    """Two relevant documents: 1 in top-3 gives 0.5; both in top-3 gives 1.0."""
    retrieved = ["doc_A", "doc_B", "doc_C"]
    relevant = {"doc_A", "doc_D"}
    # doc_A is in retrieved[:3], doc_D is not -> 1/2 = 0.5
    assert compute_recall_at_k(retrieved, relevant, k=3) == 0.5

    # Both in retrieved[:3] -> 2/2 = 1.0
    assert compute_recall_at_k(["doc_A", "doc_D", "doc_B"], relevant, k=3) == 1.0


def test_recall_at_k_zero_hits():
    """Zero relevant documents in retrieved ranking yields 0.0."""
    retrieved = ["doc_X", "doc_Y", "doc_Z"]
    relevant = {"doc_A"}
    assert compute_recall_at_k(retrieved, relevant, k=3) == 0.0


def test_recall_at_k_empty_inputs():
    """Empty retrieved list or empty relevant set returns 0.0 safely."""
    assert compute_recall_at_k([], {"doc_A"}, k=3) == 0.0
    assert compute_recall_at_k(["doc_A"], set(), k=3) == 0.0
    assert compute_recall_at_k([], set(), k=3) == 0.0


def test_recall_at_k_fewer_than_k_results():
    """When fewer than k items are returned, recall correctly evaluates on available items."""
    retrieved = ["doc_A"]  # only 1 item returned
    relevant = {"doc_A"}
    assert compute_recall_at_k(retrieved, relevant, k=3) == 1.0


def test_recall_at_k_duplicate_retrieved_items():
    """Duplicate items in retrieved list do not inflate hit count."""
    retrieved = ["doc_A", "doc_A", "doc_A"]
    relevant = {"doc_A", "doc_B"}
    # doc_A appears once uniquely in top 3 -> 1/2 = 0.5
    assert compute_recall_at_k(retrieved, relevant, k=3) == 0.5


# ---------------------------------------------------------------------------
# 2. Precision@K Tests
# ---------------------------------------------------------------------------

def test_precision_at_k_hand_calculated():
    """Verifies Precision@3 divides strictly by k=3 per standard IR convention."""
    relevant = {"doc_A"}
    # 1 relevant in top 3 -> 1/3 = 0.3333
    assert compute_precision_at_k(["doc_A", "doc_B", "doc_C"], relevant, k=3) == 0.3333
    # 2 relevant in top 3 -> 2/3 = 0.6667
    assert compute_precision_at_k(["doc_A", "doc_B", "doc_C"], {"doc_A", "doc_B"}, k=3) == 0.6667
    # 3 relevant in top 3 -> 3/3 = 1.0
    assert compute_precision_at_k(["doc_A", "doc_B", "doc_C"], {"doc_A", "doc_B", "doc_C"}, k=3) == 1.0
    # 0 relevant in top 3 -> 0/3 = 0.0
    assert compute_precision_at_k(["doc_X", "doc_Y", "doc_Z"], relevant, k=3) == 0.0


def test_precision_at_k_fewer_than_k_results():
    """Fewer than k results retains denominator k (unretrieved ranks count as non-relevant)."""
    retrieved = ["doc_A"]  # 1 result returned
    relevant = {"doc_A"}
    # Standard IR Precision@3 = 1 / 3 = 0.3333
    assert compute_precision_at_k(retrieved, relevant, k=3) == 0.3333


def test_precision_at_k_duplicate_retrieved_items():
    """Duplicate retrieved predictions do not inflate precision."""
    retrieved = ["doc_A", "doc_A", "doc_B"]
    relevant = {"doc_A"}
    # Unique relevant hit is only doc_A -> 1/3 = 0.3333
    assert compute_precision_at_k(retrieved, relevant, k=3) == 0.3333


def test_precision_at_k_empty_and_invalid_k():
    """Empty inputs or invalid k return 0.0."""
    assert compute_precision_at_k([], {"doc_A"}, k=3) == 0.0
    assert compute_precision_at_k(["doc_A"], set(), k=3) == 0.0
    assert compute_precision_at_k(["doc_A"], {"doc_A"}, k=0) == 0.0
    assert compute_precision_at_k(["doc_A"], {"doc_A"}, k=-1) == 0.0


# ---------------------------------------------------------------------------
# 3. Reciprocal Rank (RR) / MRR Tests
# ---------------------------------------------------------------------------

def test_reciprocal_rank_at_each_position():
    """Tests RR at ranks 1, 2, 3 and beyond k."""
    relevant = {"target"}
    # Rank 1 -> 1/1 = 1.0
    assert compute_reciprocal_rank(["target", "other1", "other2"], relevant, k=3) == 1.0
    # Rank 2 -> 1/2 = 0.5
    assert compute_reciprocal_rank(["other1", "target", "other2"], relevant, k=3) == 0.5
    # Rank 3 -> 1/3 = 0.3333
    assert compute_reciprocal_rank(["other1", "other2", "target"], relevant, k=3) == 0.3333
    # Rank 4 (beyond k=3) -> 0.0
    assert compute_reciprocal_rank(["other1", "other2", "other3", "target"], relevant, k=3) == 0.0


def test_reciprocal_rank_empty_and_no_match():
    """Empty lists or no relevant document yields 0.0."""
    assert compute_reciprocal_rank([], {"target"}, k=3) == 0.0
    assert compute_reciprocal_rank(["other1"], set(), k=3) == 0.0
    assert compute_reciprocal_rank(["other1", "other2"], {"target"}, k=3) == 0.0


# ---------------------------------------------------------------------------
# 4. NDCG@K Tests
# ---------------------------------------------------------------------------

def test_ndcg_at_k_hand_calculated():
    """Hand-calculated NDCG@3 with binary relevance."""
    relevant = {"doc_A"}
    # Relevant at rank 1:
    # DCG = 1 / log2(2) = 1.0, IDCG = 1.0 -> NDCG = 1.0
    assert compute_ndcg_at_k(["doc_A", "doc_B", "doc_C"], relevant, k=3) == 1.0

    # Relevant at rank 2:
    # DCG = 1 / log2(3) = 0.630929..., IDCG = 1.0 -> NDCG = 0.6309
    expected_rank2 = round(1.0 / math.log2(3), 4)
    assert compute_ndcg_at_k(["doc_B", "doc_A", "doc_C"], relevant, k=3) == expected_rank2

    # Relevant at rank 3:
    # DCG = 1 / log2(4) = 0.5, IDCG = 1.0 -> NDCG = 0.5
    assert compute_ndcg_at_k(["doc_B", "doc_C", "doc_A"], relevant, k=3) == 0.5

    # None relevant:
    assert compute_ndcg_at_k(["doc_X", "doc_Y", "doc_Z"], relevant, k=3) == 0.0


def test_ndcg_at_k_multi_relevant():
    """Two relevant items: both in top 2 gives NDCG = 1.0."""
    relevant = {"doc_A", "doc_B"}
    # DCG = 1/log2(2) + 1/log2(3), IDCG is identical -> NDCG = 1.0
    assert compute_ndcg_at_k(["doc_A", "doc_B", "doc_C"], relevant, k=3) == 1.0

    # Relevant items at rank 2 and 3:
    # DCG = 1/log2(3) + 1/log2(4)
    # IDCG = 1/log2(2) + 1/log2(3)
    idcg = 1.0 + (1.0 / math.log2(3))
    dcg = (1.0 / math.log2(3)) + (1.0 / math.log2(4))
    expected = round(dcg / idcg, 4)
    assert compute_ndcg_at_k(["doc_C", "doc_A", "doc_B"], relevant, k=3) == expected


def test_ndcg_at_k_empty_inputs():
    """Empty relevant set or empty retrieved list yields 0.0."""
    assert compute_ndcg_at_k([], {"doc_A"}, k=3) == 0.0
    assert compute_ndcg_at_k(["doc_A"], set(), k=3) == 0.0
    assert compute_ndcg_at_k([], set(), k=3) == 0.0


# ---------------------------------------------------------------------------
# 5. Source Attribution Accuracy Tests
# ---------------------------------------------------------------------------

def test_source_attribution_accuracy():
    """Attribution accuracy checks top-1 retrieved document against expected set."""
    expected = {"returns_and_refunds.pdf"}
    assert compute_source_attribution_accuracy(["returns_and_refunds.pdf", "other.pdf"], expected) == 1.0
    assert compute_source_attribution_accuracy(["wrong.pdf", "returns_and_refunds.pdf"], expected) == 0.0
    assert compute_source_attribution_accuracy([], expected) == 0.0
    assert compute_source_attribution_accuracy(["doc.pdf"], set()) == 0.0


# ---------------------------------------------------------------------------
# 6. No-Match Binary Classification Metrics Tests
# ---------------------------------------------------------------------------

def test_no_match_metrics_perfect_classification():
    """Perfect rejection of unanswerable and matching of answerable."""
    y_true_unans = [True, True, False, False]
    y_pred_no_match = [True, True, False, False]
    res = compute_no_match_metrics(y_true_unans, y_pred_no_match)

    assert res["tp"] == 2
    assert res["tn"] == 2
    assert res["fp"] == 0
    assert res["fn"] == 0
    assert res["precision"] == 1.0
    assert res["recall"] == 1.0
    assert res["f1"] == 1.0
    assert res["accuracy"] == 1.0


def test_no_match_metrics_contingency_table_hand_calculated():
    """Hand-calculated contingency table with 1 of each (TP, FP, TN, FN)."""
    # Item 1: unanswerable=True,  predicted NO_MATCH=True  -> TP
    # Item 2: unanswerable=True,  predicted NO_MATCH=False -> FN
    # Item 3: unanswerable=False, predicted NO_MATCH=True  -> FP
    # Item 4: unanswerable=False, predicted NO_MATCH=False -> TN
    y_true_unans = [True, True, False, False]
    y_pred_no_match = [True, False, True, False]
    res = compute_no_match_metrics(y_true_unans, y_pred_no_match)

    assert res["tp"] == 1
    assert res["fn"] == 1
    assert res["fp"] == 1
    assert res["tn"] == 1
    assert res["precision"] == 0.5  # 1 / (1 + 1)
    assert res["recall"] == 0.5     # 1 / (1 + 1)
    assert res["f1"] == 0.5
    assert res["accuracy"] == 0.5


def test_no_match_metrics_zero_denominators_safe():
    """Edge cases with zero positive predictions or zero unanswerable queries."""
    # Zero positive predictions: TP=0, FP=0 -> precision=0.0
    res = compute_no_match_metrics([True, False], [False, False])
    assert res["precision"] == 0.0
    assert res["recall"] == 0.0
    assert res["f1"] == 0.0

    # Length mismatch raises ValueError
    with pytest.raises(ValueError, match="Length mismatch"):
        compute_no_match_metrics([True], [True, False])


# ---------------------------------------------------------------------------
# 7. Latency Statistics Tests
# ---------------------------------------------------------------------------

def test_latency_statistics_hand_calculated():
    """Hand-calculated latency stats on known latencies."""
    lats = [10.0, 20.0, 30.0, 40.0, 50.0]
    stats = compute_latency_statistics(lats)
    assert stats["count"] == 5
    assert stats["mean_ms"] == 30.0
    assert stats["median_ms"] == 30.0
    assert stats["min_ms"] == 10.0
    assert stats["max_ms"] == 50.0
    assert stats["p95_ms"] == 50.0


def test_latency_statistics_even_number_and_single_item():
    """Tests median calculation on even length and single-item list."""
    stats_even = compute_latency_statistics([10.0, 20.0])
    assert stats_even["median_ms"] == 15.0

    stats_single = compute_latency_statistics([42.5])
    assert stats_single["count"] == 1
    assert stats_single["mean_ms"] == 42.5
    assert stats_single["median_ms"] == 42.5
    assert stats_single["p95_ms"] == 42.5

    stats_empty = compute_latency_statistics([])
    assert stats_empty["count"] == 0
    assert stats_empty["mean_ms"] == 0.0
