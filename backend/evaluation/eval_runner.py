"""Knowledge Retrieval Evaluation Runner.

Executes the labeled evaluation dataset against the Knowledge Recommendation Agent,
measures retrieval latency, computes IR and classification metrics, and generates
detailed per-query and aggregate reports.
"""

from __future__ import annotations

import json
from pathlib import Path
import time
from typing import Any, Sequence

from backend.config import AGENT_EVAL_PATH
from backend.evaluation.eval_metrics import (
    compute_latency_statistics,
    compute_ndcg_at_k,
    compute_no_match_metrics,
    compute_precision_at_k,
    compute_recall_at_k,
    compute_reciprocal_rank,
    compute_source_attribution_accuracy,
)
from backend.orchestrator.knowledge_schemas import (
    ConversationHistoryItem,
    KnowledgeExecutionStatus,
    KnowledgeRecommendationRequest,
    KnowledgeRecommendationResponse,
)
from backend.services import rag_stub
from backend.services.knowledge_agent import KnowledgeRecommendationAgent


def load_evaluation_dataset(path: Path | str | None = None) -> list[dict[str, Any]]:
    """Load the evaluation dataset from disk."""
    data_path = Path(path) if path else AGENT_EVAL_PATH
    if not data_path.exists():
        raise FileNotFoundError(f"Evaluation dataset not found at: {data_path}")

    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError(f"Dataset root must be a list of items, got {type(data)}")

    return data


