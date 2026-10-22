"""Setup page for knowledge-base ingestion and session configuration."""

import streamlit as st

from utils import rag_stub, storage
from utils.pipeline_stub import SAMPLE_TRANSCRIPT
from utils.validation import MODES, parse_transcript, validate_setup


# Short descriptions for the three interaction modes.
MODE_INFO = {
    "Simulator": "The AI sends customer messages turn by turn based on the scenario.",
    "Manual": "You paste each incoming customer message yourself.",
    "Replay": "Step through a saved transcript message by message.",
}


def kb_section():
    """Allow users to upload, index, and clear support documents."""
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

    if col_ingest.button(
        "Ingest PDFs",
        use_container_width=True,
        type="primary",
    ):
        if not files:
            st.error("Please select at least one PDF file before ingesting.")
        else:
            with st.spinner("Chunking and indexing..."):
                result = rag_stub.ingest_pdfs(files)

            for error in result["errors"]:
                st.error(error)

            if result["added"]:
                st.success(
                    f"{result['added']} chunks stored from "
                    f"{len(result['files'])} file(s) - "
                    f"{result['total']} total in knowledge base."
                )

    if col_clear.button("Clear Knowledge Base", use_container_width=True):
        rag_stub.clear()
        st.info("Knowledge base cleared.")

    # Show the current knowledge-base status.
    knowledge_base = rag_stub.stats()

    if knowledge_base["total"]:
        files_str = ", ".join(knowledge_base["files"])
        st.caption(
            f"{knowledge_base['total']} chunks indexed: {files_str}"
        )
    else:
        st.caption(
            "Knowledge base is empty. Upload PDFs above to enable retrieval."
        )


def render():
    """Render the setup page and start a coaching session."""
    session = st.session_state

    st.markdown(
        "<h1>AI Customer Support Coaching Assistant</h1>"
        '<p class="page-subtitle">'
        "Practice real support conversations with AI feedback and company knowledge."
        "</p>",
        unsafe_allow_html=True,
    )

    if session.get("restored"):
        st.success(
            "Session restored. Use the sidebar to switch sessions "
            "or fill in the form below to start a new one."
        )
        session.restored = False

    # Knowledge-base upload card.
    with st.container(border=True):
        kb_section()

    st.write("")

    # Session configuration card.
    with st.container(border=True):
        st.markdown(
            '<p class="section-heading">Session Setup</p>',
            unsafe_allow_html=True,
        )

        mode = st.radio(
            "Interaction Mode",
            MODES,
            horizontal=True,
            key="f_mode",
        )
        st.caption(MODE_INFO[mode])

        st.write("")

        col_product, col_scenario = st.columns([1, 1], gap="medium")

        product = col_product.text_input(
            "Product Context",
            key="f_product",
            placeholder="e.g. Acme Wireless Router X200",
        )
        scenario = col_scenario.text_area(
            "Customer Scenario",
            key="f_scenario",
            height=100,
            placeholder="e.g. Customer was charged twice and wants a refund.",
        )

        # Show controls that apply to the selected mode.
        persona, max_turns, script = "Calm", 5, []

        if mode == "Simulator":
            col_persona, col_turns = st.columns([1, 1], gap="medium")
            persona = col_persona.selectbox(
                "Customer Persona",
                ["Calm", "Impatient", "Angry", "Confused"],
                key="f_persona",
            )
            max_turns = col_turns.slider(
                "Number of Customer Turns",
                3,
                8,
                5,
                key="f_turns",
            )

        elif mode == "Replay":
            source = st.radio(
                "Transcript source",
                ["Bundled sample", "Upload .txt"],
                horizontal=True,
                key="f_src",
            )

            raw_transcript = SAMPLE_TRANSCRIPT

            if source == "Upload .txt":
                uploaded_transcript = st.file_uploader(
                    "Transcript file (.txt with lines like 'Customer: ...' / 'Agent: ...')",
                    type=["txt"],
                    key="f_tx",
                )
                raw_transcript = (
                    uploaded_transcript.getvalue().decode(
                        "utf-8", errors="ignore"
                    )
                    if uploaded_transcript
                    else ""
                )

            script = parse_transcript(raw_transcript)

            if script:
                st.caption(
                    f"Parsed {len(script)} messages from transcript."
                )

        elif mode == "Manual":
            st.caption(
                "You will paste each customer message inside the coaching console."
            )

        st.write("")

        if st.button(
            "Start coaching session",
            type="primary",
            use_container_width=True,
        ):
            errors = validate_setup(mode, product, scenario, script)

            if errors:
                st.error(
                    "Please fix the following before starting:\n\n"
                    + "\n".join(f"- {error}" for error in errors)
                )
            else:
                session.sid = storage.new_id()
                st.query_params["sid"] = session.sid
                session.config = {
                    "mode": mode,
                    "product": product.strip(),
                    "scenario": scenario.strip(),
                    "persona": persona,
                    "max_turns": max_turns,
                    "replay_script": script,
                }
                session.messages = []
                session.analyses = []
                session.tone = []
                session.replay_idx = 0
                session.view = "console"
                storage.save(session)
                st.rerun()
