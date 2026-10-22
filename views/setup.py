"""Setup page: KB ingestion, mode selection, scenario, validation."""
import streamlit as st

from utils import rag_stub, storage
from utils.pipeline_stub import SAMPLE_TRANSCRIPT
from utils.validation import MODES, parse_transcript, validate_setup

# Description shown under each mode selection
MODE_INFO = {
    "Simulator": "The AI sends customer messages turn by turn based on the scenario.",
    "Manual":    "You paste each incoming customer message yourself.",
    "Replay":    "Step through a saved transcript message by message.",
}


def kb_section():
    """Knowledge base upload and indexing card."""
    st.markdown(
        '<p class="section-heading">Support Knowledge Base</p>'
        '<p class="section-desc">'
        "Upload PDF documents to help the assistant retrieve relevant "
        "information during coaching sessions."
        "</p>",
        unsafe_allow_html=True,
    )

    files = st.file_uploader(
        "Select PDF files to upload",
        type=["pdf"],
        accept_multiple_files=True,
        key="kb_files",
        help="Upload FAQ, policy, or support PDFs. They are chunked and indexed automatically.",
    )

    col_ingest, col_clear = st.columns([2, 1])

    if col_ingest.button("Ingest PDFs", use_container_width=True, type="primary"):
        if not files:
            st.error("Please select at least one PDF file before ingesting.")
        else:
            with st.spinner("Chunking and indexing..."):
                res = rag_stub.ingest_pdfs(files)
            for err in res["errors"]:
                st.error(err)
            if res["added"]:
                st.success(
                    f"{res['added']} chunks stored from {len(res['files'])} file(s) "
                    f"— {res['total']} total in knowledge base."
                )

    if col_clear.button("Clear Knowledge Base", use_container_width=True):
        rag_stub.clear()
        st.info("Knowledge base cleared.")

    # Live KB status
    kb = rag_stub.stats()
    if kb["total"]:
        files_str = ", ".join(kb["files"])
        st.markdown(
            f'<span class="kb-status">'
            f'{kb["total"]} chunks indexed &mdash; {files_str}'
            f"</span>",
            unsafe_allow_html=True,
        )
        st.write("")
    else:
        st.caption("Knowledge base is empty. Upload PDFs above to enable retrieval.")


def render():
    """Render the full setup page."""
    s = st.session_state

    # Page header
    st.markdown(
        "<h1>AI Customer Support Coaching Assistant</h1>"
        '<p class="page-subtitle">'
        "Practice real support conversations with AI feedback and company knowledge."
        "</p>",
        unsafe_allow_html=True,
    )

    if s.get("restored"):
        st.success(
            "Session restored. Use the sidebar to switch sessions "
            "or fill in the form below to start a new one."
        )
        s.restored = False

    # ── Card 1: Knowledge Base ─────────────────────────────────────────────
    with st.container(border=True):
        kb_section()

    st.write("")  # vertical rhythm

    # ── Card 2: Session Setup ──────────────────────────────────────────────
    with st.container(border=True):
        st.markdown(
            '<p class="section-heading">Session Setup</p>',
            unsafe_allow_html=True,
        )

        # Mode selection
        mode = st.radio(
            "Interaction Mode",
            MODES,
            horizontal=True,
            key="f_mode",
        )
        st.caption(MODE_INFO[mode])

        st.write("")  # small gap

        # Product context and scenario — two columns
        col_prod, col_scen = st.columns([1, 1], gap="medium")
        product = col_prod.text_input(
            "Product Context",
            key="f_product",
            placeholder="e.g. Acme Wireless Router X200",
        )
        scenario = col_scen.text_area(
            "Customer Scenario",
            key="f_scenario",
            height=100,
            placeholder="e.g. Customer was charged twice and wants a refund.",
        )

        # Mode-specific controls
        persona, max_turns, script = "Calm", 5, []

        if mode == "Simulator":
            col_persona, col_turns = st.columns([1, 1], gap="medium")
            persona = col_persona.selectbox(
                "Customer Persona",
                ["Calm", "Impatient", "Angry", "Confused"],
                key="f_persona",
            )
            max_turns = col_turns.slider(
                "Number of Customer Turns", 3, 8, 5, key="f_turns"
            )

        elif mode == "Replay":
            src = st.radio(
                "Transcript source",
                ["Bundled sample", "Upload .txt"],
                horizontal=True,
                key="f_src",
            )
            raw = SAMPLE_TRANSCRIPT
            if src == "Upload .txt":
                up = st.file_uploader(
                    "Transcript file (.txt with lines like 'Customer: ...' / 'Agent: ...')",
                    type=["txt"],
                    key="f_tx",
                )
                raw = up.getvalue().decode("utf-8", errors="ignore") if up else ""
            script = parse_transcript(raw)
            if script:
                st.caption(f"Parsed {len(script)} messages from transcript.")

        elif mode == "Manual":
            st.caption("You will paste each customer message inside the coaching console.")

        st.write("")

        if st.button(
            "Start coaching session",
            type="primary",
            use_container_width=True,
        ):
            errs = validate_setup(mode, product, scenario, script)
            if errs:
                st.error(
                    "Please fix the following before starting:\n\n"
                    + "\n".join(f"- {e}" for e in errs)
                )
            else:
                s.sid = storage.new_id()
                st.query_params["sid"] = s.sid
                s.config = {
                    "mode": mode,
                    "product": product.strip(),
                    "scenario": scenario.strip(),
                    "persona": persona,
                    "max_turns": max_turns,
                    "replay_script": script,
                }
                s.messages, s.analyses, s.tone, s.replay_idx = [], [], [], 0
                s.view = "console"
                storage.save(s)
                st.rerun()
