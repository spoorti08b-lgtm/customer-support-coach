"""Evaluation Metrics for Knowledge Retrieval.

Defines mathematically rigorous, standard Information Retrieval (IR) metrics
and binary classification metrics for the Knowledge Recommendation Agent:
  - Recall@K
  - Precision@K
  - Reciprocal Rank (RR) / Mean Reciprocal Rank (MRR)
  - Normalized Discounted Cumulative Gain (NDCG@K)
  - No-match Precision, Recall, and F1
  - Source Attribution Accuracy
  - Latency Summary Statistics
"""

from __future__ import annotations

import math
from typing import Any, Sequence


def compute_recall_at_k(
    retrieved: Sequence[str],
    relevant: set[str] | Sequence[str],
    k: int = 3,
) -> float:
    """Compute Recall@K.
    
    Definition:
        Recall@K = |Retrieved[:K] ∩ Relevant| / |Relevant|
    
    Edge cases:
        - If relevant set is empty: returns 0.0 (or 1.0 if retrieved is also empty and relevant is empty).
        - If retrieved has fewer than K items: evaluates on the available items,
          with denominator remaining |Relevant|.
        - Duplicate items in `retrieved[:k]` are deduplicated so a repeated
          identifier cannot artificially increase recall.
    """
    rel_set = set(relevant)
    if not rel_set:
        return 0.0

    retrieved_k = list(retrieved[:k])
    # Deduplicate while preserving order
    seen: set[str] = set()
    unique_retrieved_k: list[str] = []
    for item in retrieved_k:
        if item not in seen:
            seen.add(item)
            unique_retrieved_k.append(item)

    hits = sum(1 for item in unique_retrieved_k if item in rel_set)
    return round(hits / len(rel_set), 4)


def compute_precision_at_k(
    retrieved: Sequence[str],
    relevant: set[str] | Sequence[str],
    k: int = 3,
) -> float:
    """Compute Precision@K using standard Information Retrieval conventions.
    
    Definition:
        Precision@K = |Retrieved[:K] ∩ Relevant| / K
    
    Edge cases:
        - Standard IR convention: The denominator is strictly K (not the number
          of returned items). If fewer than K items are returned (e.g., 1 hit),
          the remaining ranks are treated as unretrieved non-relevant positions.
        - If k <= 0: returns 0.0.
        - If relevant set is empty: returns 0.0.
        - Duplicate items in `retrieved[:k]` are deduplicated so duplicate
          predictions do not inflate the intersection count.
    """
    if k <= 0:
        return 0.0

    rel_set = set(relevant)
    if not rel_set:
        return 0.0

    retrieved_k = list(retrieved[:k])
    seen: set[str] = set()
    unique_retrieved_k: list[str] = []
    for item in retrieved_k:
        if item not in seen:
            seen.add(item)
            unique_retrieved_k.append(item)

    hits = sum(1 for item in unique_retrieved_k if item in rel_set)
    return round(hits / k, 4)


def compute_reciprocal_rank(
    retrieved: Sequence[str],
    relevant: set[str] | Sequence[str],
    k: int = 3,
) -> float:
    """Compute Reciprocal Rank (RR) at cutoff K.
    
    Definition:
        RR = 1 / rank  where rank is the 1-based index of the FIRST relevant
                       item found in retrieved[:K].
        If no relevant item is found within the top K results, RR = 0.0.
    """
    if k <= 0:
        return 0.0

    rel_set = set(relevant)
    if not rel_set:
        return 0.0

    for idx, item in enumerate(retrieved[:k], start=1):
        if item in rel_set:
            return round(1.0 / idx, 4)

    return 0.0


def compute_ndcg_at_k(
    retrieved: Sequence[str],
    relevant: set[str] | Sequence[str],
    k: int = 3,
) -> float:
    """Compute Normalized Discounted Cumulative Gain at K (NDCG@K) with binary relevance.
    
    Definition:
        DCG@K  = sum_{i=1}^{min(K, |retrieved|)} ( rel_i / log2(i + 1) )
        IDCG@K = sum_{i=1}^{min(K, |relevant|)}  ( 1 / log2(i + 1) )
        NDCG@K = DCG@K / IDCG@K
    
    Edge cases:
        - If IDCG@K == 0 (no relevant items exist): returns 0.0.
        - Binary relevance: rel_i = 1 if retrieved[i-1] in relevant else 0.
        - Duplicates in retrieved are ignored after their first appearance.
    """
    if k <= 0:
        return 0.0

    rel_set = set(relevant)
    if not rel_set:
        return 0.0

    # Ideal DCG: all possible relevant items placed at top ranks up to K
    num_ideal = min(k, len(rel_set))
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, num_ideal + 1))
    if idcg == 0.0:
        return 0.0

    # Actual DCG
    dcg = 0.0
    seen: set[str] = set()
    for idx, item in enumerate(retrieved[:k], start=1):
        if item in rel_set and item not in seen:
            seen.add(item)
            dcg += 1.0 / math.log2(idx + 1)

    return round(dcg / idcg, 4)


