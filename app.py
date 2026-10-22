"""AI Customer Support Coaching Assistant — Streamlit frontend.

Run from the project root:
    py -3 -m streamlit run app.py

Developed as a team project for Infosys Springboard Virtual Internship 7.0.
Frontend by Member 2. Orchestrator integration by Member 4.
"""
import streamlit as st

from utils import storage
from views import console, report, setup

st.set_page_config(
    page_title="Support Coach",
    page_icon="SC",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Design system
#
# Reference: warm dashboard with coral outer background, white workspace card.
#
# Palette:
#   Outer background   #FF5841  sunset coral  (page shell around workspace)
#   Workspace / cards  #FFFFFF  white
#   Primary actions    #C53678  red-violet    (buttons, active nav)
#   Accent highlights  #FF5841  sunset orange (progress bars, badges)
#   Headings / text    #000000  black
#   Secondary text     #666666  muted gray
#   Borders            #E8E8E8  light gray
#   Hover surface      #FFF0F4  very pale pink
#   Selected nav bg    #FFF0F4  very pale pink
# ---------------------------------------------------------------------------
st.markdown("""
<style>
/* ══════════════════════════════════════════════════════
   1. CORAL PAGE SHELL
   The entire page gets a coral background.
   The white workspace (stMain) sits on top of it.
   ══════════════════════════════════════════════════════ */

/* Coral fills the whole browser viewport */
html,
body {
    background-color: #FF5841 !important;
    margin: 0;
    padding: 0;
}

/* stAppViewContainer is the flex container holding sidebar + main */
[data-testid="stAppViewContainer"] {
    background-color: #FF5841 !important;
    min-height: 100vh;
}

/* ══════════════════════════════════════════════════════
   2. WHITE WORKSPACE  (stMain)
   stMain wraps the header strip AND the block container.
   Give it a white background, rounded corners, subtle shadow.
   Add a right margin so coral peeks out on the right side.
   ══════════════════════════════════════════════════════ */
[data-testid="stMain"] {
    background-color: #FFFFFF !important;
    border-radius: 20px !important;
    box-shadow: 0 4px 24px rgba(0, 0, 0, 0.12) !important;
    /* top/bottom margin = coral gutter; right margin lets coral show */
    margin: 14px 18px 14px 0 !important;
    overflow: hidden !important;
}

/* The header strip inside stMain must also be white */
[data-testid="stHeader"] {
    background-color: #FFFFFF !important;
}

/* Block container: the actual content area */
[data-testid="stMainBlockContainer"],
.block-container {
    padding: 1.75rem 2.25rem 2rem 2.25rem !important;
    max-width: 1280px !important;
    background-color: #FFFFFF !important;
}

/* ══════════════════════════════════════════════════════
   3. SIDEBAR — white panel, compact, flush left
   ══════════════════════════════════════════════════════ */
[data-testid="stSidebar"] {
    background-color: #FFFFFF !important;
    border-right: 1px solid #EDEDED !important;
    /* No rounded corners on sidebar — it's flush left */
    border-radius: 0 !important;
}
[data-testid="stSidebar"] > div:first-child {
    padding-top: 1.25rem !important;
}

/* ── Brand ─────────────────────────────────── */
.sb-brand {
    font-size: 1.15rem;
    font-weight: 800;
    color: #C53678;
    letter-spacing: -0.3px;
    padding: 0 1.1rem 0.15rem 1.1rem;
    margin-bottom: 0;
    line-height: 1.2;
}
.sb-tagline {
    font-size: 0.7rem;
    color: #999999;
    padding: 0 1.1rem 1rem 1.1rem;
    border-bottom: 1px solid #F0F0F0;
    margin-bottom: 0.9rem;
    line-height: 1.4;
}

/* ── Section label ──────────────────────────── */
.sb-section-label {
    font-size: 0.66rem;
    font-weight: 700;
    letter-spacing: 0.09em;
    text-transform: uppercase;
    color: #BBBBBB;
    padding: 0 1.1rem 0.3rem 1.1rem;
    margin-top: 0.25rem;
}

/* ── Nav items ──────────────────────────────── */
.sb-nav-item {
    display: flex;
    align-items: center;
    gap: 9px;
    padding: 0.48rem 1.1rem;
    font-size: 0.875rem;
    font-weight: 500;
    color: #444444;
    border-radius: 8px;
    margin: 1px 0.5rem;
    cursor: default;
    user-select: none;
    transition: background 0.13s, color 0.13s;
}
.sb-nav-item:hover {
    background: #FFF0F4;
    color: #C53678;
}
.sb-nav-item.active {
    background: #FFF0F4;
    color: #C53678;
    font-weight: 700;
}
.sb-nav-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #DDDDDD;
    flex-shrink: 0;
}
.sb-nav-item.active .sb-nav-dot {
    background: #C53678;
}

/* ── Sidebar divider ────────────────────────── */
.sb-divider {
    border: none;
    border-top: 1px solid #F0F0F0;
    margin: 0.7rem 0.5rem;
}

/* ── Sidebar buttons (session load) ─────────── */
[data-testid="stSidebar"] .stButton > button {
    background: #FAFAFA !important;
    border: 1px solid #EEEEEE !important;
    border-radius: 7px !important;
    color: #444444 !important;
    font-size: 0.76rem !important;
    text-align: left !important;
    padding: 0.3rem 0.55rem !important;
    box-shadow: none !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
    border-color: #C53678 !important;
    color: #C53678 !important;
    background: #FFF0F4 !important;
}

/* ══════════════════════════════════════════════════════
   4. TYPOGRAPHY
   ══════════════════════════════════════════════════════ */
h1 {
    font-size: 1.6rem !important;
    font-weight: 800 !important;
    color: #000000 !important;
    margin-bottom: 0.1rem !important;
    letter-spacing: -0.4px;
    line-height: 1.2;
}
h2 {
    font-size: 1.1rem !important;
    font-weight: 700 !important;
    color: #000000 !important;
    margin-bottom: 0.2rem !important;
}
h3 {
    font-size: 0.95rem !important;
    font-weight: 600 !important;
    color: #000000 !important;
}

/* Page subtitle */
.page-subtitle {
    font-size: 0.88rem;
    color: #666666;
    margin-top: 0.1rem;
    margin-bottom: 1.4rem;
    line-height: 1.45;
}

/* Section card heading */
.section-heading {
    font-size: 0.97rem;
    font-weight: 700;
    color: #000000;
    margin-bottom: 0.1rem;
    line-height: 1.3;
}
.section-desc {
    font-size: 0.8rem;
    color: #777777;
    margin-bottom: 0.85rem;
    line-height: 1.45;
}

/* ══════════════════════════════════════════════════════
   5. CARDS  (st.container with border=True)
   ══════════════════════════════════════════════════════ */
[data-testid="stVerticalBlockBorderWrapper"] {
    border: 1px solid #EDEDED !important;
    border-radius: 14px !important;
    background: #FFFFFF !important;
    padding: 1.25rem 1.4rem !important;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05) !important;
}

/* ══════════════════════════════════════════════════════
   6. BUTTONS
   ══════════════════════════════════════════════════════ */

/* Primary (red-violet) */
.stButton > button[kind="primary"],
button[kind="primary"] {
    background-color: #C53678 !important;
    border-color: #C53678 !important;
    color: #FFFFFF !important;
    font-weight: 700 !important;
    border-radius: 9px !important;
    padding: 0.45rem 1.1rem !important;
    font-size: 0.88rem !important;
    box-shadow: 0 2px 6px rgba(197, 54, 120, 0.25) !important;
    transition: background 0.15s, box-shadow 0.15s;
}
.stButton > button[kind="primary"]:hover,
button[kind="primary"]:hover {
    background-color: #a8295e !important;
    border-color: #a8295e !important;
    box-shadow: 0 3px 10px rgba(197, 54, 120, 0.35) !important;
}

/* Secondary / default */
.stButton > button:not([kind="primary"]) {
    background-color: #FFFFFF !important;
    border: 1px solid #DDDDDD !important;
    color: #333333 !important;
    font-weight: 500 !important;
    border-radius: 9px !important;
    font-size: 0.86rem !important;
    box-shadow: none !important;
    transition: border-color 0.13s, color 0.13s, background 0.13s;
}
.stButton > button:not([kind="primary"]):hover {
    border-color: #C53678 !important;
    color: #C53678 !important;
    background-color: #FFF0F4 !important;
}

/* Form submit buttons */
.stFormSubmitButton > button {
    background-color: #FFFFFF !important;
    border: 1px solid #DDDDDD !important;
    color: #333333 !important;
    border-radius: 9px !important;
    font-weight: 500 !important;
    font-size: 0.86rem !important;
    box-shadow: none !important;
}
.stFormSubmitButton > button:hover {
    border-color: #C53678 !important;
    color: #C53678 !important;
    background-color: #FFF0F4 !important;
}

/* ══════════════════════════════════════════════════════
   7. FORM INPUTS
   ══════════════════════════════════════════════════════ */
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea {
    border: 1px solid #E2E2E2 !important;
    border-radius: 8px !important;
    background: #FAFAFA !important;
    color: #000000 !important;
    font-size: 0.88rem !important;
    transition: border-color 0.13s, box-shadow 0.13s;
}
[data-testid="stTextInput"] input:focus,
[data-testid="stTextArea"] textarea:focus {
    border-color: #C53678 !important;
    background: #FFFFFF !important;
    box-shadow: 0 0 0 2px rgba(197, 54, 120, 0.12) !important;
    outline: none !important;
}

/* Selectbox */
[data-testid="stSelectbox"] > div > div {
    border: 1px solid #E2E2E2 !important;
    border-radius: 8px !important;
    background: #FAFAFA !important;
}

/* ── File uploader ─────────────────────────────
   Remove the bright pink dashed border.
   Use a soft light-gray area instead.
   ─────────────────────────────────────────────── */
[data-testid="stFileUploader"] > section {
    border: 1.5px dashed #CCCCCC !important;
    border-radius: 10px !important;
    background: #FAFAFA !important;
    padding: 0.6rem !important;
    transition: border-color 0.13s, background 0.13s;
}
[data-testid="stFileUploader"] > section:hover {
    border-color: #C53678 !important;
    background: #FFF8FB !important;
}
/* Also target the outer wrapper in case Streamlit nests differently */
[data-testid="stFileUploader"] {
    border: none !important;
    background: transparent !important;
    padding: 0 !important;
}

/* ══════════════════════════════════════════════════════
   8. RADIO BUTTONS
   ══════════════════════════════════════════════════════ */
[data-testid="stRadio"] label {
    font-weight: 500 !important;
    color: #000000 !important;
    font-size: 0.88rem !important;
}

/* ══════════════════════════════════════════════════════
   9. PROGRESS BARS — sunset orange
   ══════════════════════════════════════════════════════ */
[data-testid="stProgress"] > div > div {
    background: linear-gradient(90deg, #FF5841, #ff7a5c) !important;
    border-radius: 4px !important;
}
[data-testid="stProgress"] > div {
    background: #F0F0F0 !important;
    border-radius: 4px !important;
}

/* ══════════════════════════════════════════════════════
   10. METRICS
   ══════════════════════════════════════════════════════ */
[data-testid="stMetricLabel"]  { color: #555555 !important; font-size: 0.78rem; font-weight: 600; }
[data-testid="stMetricValue"]  { color: #000000 !important; font-weight: 800; }
[data-testid="stMetricDelta"]  { color: #888888 !important; }

/* ══════════════════════════════════════════════════════
   11. ALERTS AND STATUS
   ══════════════════════════════════════════════════════ */
[data-testid="stAlert"] {
    border-radius: 9px !important;
}

/* ══════════════════════════════════════════════════════
   12. CAPTIONS
   ══════════════════════════════════════════════════════ */
.stCaption, [data-testid="stCaptionContainer"] {
    color: #777777 !important;
    font-size: 0.79rem !important;
}

/* ══════════════════════════════════════════════════════
   13. DIVIDERS
   ══════════════════════════════════════════════════════ */
hr {
    border: none !important;
    border-top: 1px solid #F0F0F0 !important;
    margin: 0.6rem 0 !important;
}

/* ══════════════════════════════════════════════════════
   14. BADGE HELPERS
   ══════════════════════════════════════════════════════ */

/* Orange score badge */
.badge-orange {
    display: inline-block;
    background: #FF5841;
    color: #FFFFFF;
    font-size: 0.7rem;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 20px;
    margin-left: 5px;
    vertical-align: middle;
}

/* KB chunk count pill */
.kb-status {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    background: #FFF0F4;
    border: 1px solid #F0C0D4;
    border-radius: 20px;
    padding: 3px 11px;
    font-size: 0.78rem;
    font-weight: 600;
    color: #C53678;
    margin-top: 5px;
}

/* ══════════════════════════════════════════════════════
   15. CHAT MESSAGES
   ══════════════════════════════════════════════════════ */
[data-testid="stChatMessage"] {
    border-radius: 10px !important;
    margin-bottom: 0.35rem !important;
}

/* ══════════════════════════════════════════════════════
   16. SLIDER
   ══════════════════════════════════════════════════════ */
[data-testid="stSlider"] [data-baseweb="slider"] [role="slider"] {
    background-color: #C53678 !important;
}

/* ══════════════════════════════════════════════════════
   17. RESPONSIVE ADJUSTMENTS
   ══════════════════════════════════════════════════════ */
@media (max-width: 900px) {
    [data-testid="stMain"] {
        margin: 8px 8px 8px 0 !important;
        border-radius: 14px !important;
    }
    .block-container,
    [data-testid="stMainBlockContainer"] {
        padding: 1.1rem 1rem !important;
    }
    h1 { font-size: 1.3rem !important; }
}
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Session bootstrap — restore from ?sid= URL param on first load
# ---------------------------------------------------------------------------
def bootstrap():
    """Load a saved session from the URL ?sid= parameter on first page load."""
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
    """Load a saved session by ID and update the URL."""
    data = storage.load(sid)
    if data:
        for k, v in data.items():
            st.session_state[k] = v
        st.session_state.sid = sid
        st.query_params["sid"] = sid


bootstrap()

# ---------------------------------------------------------------------------
# Sidebar — brand + navigation + saved sessions
# ---------------------------------------------------------------------------
with st.sidebar:

    # Brand
    st.markdown('<div class="sb-brand">Support Coach</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sb-tagline">AI coaching for support teams</div>',
        unsafe_allow_html=True,
    )

    # Active view for nav highlight
    current_view = st.session_state.get("view", "setup")

    # Navigation
    st.markdown('<div class="sb-section-label">Navigation</div>', unsafe_allow_html=True)

    dash_cls = "sb-nav-item active" if current_view == "setup" else "sb-nav-item"
    sess_cls = "sb-nav-item active" if current_view in ("console", "report") else "sb-nav-item"

    st.markdown(f"""
    <div class="{dash_cls}">
        <span class="sb-nav-dot"></span> Dashboard
    </div>
    <div class="{sess_cls}">
        <span class="sb-nav-dot"></span> Sessions
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<hr class="sb-divider">', unsafe_allow_html=True)

    # Saved sessions list
    st.markdown('<div class="sb-section-label">Saved Sessions</div>', unsafe_allow_html=True)
    rows = storage.list_sessions()

    if not rows:
        st.caption("No saved sessions yet.")

    for sid, ts, mode in rows:
        col1, col2 = st.columns([5, 1])
        with col1:
            if st.button(
                f"{mode}  {ts}",
                key=f"ld_{sid}",
                use_container_width=True,
            ):
                load_session(sid)
                st.rerun()
        with col2:
            if st.button("x", key=f"del_{sid}", help="Delete this session"):
                st.session_state["delete_session_id"] = sid

    delete_sid = st.session_state.get("delete_session_id")
    if delete_sid:
        st.warning(f"Delete session {delete_sid}?")
        col_yes, col_no = st.columns(2)
        with col_yes:
            if st.button("Yes", key="confirm_delete", type="primary"):
                deleted = storage.delete_session(delete_sid)
                st.success("Deleted.") if deleted else st.error("Could not delete.")
                st.session_state.pop("delete_session_id", None)
                st.rerun()
        with col_no:
            if st.button("Cancel", key="cancel_delete"):
                st.session_state.pop("delete_session_id", None)
                st.rerun()

    st.markdown('<hr class="sb-divider">', unsafe_allow_html=True)
    st.caption("Orchestrator: run_workflow()")
    st.caption("Store: data/sessions/")

# ---------------------------------------------------------------------------
# Route to the correct view
# ---------------------------------------------------------------------------
view = st.session_state.view
if view in ("console", "report") and not st.session_state.config:
    view = "setup"

{"setup": setup.render, "console": console.render, "report": report.render}[view]()