def run_evaluation(
    dataset_path: Path | str | None = None,
    agent: KnowledgeRecommendationAgent | None = None,
    k: int = 3,
) -> dict[str, Any]:
    """Run full evaluation suite over the labeled dataset using the live agent.
    
    Returns a comprehensive result dictionary containing per-query results,
    aggregate metrics, contingency counts, category breakdowns, and latency stats.
    """
    # Verify index availability
    stats = rag_stub.stats()
    if stats.get("total", 0) == 0:
        # Attempt to load sample PDFs
        load_res = rag_stub.load_sample_pdfs()
        stats = rag_stub.stats()
        if stats.get("total", 0) == 0:
            raise RuntimeError(
                "ChromaDB vector store is empty and sample PDFs could not be loaded. "
                "Evaluation cannot run without an active indexed knowledge base."
            )

    dataset = load_evaluation_dataset(dataset_path)
    rec_agent = agent or KnowledgeRecommendationAgent()

    per_query_results: list[dict[str, Any]] = []
    latencies_ms: list[float] = []

    for item in dataset:
        qid = item["query_id"]
        msg = item["message"]
        intent = item.get("intent")
        raw_history = item.get("history", [])
        product = item.get("product")
        is_answerable = bool(item.get("is_answerable", True))
        expected_docs = item.get("expected_docs", [])
        expected_chunks = item.get("expected_chunks", [])
        category = item.get("category", "unspecified")

        history_items = [
            ConversationHistoryItem.model_validate(h) if isinstance(h, dict) else h
            for h in raw_history
        ]

        req = KnowledgeRecommendationRequest(
            message=msg,
            intent=intent,
            history=history_items,
            product=product,
            limit=k,
        )

        t0 = time.perf_counter()
        resp: KnowledgeRecommendationResponse = rec_agent.recommend(req)
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        latencies_ms.append(elapsed_ms)

        retrieved_docs = [p.source for p in resp.passages]
        retrieved_chunks = [p.chunk_id for p in resp.passages if p.chunk_id]
        top_score = resp.passages[0].score if resp.passages else 0.0
        top_doc = resp.passages[0].source if resp.passages else None
        top_chunk = resp.passages[0].chunk_id if resp.passages else None

        query_record: dict[str, Any] = {
            "query_id": qid,
            "category": category,
            "message": msg,
            "synthesized_query": resp.query,
            "is_answerable": is_answerable,
            "expected_docs": expected_docs,
            "expected_chunks": expected_chunks,
            "execution_status": resp.status.value,
            "no_match": resp.no_match,
            "error": resp.error,
            "latency_ms": elapsed_ms,
            "retrieved_count": len(resp.passages),
            "top_doc": top_doc,
            "top_chunk": top_chunk,
            "top_score": top_score,
            "retrieved_docs": retrieved_docs,
            "retrieved_chunks": retrieved_chunks,
        }

        if is_answerable:
            query_record["doc_recall_at_k"] = compute_recall_at_k(retrieved_docs, expected_docs, k=k)
            query_record["chunk_recall_at_k"] = (
                compute_recall_at_k(retrieved_chunks, expected_chunks, k=k)
                if expected_chunks
                else None
            )
            query_record["doc_precision_at_k"] = compute_precision_at_k(retrieved_docs, expected_docs, k=k)
            query_record["chunk_precision_at_k"] = (
                compute_precision_at_k(retrieved_chunks, expected_chunks, k=k)
                if expected_chunks
                else None
            )
            query_record["reciprocal_rank"] = compute_reciprocal_rank(retrieved_docs, expected_docs, k=k)
            query_record["ndcg_at_k"] = compute_ndcg_at_k(retrieved_docs, expected_docs, k=k)
            query_record["source_attribution_accuracy"] = compute_source_attribution_accuracy(
                retrieved_docs, expected_docs
            )
        else:
            query_record["is_correct_no_match"] = bool(resp.status == KnowledgeExecutionStatus.NO_MATCH)

        per_query_results.append(query_record)

    # -----------------------------------------------------------------------
    # Aggregate Metrics Calculation
    # -----------------------------------------------------------------------
    ans_queries = [r for r in per_query_results if r["is_answerable"]]
    unans_queries = [r for r in per_query_results if not r["is_answerable"]]

    # IR metrics over answerable queries
    if ans_queries:
        mean_doc_recall = round(sum(r["doc_recall_at_k"] for r in ans_queries) / len(ans_queries), 4)
        chunk_recalls = [r["chunk_recall_at_k"] for r in ans_queries if r["chunk_recall_at_k"] is not None]
        mean_chunk_recall = (
            round(sum(chunk_recalls) / len(chunk_recalls), 4) if chunk_recalls else 0.0
        )
        mean_doc_precision = round(sum(r["doc_precision_at_k"] for r in ans_queries) / len(ans_queries), 4)
        chunk_precisions = [r["chunk_precision_at_k"] for r in ans_queries if r["chunk_precision_at_k"] is not None]
        mean_chunk_precision = (
            round(sum(chunk_precisions) / len(chunk_precisions), 4) if chunk_precisions else 0.0
        )
        mrr = round(sum(r["reciprocal_rank"] for r in ans_queries) / len(ans_queries), 4)
        mean_ndcg = round(sum(r["ndcg_at_k"] for r in ans_queries) / len(ans_queries), 4)
        mean_attribution = round(
            sum(r["source_attribution_accuracy"] for r in ans_queries) / len(ans_queries), 4
        )
    else:
        mean_doc_recall = 0.0
        mean_chunk_recall = 0.0
        mean_doc_precision = 0.0
        mean_chunk_precision = 0.0
        mrr = 0.0
        mean_ndcg = 0.0
        mean_attribution = 0.0

    # No-match classification metrics across the entire dataset
    y_true_unans = [not r["is_answerable"] for r in per_query_results]
    y_pred_no_match = [r["execution_status"] == KnowledgeExecutionStatus.NO_MATCH.value for r in per_query_results]
    no_match_metrics = compute_no_match_metrics(y_true_unans, y_pred_no_match)

    # Category breakdowns
    categories = sorted(list({r["category"] for r in per_query_results}))
    category_breakdown: dict[str, Any] = {}
    for cat in categories:
        cat_records = [r for r in per_query_results if r["category"] == cat]
        cat_ans = [r for r in cat_records if r["is_answerable"]]
        if cat_ans:
            cat_metrics = {
                "count": len(cat_records),
                "answerable": True,
                "doc_recall_at_k": round(sum(r["doc_recall_at_k"] for r in cat_ans) / len(cat_ans), 4),
                "mrr": round(sum(r["reciprocal_rank"] for r in cat_ans) / len(cat_ans), 4),
                "ndcg_at_k": round(sum(r["ndcg_at_k"] for r in cat_ans) / len(cat_ans), 4),
                "source_attribution_accuracy": round(
                    sum(r["source_attribution_accuracy"] for r in cat_ans) / len(cat_ans), 4
                ),
            }
        else:
            cat_correct = sum(1 for r in cat_records if r.get("is_correct_no_match"))
            cat_metrics = {
                "count": len(cat_records),
                "answerable": False,
                "correct_no_match": cat_correct,
                "rejection_accuracy": round(cat_correct / len(cat_records), 4) if cat_records else 0.0,
            }
        category_breakdown[cat] = cat_metrics

    latency_stats = compute_latency_statistics(latencies_ms)

    return {
        "dataset_size": len(dataset),
        "answerable_count": len(ans_queries),
        "unanswerable_count": len(unans_queries),
        "evaluated_count": len(per_query_results),
        "k": k,
        "metrics": {
            "recall_at_k_doc": mean_doc_recall,
            "recall_at_k_chunk": mean_chunk_recall,
            "precision_at_k_doc": mean_doc_precision,
            "precision_at_k_chunk": mean_chunk_precision,
            "mrr": mrr,
            "ndcg_at_k": mean_ndcg,
            "source_attribution_accuracy": mean_attribution,
            "no_match_precision": no_match_metrics["precision"],
            "no_match_recall": no_match_metrics["recall"],
            "no_match_f1": no_match_metrics["f1"],
            "no_match_accuracy": no_match_metrics["accuracy"],
            "contingency_table": {
                "tp": no_match_metrics["tp"],
                "fp": no_match_metrics["fp"],
                "tn": no_match_metrics["tn"],
                "fn": no_match_metrics["fn"],
            },
        },
        "latency": latency_stats,
        "category_breakdown": category_breakdown,
        "per_query_results": per_query_results,
    }


