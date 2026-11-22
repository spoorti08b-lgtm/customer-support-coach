"""Architecture and System Design view with multi-agent specifications and data models."""

from __future__ import annotations

import inspect
from pathlib import Path
import pandas as pd
import streamlit as st

from backend.core import data_models
from backend.config import DOCS_DIR

STUDY_NOTES_PATH = DOCS_DIR / "study_notes.md"
DESIGN_DECISIONS_PATH = DOCS_DIR / "design_decisions.md"


def render_graphviz_diagram() -> None:
    """Render the orchestration and multi-agent flow diagram using Graphviz."""
    dot_code = """
    digraph G {
        rankdir=LR;
        node [shape=box, style="filled,rounded", fontname="sans-serif", fontsize=10, margin="0.2,0.1"];
        edge [color="#6B6475", fontname="sans-serif", fontsize=9];

        // Nodes
        User [label="Frontline Agent\\n(Browser)", fillcolor="#FFF0F6", color="#C2347A"];
        Frontend [label="Streamlit App\\n(app.py & views/)", fillcolor="#FDE7F1", color="#C2347A"];
        Store [label="Session Store\\n(data/sessions/)", fillcolor="#ECE8FB", color="#6D5BD0"];
        RAG [label="Vector Store & RAG\\n(ChromaDB MiniLM)", fillcolor="#DDF5F1", color="#0E9F8E"];
        Orchestrator [label="Orchestrator\\n(run_workflow)", fillcolor="#FFE9DC", color="#B5541B"];

        subgraph cluster_agents {
            label = "Specialized Agent Ecosystem";
            style = "dashed";
            color = "#6B6475";
            fontname = "sans-serif";
            fontsize = 10;

            A1 [label="Customer Simulator [M2]", fillcolor="#FFFFFF", color="#6B6475"];
            A2 [label="Intent & Sentiment [M2]", fillcolor="#FFFFFF", color="#6B6475"];
            A3 [label="Knowledge Recommender [M3]", fillcolor="#FFFFFF", color="#6B6475"];
            A4 [label="Coaching & Response [M3]", fillcolor="#FFFFFF", color="#6B6475"];
            A5 [label="Escalation Risk Monitor [M3]", fillcolor="#FFFFFF", color="#6B6475"];
            A6 [label="Post-Interaction Summary [M4]", fillcolor="#FFFFFF", color="#6B6475"];
        }

        // Edges
        User -> Frontend [label="Turn input / PDF"];
        Frontend -> Store [label="Save / Load JSON"];
        Frontend -> RAG [label="Ingest / Query"];
        Frontend -> Orchestrator [label="WorkflowRequest"];
        Orchestrator -> A1 [style="dotted"];
        Orchestrator -> A2;
        Orchestrator -> A3;
        Orchestrator -> A4;
        Orchestrator -> A5;
        Orchestrator -> A6 [style="dotted"];
        A3 -> RAG [label="Cosine vector search", dir="both", style="dashed"];
        Orchestrator -> Frontend [label="WorkflowResponse"];
    }
    """
    st.graphviz_chart(dot_code, use_container_width=True)


