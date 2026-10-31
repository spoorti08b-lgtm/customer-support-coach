"""AI Customer Support Coaching Assistant."""

from __future__ import annotations

import sys
from pathlib import Path

# Bootstrap repository root into sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st

from backend.services import rag_stub, storage
from frontend.theme import PAGE_THEMES, apply_theme
from frontend.views import architecture, sessions, setup

# Configure Streamlit page settings
st.set_page_config(
    page_title="Support Coach",
    page_icon="🎧",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Define application pages
page_dashboard = st.Page(
    setup.render,
    title="Dashboard",
    url_path="dashboard",
    default=True,
)
page_sessions = st.Page(
    sessions.render,
    title="Sessions",
    url_path="sessions",
)
page_architecture = st.Page(
    architecture.render,
    title="Architecture",
    url_path="architecture",
)

# Navigation with hidden native position for custom styled sidebar
nav = st.navigation(
    [page_dashboard, page_sessions, page_architecture],
    position="hidden",
)

# Centralized theme applied based on active page title
try:
    active_title = nav.title
except Exception:
    active_title = "Dashboard"

apply_theme(active_title)

# Active theme variables for sidebar accents
active_theme = PAGE_THEMES.get(active_title, PAGE_THEMES["Dashboard"])
brand_color = active_theme["brand_color"]

# Render Left Sidebar
with st.sidebar:
    st.markdown(
        f"""
        <div class="sb-brand" style="color: {brand_color};">
            <span>🎧</span> Support Coach
        </div>
        <div class="sb-tagline">AI coaching for support teams</div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="sb-section-label">Navigation</div>', unsafe_allow_html=True)
    st.page_link(page_dashboard, label="Dashboard", icon=":material/dashboard:")
    st.page_link(page_sessions, label="Sessions", icon=":material/list_alt:")
    st.page_link(page_architecture, label="Architecture", icon=":material/account_tree:")

    st.markdown(
        '<div class="sb-section-label" style="margin-top:0.75rem;">Recent Sessions</div>',
        unsafe_allow_html=True,
    )
    recent_sessions = storage.list_sessions(limit=5)
    if not recent_sessions:
        st.caption("No saved sessions yet.")
    else:
        for item in recent_sessions:
            sid, created_at, mode, product, persona, max_turns = item
            short_id = sid[:12] if len(sid) > 12 else sid
            mode_badge = mode[:3].upper() if mode else "SIM"
            st.markdown(
                f'<div class="sb-session-row">'
                f'<span style="font-family:monospace;font-size:0.75rem;font-weight:600;">{short_id}</span>'
                f'<span class="sb-mode-badge">{mode_badge}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

    st.markdown(
        f"""
        <div style="margin-top:1.2rem;padding-top:0.5rem;border-top:1px solid {active_theme['border']};">
            <div style="font-size:0.68rem;color:#8C8496;">Orchestrator: <code>run_workflow()</code></div>
            <div style="font-size:0.68rem;color:#8C8496;margin-top:2px;">Store: <code>data/sessions/</code></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Reset demo button with confirmation step
    st.markdown('<div style="height:8px;"></div>', unsafe_allow_html=True)
    if not st.session_state.get("confirm_reset_demo", False):
        if st.button("Reset demo", use_container_width=True, key="btn_reset_demo_init"):
            st.session_state["confirm_reset_demo"] = True
            st.rerun()
    else:
        st.markdown(
            '<div style="font-size:0.72rem;font-weight:600;color:#9C3E08;margin-bottom:4px;">'
            'Reset all sessions and reload sample KB?'
            '</div>',
            unsafe_allow_html=True,
        )
        col_c1, col_c2 = st.columns(2, gap="small")
        if col_c1.button("Confirm", type="primary", use_container_width=True, key="btn_confirm_reset_demo"):
            storage.delete_all_sessions()
            rag_stub.clear()
            rag_stub.load_sample_pdfs()
            st.session_state["confirm_reset_demo"] = False
            st.session_state["accuracy_card_val"] = "15/15 . 15/15"
            st.session_state["cached_eval_res"] = None
            st.session_state["field_product"] = ""
            st.session_state["field_problem"] = ""
            st.session_state["field_mood"] = "Calm"
            st.session_state["load_example_sel"] = "Choose..."
            st.toast("Demo reset: sessions cleared and sample KB reloaded", icon="🔄")
            st.rerun()
        if col_c2.button("Cancel", use_container_width=True, key="btn_cancel_reset_demo"):
            st.session_state["confirm_reset_demo"] = False
            st.rerun()

# Render active flash / toast notifications
if "flash" in st.session_state and st.session_state["flash"]:
    for flash_msg in st.session_state["flash"]:
        st.toast(flash_msg, icon="✅")
    st.session_state["flash"] = []

# Execute active view
nav.run()
