"""Setup page: KB ingestion (PDF -> 'X chunks stored'), mode selection, scenario, validation."""
import streamlit as st

from utils import rag_stub, storage
from utils.pipeline_stub import SAMPLE_TRANSCRIPT
from utils.validation import MODES, parse_transcript, validate_setup

MODE_INFO = {"Simulator": "🤖 AI customer sends messages turn by turn",
             "Manual": "✍️ You paste incoming customer messages",
             "Replay": "🎞️ Replay a transcript message by message"}


def kb_section():
    st.subheader("1 · Support knowledge base")
    st.caption("Upload FAQs, support docs and policy PDFs. They're chunked and indexed for retrieval.")
    files = st.file_uploader("Upload PDF(s)", type=["pdf"], accept_multiple_files=True, key="kb_files")
    c1, c2 = st.columns([2, 1])
    if c1.button("📥 Ingest PDFs", use_container_width=True):
        if not files:
            st.error("Please choose at least one PDF file first.")
        else:
            with st.spinner("Chunking and indexing…"):
                res = rag_stub.ingest_pdfs(files)
            for e in res["errors"]:
                st.error(e)
            if res["added"]:
                st.success(f"✅ {res['added']} chunks stored from {len(res['files'])} file(s) "
                           f"· {res['total']} total in knowledge base")
    if c2.button("🗑️ Clear KB", use_container_width=True):
        rag_stub.clear()
        st.info("Knowledge base cleared.")
    s = rag_stub.stats()
    if s["total"]:
        st.caption(f"📚 Indexed now: **{s['total']} chunks** · " + ", ".join(s["files"]))
    else:
        st.caption("📚 Knowledge base is empty.")


def render():
    s = st.session_state
    st.title("🎧 AI Customer Support Coaching Assistant")
    if s.get("restored"):
        st.success("Saved session reloaded after refresh. Use the sidebar to continue or start a new one.")
        s.restored = False

    with st.container(border=True):
        kb_section()

    with st.container(border=True):
        st.subheader("2 · Session setup")
        mode = st.radio("Interaction mode", MODES, horizontal=True, key="f_mode",
                        format_func=lambda m: f"{m}")
        st.caption(MODE_INFO[mode])
        product = st.text_input("Product context", key="f_product", placeholder="e.g. Acme Wireless Router X200")
        scenario = st.text_area("Customer scenario", key="f_scenario", height=100,
                                placeholder="e.g. Customer was charged twice and wants a refund.")
        persona, max_turns, script = "Calm", 5, []
        if mode == "Simulator":
            c1, c2 = st.columns(2)
            persona = c1.selectbox("Customer persona", ["Calm", "Impatient", "Angry", "Confused"], key="f_persona")
            max_turns = c2.slider("Number of customer turns", 3, 8, 5, key="f_turns")
        elif mode == "Replay":
            src = st.radio("Transcript source", ["Bundled sample", "Upload .txt"], horizontal=True, key="f_src")
            raw = SAMPLE_TRANSCRIPT
            if src == "Upload .txt":
                up = st.file_uploader("Transcript (.txt, lines like 'Customer: …' / 'Agent: …')",
                                      type=["txt"], key="f_tx")
                raw = up.getvalue().decode("utf-8", errors="ignore") if up else ""
            script = parse_transcript(raw)
            if script:
                st.caption(f"Parsed {len(script)} messages.")
        elif mode == "Manual":
            st.caption("You'll paste each customer message in the console.")

        if st.button("🚀 Start coaching session", type="primary", use_container_width=True):
            errs = validate_setup(mode, product, scenario, script)
            if errs:
                st.error("Please fix the following:\n\n" + "\n".join(f"- {e}" for e in errs))
            else:
                s.sid = storage.new_id()
                st.query_params["sid"] = s.sid
                s.config = {"mode": mode, "product": product.strip(), "scenario": scenario.strip(),
                            "persona": persona, "max_turns": max_turns, "replay_script": script}
                s.messages, s.analyses, s.tone, s.replay_idx = [], [], [], 0
                s.view = "console"
                storage.save(s)
                st.rerun()
