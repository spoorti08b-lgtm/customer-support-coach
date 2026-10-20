"""Runnable demo: ingest the synthetic sample PDFs and ask three questions.

Run from the repository root (PowerShell):

    $env:PYTHONPATH = "src"
    python examples/rag_demo.py

The first run downloads the embedding model (~80 MB, needs internet).
Use --persist-dir to choose where ChromaDB stores its files.
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from customer_support_coach.rag import RagConfig, RagError, RagPipeline  # noqa: E402

QUESTIONS = [
    "A customer says they forgot their password. What should they do?",
    "How long do refunds take?",
    "My parcel has not arrived yet.",
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--docs", default=str(ROOT / "examples" / "sample_docs"))
    parser.add_argument("--persist-dir", default=str(ROOT / "data" / "rag" / "demo_chroma"))
    parser.add_argument("--query", help="ask a single custom question instead of the built-in ones")
    args = parser.parse_args()

    try:
        with RagPipeline(RagConfig(persist_directory=args.persist_dir)) as rag:
            report = rag.ingest_directory(args.docs)
            print(report.summary())
            total = rag.get_collection_stats()["total_chunks"]
            print("\nCollection:", total, "chunks\n")
            if total == 0:
                print("Nothing was ingested, so there is nothing to search. See the errors above.",
                      file=sys.stderr)
                return 1

            for question in [args.query] if args.query else QUESTIONS:
                print(f"Q: {question}")
                for hit in rag.search(question, top_k=3):
                    print(f"  #{hit.rank}  {hit.citation}  "
                          f"(cosine distance {hit.distance:.3f}, chunk {hit.chunk_id})")
                    print("      " + hit.text.replace("\n", " ")[:140] + "...")
                print()
    except RagError as exc:
        print(f"RAG error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