def format_evaluation_summary_table(results: dict[str, Any]) -> str:
    """Format evaluation results into a human-readable text table."""
    m = results["metrics"]
    lat = results["latency"]
    lines = [
        "==================================================================",
        f"KNOWLEDGE RETRIEVAL EVALUATION REPORT (k={results['k']})",
        "==================================================================",
        f"Dataset Size:           {results['dataset_size']}",
        f"  - Answerable Queries: {results['answerable_count']}",
        f"  - Unanswerable:       {results['unanswerable_count']}",
        "------------------------------------------------------------------",
        "INFORMATION RETRIEVAL METRICS (Answerable Queries):",
        f"  Recall@{results['k']} (Doc-level):      {m['recall_at_k_doc'] * 100:.2f}%",
        f"  Recall@{results['k']} (Chunk-level):    {m['recall_at_k_chunk'] * 100:.2f}%",
        f"  Precision@{results['k']} (Doc-level):   {m['precision_at_k_doc'] * 100:.2f}%",
        f"  Precision@{results['k']} (Chunk-level): {m['precision_at_k_chunk'] * 100:.2f}%",
        f"  Mean Reciprocal Rank (MRR): {m['mrr']:.4f}",
        f"  NDCG@{results['k']}:                    {m['ndcg_at_k']:.4f}",
        f"  Source Attribution Acc:     {m['source_attribution_accuracy'] * 100:.2f}%",
        "------------------------------------------------------------------",
        "NO-MATCH CLASSIFICATION METRICS (Unanswerable / Out-of-Domain):",
        f"  Precision:                  {m['no_match_precision'] * 100:.2f}%",
        f"  Recall:                     {m['no_match_recall'] * 100:.2f}%",
        f"  F1-Score:                   {m['no_match_f1'] * 100:.2f}%",
        f"  Accuracy:                   {m['no_match_accuracy'] * 100:.2f}%",
        f"  Contingency (TP/FP/TN/FN):  {m['contingency_table']['tp']} / {m['contingency_table']['fp']} / {m['contingency_table']['tn']} / {m['contingency_table']['fn']}",
        "------------------------------------------------------------------",
        "RETRIEVAL LATENCY (ms):",
        f"  Mean:                       {lat['mean_ms']:.1f} ms",
        f"  Median (p50):               {lat['median_ms']:.1f} ms",
        f"  95th Percentile (p95):      {lat['p95_ms']:.1f} ms",
        f"  Min / Max:                  {lat['min_ms']:.1f} ms / {lat['max_ms']:.1f} ms",
        "==================================================================",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    res = run_evaluation()
    print(format_evaluation_summary_table(res))

    results_out_path = Path(__file__).resolve().parents[2] / "data" / "evaluation" / "agent_eval_results.json"
    results_out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(results_out_path, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2)
    print(f"\nDetailed evaluation results saved to: {results_out_path}")