def compute_source_attribution_accuracy(
    retrieved_docs: Sequence[str],
    expected_docs: set[str] | Sequence[str],
) -> float:
    """Compute top-1 Source Document Attribution Accuracy.
    
    Definition:
        1.0 if the top-ranked retrieved document matches one of the expected
        documents; 0.0 otherwise.
    """
    exp_set = set(expected_docs)
    if not exp_set or not retrieved_docs:
        return 0.0

    return 1.0 if retrieved_docs[0] in exp_set else 0.0


def compute_no_match_metrics(
    y_true_unanswerable: Sequence[bool],
    y_pred_no_match: Sequence[bool],
) -> dict[str, Any]:
    """Compute binary classification metrics for the NO_MATCH decision.
    
    Explicit Definition of Classes:
      - Positive class (y = 1):
          The query is UNANSWERABLE (i.e., `is_answerable == False`), meaning
          the knowledge base lacks supporting evidence or the query is out-of-domain.
      - Negative class (y = 0):
          The query is ANSWERABLE (i.e., `is_answerable == True`).
      - Predicted positive (y_hat = 1):
          The agent produced `NO_MATCH` (i.e., `status == NO_MATCH`).
      - Predicted negative (y_hat = 0):
          The agent produced `SUCCESS` with retrieved passages.
    
    Contingency table:
      - True Positive (TP):  Unanswerable query correctly rejected as NO_MATCH.
      - False Positive (FP): Answerable query wrongly rejected as NO_MATCH (false rejection).
      - True Negative (TN):  Answerable query correctly matched with passages.
      - False Negative (FN): Unanswerable query wrongly matched with passages (hallucinated match).
    
    Returns:
      dict with keys: tp, fp, tn, fn, precision, recall, f1, accuracy, total
    """
    if len(y_true_unanswerable) != len(y_pred_no_match):
        raise ValueError(
            f"Length mismatch: y_true ({len(y_true_unanswerable)}) vs y_pred ({len(y_pred_no_match)})"
        )

    tp = sum(1 for yt, yp in zip(y_true_unanswerable, y_pred_no_match) if yt and yp)
    fp = sum(1 for yt, yp in zip(y_true_unanswerable, y_pred_no_match) if (not yt) and yp)
    tn = sum(1 for yt, yp in zip(y_true_unanswerable, y_pred_no_match) if (not yt) and (not yp))
    fn = sum(1 for yt, yp in zip(y_true_unanswerable, y_pred_no_match) if yt and (not yp))

    total = len(y_true_unanswerable)
    accuracy = round((tp + tn) / total, 4) if total > 0 else 0.0
    precision = round(tp / (tp + fp), 4) if (tp + fp) > 0 else 0.0
    recall = round(tp / (tp + fn), 4) if (tp + fn) > 0 else 0.0
    f1 = (
        round(2 * (precision * recall) / (precision + recall), 4)
        if (precision + recall) > 0
        else 0.0
    )

    return {
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "accuracy": accuracy,
        "total": total,
    }


def compute_latency_statistics(latencies_ms: Sequence[float]) -> dict[str, float]:
    """Compute summary statistics for retrieval latency in milliseconds.
    
    Returns:
      dict with: count, mean_ms, median_ms, p95_ms, min_ms, max_ms
    """
    if not latencies_ms:
        return {
            "count": 0,
            "mean_ms": 0.0,
            "median_ms": 0.0,
            "p95_ms": 0.0,
            "min_ms": 0.0,
            "max_ms": 0.0,
        }

    sorted_lat = sorted(latencies_ms)
    n = len(sorted_lat)

    mean_val = sum(sorted_lat) / n

    # Median (p50)
    if n % 2 == 1:
        median_val = sorted_lat[n // 2]
    else:
        median_val = (sorted_lat[(n // 2) - 1] + sorted_lat[n // 2]) / 2.0

    # 95th percentile (nearest rank method)
    p95_idx = min(n - 1, math.ceil(0.95 * n) - 1)
    p95_val = sorted_lat[p95_idx]

    return {
        "count": n,
        "mean_ms": round(mean_val, 2),
        "median_ms": round(median_val, 2),
        "p95_ms": round(p95_val, 2),
        "min_ms": round(sorted_lat[0], 2),
        "max_ms": round(sorted_lat[-1], 2),
    }
