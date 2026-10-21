"""AI Customer Support Coaching Assistant — Streamlit frontend. Run: streamlit run app.py"""
import streamlit as st

from utils import storage
from views import console, report, setup

st.set_page_config(page_title="Support Coaching Assistant", page_icon="🎧",
                   layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
.block-container{padding-top:1.5rem;max-width:1500px}
@media (max-width:768px){
  .block-container{padding:3.2rem .7rem 1rem}
  h1{font-size:1.45rem!important} h2,h3{font-size:1.15rem!important}
  [data-testid="stMetricValue"]{font-size:1.2rem}
}
</style>""", unsafe_allow_html=True)


def bootstrap():
    s = st.session_state
    if s.get("_ready"):
        return
    sid = st.query_params.get("sid")
    data = storage.load(sid)
    s.sid = sid if data else None
    for k, v in (data or storage.DEFAULTS).items():
        s[k] = v
    s.restored = bool(data)
    s._ready = True


def load_session(sid):
    data = storage.load(sid)
    if data:
        for k, v in data.items():
            st.session_state[k] = v
        st.session_state.sid = sid
        st.query_params["sid"] = sid


bootstrap()


with st.sidebar:
    st.header("💾 Saved sessions")

    rows = storage.list_sessions()

    if not rows:
        st.caption("No saved sessions yet.")

    for sid, ts, mode in rows:
        col1, col2 = st.columns([5, 1])

        with col1:
            if st.button(
                f"{mode} · {ts} · {sid}",
                key=f"ld_{sid}",
                use_container_width=True
            ):
                load_session(sid)
                st.rerun()

        with col2:
            if st.button("🗑️", key=f"del_{sid}", help="Delete this session"):
                st.session_state["delete_session_id"] = sid

    # Confirm deletion before removing the file
    delete_sid = st.session_state.get("delete_session_id")

    if delete_sid:
        st.warning(f"Are you sure you want to delete session {delete_sid}?")

        col_yes, col_no = st.columns(2)

        with col_yes:
            if st.button("Yes, delete", key="confirm_delete", type="primary"):
                deleted = storage.delete_session(delete_sid)

                if deleted:
                    st.success("Session deleted successfully.")
                else:
                    st.error("Could not delete the session.")

                st.session_state.pop("delete_session_id", None)
                st.rerun()

        with col_no:
            if st.button("Cancel", key="cancel_delete"):
                st.session_state.pop("delete_session_id", None)
                st.rerun()


view = st.session_state.view
if view in ("console", "report") and not st.session_state.config:
    view = "setup"
{"setup": setup.render, "console": console.render, "report": report.render}[view]()