def render() -> None:
    """Render the Architecture, Agent specifications, Data models, and Study notes."""
    st.markdown("<h1>System Architecture & Multi-Agent Design</h1>", unsafe_allow_html=True)
    st.markdown(
        '<p class="page-subtitle">'
        "Architectural specifications, agent roles, data contracts, and engineering notes."
        "</p>",
        unsafe_allow_html=True,
    )

    tab_overview, tab_agents, tab_models, tab_rag, tab_notes = st.tabs([
        "Overview & Flow",
        "Agent Ecosystem (6 Agents)",
        "Data Models",
        "RAG Pipeline Design",
        "Study Notes",
    ])

    with tab_overview:
        st.markdown('<div class="card-title">Orchestration & Data Flow Architecture</div>', unsafe_allow_html=True)
        st.caption("Interactive system topology mapping frontend, storage, vector RAG, and multi-agent coordination.")
        render_graphviz_diagram()

        col1, col2 = st.columns(2)
        with col1:
            with st.container(border=True):
                st.markdown("**Core Design Tenets**")
                st.markdown(
                    "- **Decoupled Architecture:** Frontend views communicate solely via typed schemas and persistent stores.\n"
                    "- **Deterministic Contracts:** Pydantic models validate workflow boundaries at every step.\n"
                    "- **Offline & Local First:** Local MiniLM embeddings and ChromaDB ensure data privacy without external API latency.\n"
                    "- **State Resiliency:** Saved JSON files preserve session states across page reloads and reboots."
                )
        with col2:
            with st.container(border=True):
                st.markdown("**Milestone Roadmap Status**")
                st.markdown(
                    "- **Milestone 1 (Complete):** Core architecture, setup configuration, RAG vector ingestion, session persistence.\n"
                    "- **Milestone 2 (Next):** Customer Simulator & Intent/Sentiment analysis pipeline.\n"
                    "- **Milestone 3:** Live coaching console, escalation risk monitor, knowledge recommendation.\n"
                    "- **Milestone 4:** Post-interaction summary, Kirkpatrick evaluation, historical analytics."
                )

    with tab_agents:
        st.markdown('<div class="card-title">Specialized Agent Responsibilities & Milestone Matrix</div>', unsafe_allow_html=True)
        st.caption("Six specialized agents coordinated by the central orchestrator across project milestones.")

        agents_data = [
            {
                "Agent Name": "Customer Simulator",
                "Milestone": "M2",
                "Primary Responsibility": "Generates dynamic customer messages following persona traits (Calm, Confused, Impatient, Angry) and conversation ladders.",
                "Input Context": "Product context, scenario, selected persona, conversation turn index",
                "Output Artifact": "Simulated customer dialogue turn",
            },
            {
                "Agent Name": "Intent & Sentiment",
                "Milestone": "M2",
                "Primary Responsibility": "Classifies customer intent, extracts emotional tone, and calculates frustration score (0–100%).",
                "Input Context": "Latest customer turn, conversation history, product context",
                "Output Artifact": "Intent label, sentiment classification, frustration percentage",
            },
            {
                "Agent Name": "Knowledge Recommendation",
                "Milestone": "M3",
                "Primary Responsibility": "Queries ChromaDB vector collection using cosine similarity to retrieve top-3 relevant policy excerpts.",
                "Input Context": "Customer query, identified intent, product context",
                "Output Artifact": "Top-3 policy chunks with document names, page numbers, and similarity scores",
            },
            {
                "Agent Name": "Coaching & Response",
                "Milestone": "M3",
                "Primary Responsibility": "Evaluates agent reply tone, empathy, conciseness, and generates context-aware response suggestions.",
                "Input Context": "Draft agent response, retrieved knowledge chunks, customer intent",
                "Output Artifact": "Empathy score, clarity notes, recommended next turn reply",
            },
            {
                "Agent Name": "Escalation Risk Monitor",
                "Milestone": "M3",
                "Primary Responsibility": "Tracks sentiment trajectory across turns to detect churn threats, repeated complaints, and SLA breaches.",
                "Input Context": "Turn history, frustration trend, churn keywords, turn count",
                "Output Artifact": "Escalation risk score (0–100%), warning flags, de-escalation guidance",
            },
            {
                "Agent Name": "Post-Interaction Summary",
                "Milestone": "M4",
                "Primary Responsibility": "Compiles conversation metrics into overall resolution quality score, journey graphs, and actionable takeaways.",
                "Input Context": "Full dialogue transcript, turn sentiment trajectory, tone scores",
                "Output Artifact": "Resolution score (0–100), key strengths, specific growth areas",
            },
        ]
        df_agents = pd.DataFrame(agents_data)
        st.dataframe(df_agents, use_container_width=True, hide_index=True)

    with tab_models:
        st.markdown('<div class="card-title">Domain Data Models (`data_models.py`)</div>', unsafe_allow_html=True)
        st.caption("Source code inspected directly from `backend/core/data_models.py` via `inspect.getsource`.")

        model_classes = [
            ("Session", data_models.Session),
            ("ConversationMessage", data_models.ConversationMessage),
            ("AgentResult", data_models.AgentResult),
            ("InteractionMode", data_models.InteractionMode),
            ("SessionStatus", data_models.SessionStatus),
            ("Speaker", data_models.Speaker),
        ]

        for name, cls_obj in model_classes:
            with st.expander(f"Class: {name}", expanded=(name == "Session")):
                src = inspect.getsource(cls_obj)
                st.code(src, language="python")

    with tab_rag:
        st.markdown('<div class="card-title">Support Knowledge Base RAG Design</div>', unsafe_allow_html=True)
        col_r1, col_r2 = st.columns(2)
        with col_r1:
            with st.container(border=True):
                st.markdown("**1. Ingestion & Preprocessing**")
                st.markdown(
                    "- **PDF Extraction:** Extracts text per page using `pypdf.PdfReader`.\n"
                    "- **Size Guard:** Strict 20 MB file size limit protects memory.\n"
                    "- **Text Validation:** Detects scanned PDFs without OCR and alerts the user cleanly."
                )
            with st.container(border=True):
                st.markdown("**2. Chunking Strategy**")
                st.markdown(
                    "- **Window Size:** 500 characters per chunk.\n"
                    "- **Overlap:** 50 characters between sequential windows.\n"
                    "- **Metadata Preservation:** Injects `doc_name`, `page`, and SHA-256 hash into each chunk."
                )
        with col_r2:
            with st.container(border=True):
                st.markdown("**3. Dense Embeddings & Vector Storage**")
                st.markdown(
                    "- **Embedding Model:** Local `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions).\n"
                    "- **Vector Database:** `ChromaDB PersistentClient` at `data/chroma/`.\n"
                    "- **Distance Metric:** Cosine similarity ($1 - \\text{distance}$).\n"
                    "- **Deduplication:** Hash-based deterministic IDs (`<hash>_p<page>_c<idx>`) prevent duplicate chunks on re-upload."
                )

    with tab_notes:
        sub_study, sub_design = st.tabs(["Study Notes", "Design Decisions"])
        with sub_study:
            st.markdown('<div class="card-title">Study Notes: Support, Coaching & Architecture</div>', unsafe_allow_html=True)
            if STUDY_NOTES_PATH.exists():
                st.markdown(STUDY_NOTES_PATH.read_text(encoding="utf-8"))
            else:
                st.warning("Study notes file not found.")
        with sub_design:
            st.markdown('<div class="card-title">Engineering & Architectural Decisions</div>', unsafe_allow_html=True)
            if DESIGN_DECISIONS_PATH.exists():
                st.markdown(DESIGN_DECISIONS_PATH.read_text(encoding="utf-8"))
            else:
                st.warning("Design decisions file not found.")
