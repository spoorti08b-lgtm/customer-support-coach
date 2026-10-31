"""Centralized configuration and path management for Customer Support Coach.

Resolves absolute paths anchored at the repository root so the application,
services, CLI runners, and test suites work consistently from any working directory.
"""

from __future__ import annotations

from pathlib import Path

# Repository root (one level up from backend/)
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Data directories and persistence paths
DATA_DIR = PROJECT_ROOT / "data"
CHROMA_DIR = DATA_DIR / "chroma"
SESSIONS_DIR = DATA_DIR / "sessions"
KB_INDEX_PATH = DATA_DIR / "kb_index.json"
SAMPLE_PDFS_DIR = DATA_DIR / "sample_pdfs"
EVAL_PATH = DATA_DIR / "evaluation" / "retrieval_eval.json"
AGENT_EVAL_PATH = DATA_DIR / "evaluation" / "agent_eval_dataset.json"
REPLAY_SAMPLE_PATH = DATA_DIR / "samples" / "replay_demo.txt"
TEST_TEMP_DIR = DATA_DIR / "test_temp"

# Documentation and visual artifacts
DOCS_DIR = PROJECT_ROOT / "docs"
DOCS_SCREENSHOTS_DIR = DOCS_DIR / "screenshots"
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts" / "visual_qa"

# Model & RAG constants
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
CHROMA_COLLECTION_NAME = "support_kb"
MAX_PDF_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB
CHUNK_SIZE_CHARS = 500
CHUNK_OVERLAP_CHARS = 100
DEFAULT_TOP_K = 3

# Ensure critical persistence directories exist
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
DOCS_SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
