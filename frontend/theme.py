"""Centralized theme and pastel glass-card styling for the Support Coach application."""

import streamlit as st


PAGE_THEMES = {
    "Dashboard": {
        "accent": "#C2347A",
        "tint": "#FDE7F1",
        "hover_tint": "#FFF0F6",
        "tab_active_bg": "#FDE7F1",
        "select_bg": "#FFF5F9",
        "border": "#F1E4EE",
        "brand_color": "#C2347A",
        "badge_color": "#A61E63",
    },
    "Sessions": {
        "accent": "#6D5BD0",
        "tint": "#ECE8FB",
        "hover_tint": "#F3F1FD",
        "tab_active_bg": "#ECE8FB",
        "select_bg": "#F5F3FD",
        "border": "#E2DEFA",
        "brand_color": "#6D5BD0",
        "badge_color": "#5844B8",
    },
    "Architecture": {
        "accent": "#0E7A6D",
        "tint": "#DDF5F1",
        "hover_tint": "#EDFAF7",
        "tab_active_bg": "#DDF5F1",
        "select_bg": "#F0FBF9",
        "border": "#CDEFEA",
        "brand_color": "#0E7A6D",
        "badge_color": "#0E7A6D",
    },
}


def apply_theme(page_title: str = "Dashboard") -> None:
    """Inject centralized CSS styling for the application based on the active page."""
    theme = PAGE_THEMES.get(page_title, PAGE_THEMES["Dashboard"])
    accent = theme["accent"]
    tint = theme["tint"]
    hover_tint = theme["hover_tint"]
    tab_active_bg = theme["tab_active_bg"]
    select_bg = theme["select_bg"]
    border = theme["border"]
    brand_color = theme["brand_color"]
    badge_color = theme.get("badge_color", accent)

    css = f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    /* ── Base Font & Reset: Inter with system sans fallback ── */
    html, body, [class*="css"], [data-testid="stMarkdownContainer"] p, .stMarkdown {{
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif !important;
        font-size: 14px !important;
        color: #2B2433 !important;
    }}

    /* ── Field labels: 13px / 500 weight ── */
    label, [data-testid="stWidgetLabel"] p {{
        font-size: 13px !important;
        font-weight: 500 !important;
        color: #2B2433 !important;
        margin-bottom: 2px !important;
    }}

    /* ── Transparent header bar — keep it visible so sidebar toggle is reachable ── */
    header[data-testid="stHeader"] {{
        background: transparent !important;
        border-bottom: none !important;
        box-shadow: none !important;
        height: 2.5rem !important;
        z-index: 999 !important;
    }}
    [data-testid="stToolbar"] {{
        background: transparent !important;
        display: flex !important;
        visibility: visible !important;
    }}
    [data-testid="stAppDeployButton"],
    [data-testid="stToolbarActions"],
    [data-testid="stDecoration"],
    [data-testid="stStatusWidget"],
    [data-testid="stMainMenu"],
    [data-testid="stMainMenuButton"],
    #MainMenu,
    footer {{
        display: none !important;
        visibility: hidden !important;
    }}

    /* ── Sidebar collapse / expand toggle button: always visible and clearly clickable ── */
    [data-testid="stExpandSidebarButton"],
    [data-testid="stBaseButton-headerNoPadding"],
    [data-testid="stSidebarCollapsedControl"],
    [data-testid="stSidebarCollapseButton"],
    button[aria-label="Expand sidebar"],
    button[aria-label="Collapse sidebar"],
    button[kind="headerNoPadding"] {{
        display: inline-flex !important;
        visibility: visible !important;
        opacity: 1 !important;
        pointer-events: auto !important;
        z-index: 99999 !important;
        color: #2B2433 !important;
        border-radius: 8px !important;
        transition: all 0.15s ease !important;
    }}
    [data-testid="stExpandSidebarButton"] {{
        background: rgba(255, 255, 255, 0.95) !important;
        border: 1px solid #E6D8E2 !important;
        box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08) !important;
        padding: 4px !important;
        color: {accent} !important;
    }}
    [data-testid="stExpandSidebarButton"]:hover {{
        background: {hover_tint} !important;
        border-color: {accent} !important;
    }}

    /* ── App background gradient ── */
    .stApp {{
        background: linear-gradient(135deg, #FFF9FC 0%, {tint} 100%) !important;
        background-attachment: fixed !important;
    }}

    /* ── Main block container: comfortable top padding clearing header ── */
    .block-container {{
        padding-top: 2.2rem !important;
        padding-bottom: 0.4rem !important;
        padding-left: 1.5rem !important;
        padding-right: 1.5rem !important;
        max-width: 1440px !important;
    }}

    /* ── Sidebar ── */
    [data-testid="stSidebar"] {{
        background: rgba(255, 255, 255, 0.90) !important;
        backdrop-filter: blur(14px) !important;
        border-right: 1px solid {border} !important;
    }}
    [data-testid="stSidebar"] > div:first-child {{
        padding-top: 1rem !important;
        padding-left: 0.85rem !important;
        padding-right: 0.85rem !important;
    }}

    .sb-brand {{
        font-size: 1.15rem;
        font-weight: 700;
        color: {brand_color};
        letter-spacing: -0.02em;
        margin-bottom: 0.1rem;
        display: flex;
        align-items: center;
        gap: 7px;
    }}
    .sb-tagline {{
        font-size: 0.72rem;
        color: #6B6475;
        margin-bottom: 0.8rem;
        padding-bottom: 0.5rem;
        border-bottom: 1px solid {border};
    }}
    .sb-section-label {{
        font-size: 0.65rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: #8C8496;
        margin-top: 0.6rem;
        margin-bottom: 8px !important;
    }}

    /* ── Sidebar nav items: 8px gap ── */
    [data-testid="stSidebar"] [data-testid="stPageLink-NavLink"] {{
        border-radius: 9px !important;
        padding: 0.35rem 0.65rem !important;
        font-size: 0.86rem !important;
        font-weight: 500 !important;
        color: #2B2433 !important;
        transition: all 0.15s ease !important;
        margin-bottom: 8px !important;
        display: flex !important;
        align-items: center !important;
        gap: 8px !important;
    }}
    [data-testid="stSidebar"] [data-testid="stPageLink-NavLink"]:hover {{
        background-color: {hover_tint} !important;
        color: {accent} !important;
    }}
    [data-testid="stSidebar"] [data-testid="stPageLink-NavLink"][aria-current="page"] {{
        background: {tint} !important;
        color: {accent} !important;
        font-weight: 700 !important;
        box-shadow: 0 1px 4px rgba(0,0,0,0.04) !important;
    }}

    .sb-session-row {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 3px 5px;
        border-radius: 6px;
        font-size: 0.76rem;
        color: #3A3344;
        margin-bottom: 4px;
    }}
    .sb-session-row:hover {{ background: {hover_tint}; }}
    .sb-mode-badge {{
        font-size: 0.64rem;
        font-weight: 600;
        padding: 1px 6px;
        border-radius: 4px;
        background: {tint};
        color: {badge_color};
        white-space: nowrap;
    }}

    /* ── Header Row: 24px/600 ── */
    .app-header-row {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 12px;
        height: 36px;
    }}
    .app-title {{
        font-size: 24px !important;
        font-weight: 600 !important;
        color: #2B2433 !important;
        letter-spacing: -0.02em;
        line-height: 1.2;
    }}
    .status-pill {{
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 4px 10px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: 600;
    }}
    .status-pill.ready {{
        background: #DDF5F1;
        color: #0E7A6D;
        border: 1px solid #B8EADF;
    }}
    .status-pill.warn {{
        background: #FFE9DC;
        color: #9C3E08;
        border: 1px solid #FFD3BA;
    }}

    /* ── Stat Cards: 76px height, 12px padding, 24px/600 number, 11px uppercase label ── */
    .stat-card-row {{
        display: flex;
        gap: 12px;
        margin-bottom: 12px;
    }}
    .stat-card {{
        flex: 1;
        border-radius: 14px;
        padding: 12px !important;
        height: 76px !important;
        box-sizing: border-box !important;
        border: 1px solid rgba(255,255,255,0.6);
        box-shadow: 0 4px 20px rgba(80,50,90,0.05);
        display: flex;
        flex-direction: column;
        justify-content: center;
    }}
    .stat-val {{
        font-size: 24px !important;
        font-weight: 600 !important;
        color: #2B2433 !important;
        line-height: 1 !important;
    }}
    .stat-val-text {{
        font-size: 16px !important;
        font-weight: 600 !important;
        color: #2B2433 !important;
        line-height: 1 !important;
    }}
    .stat-val-accuracy {{
        font-size: 18px !important;
        font-weight: 600 !important;
        color: #2B2433 !important;
        line-height: 1 !important;
        white-space: nowrap !important;
    }}
    .stat-lbl {{
        font-size: 11px !important;
        font-weight: 600 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.05em !important;
        color: #6B6475 !important;
        margin-top: 4px !important;
    }}

    /* ── Card Containers: 14px radius, 16px padding, 1px #F1E4EE, shadow ── */
    [data-testid="stVerticalBlockBorderWrapper"],
    .glass-card {{
        background: rgba(255, 255, 255, 0.85) !important;
        border: 1px solid #F1E4EE !important;
        border-radius: 14px !important;
        box-shadow: 0 4px 20px rgba(80,50,90,0.06) !important;
        backdrop-filter: blur(10px) !important;
        padding: 16px !important;
    }}

    .card-title-16 {{
        font-size: 16px !important;
        font-weight: 600 !important;
        color: #2B2433 !important;
        margin-bottom: 8px !important;
    }}

    /* ── Tabs ── */
    [data-testid="stTabs"] [data-baseweb="tab-list"],
    [data-testid="stTabs"] [role="tablist"] {{
        gap: 3px !important;
        border-bottom: 2px solid {border} !important;
    }}
    [data-testid="stTabs"] [data-baseweb="tab"],
    [data-testid="stTab"] {{
        font-size: 13px !important;
        font-weight: 500 !important;
        padding: 0.28rem 0.65rem !important;
        border-radius: 7px 7px 0 0 !important;
        color: #6B6475 !important;
        background: transparent !important;
        border-bottom: 2px solid transparent !important;
        margin-bottom: -2px !important;
    }}
    [data-testid="stTabs"] [aria-selected="true"][data-baseweb="tab"],
    [data-testid="stTab"][aria-selected="true"] {{
        background: {tab_active_bg} !important;
        color: {accent} !important;
        font-weight: 600 !important;
        border-bottom: 2px solid {accent} !important;
    }}
    [data-testid="stTabs"] [data-baseweb="tab"]:hover,
    [data-testid="stTab"]:hover {{
        background: {hover_tint} !important;
        color: {accent} !important;
    }}

    /* ── Expanders ── */
    [data-testid="stExpander"] {{
        border: 1px solid {border} !important;
        border-radius: 10px !important;
        background: #FFFFFF !important;
        margin-top: 0.25rem !important;
    }}
    [data-testid="stExpander"] summary:hover {{
        background: {hover_tint} !important;
        border-radius: 10px !important;
    }}

    /* ── Selectbox ── */
    [data-testid="stSelectbox"] > div > div {{
        border: 1px solid #E6D8E2 !important;
        border-radius: 9px !important;
        background: {select_bg} !important;
        font-size: 13px !important;
    }}
    [data-testid="stSelectbox"] > div > div:focus-within {{
        border-color: {accent} !important;
        box-shadow: 0 0 0 2px {tint} !important;
    }}

    /* ── Segmented Control / Radio ── */
    [data-testid="stSegmentedControl"] [data-baseweb="button-group"] {{
        border-radius: 9px !important;
        overflow: hidden !important;
    }}
    [data-testid="stSegmentedControl"] button[aria-checked="true"],
    button[data-variant="segmented_control"][aria-checked="true"],
    button[data-variant="segmented_control"][aria-selected="true"],
    button[data-variant="segmented_control"][data-selected="true"] {{
        background-color: {accent} !important;
        color: #FFFFFF !important;
    }}
    button[data-variant="segmented_control"][aria-checked="true"] *,
    button[data-variant="segmented_control"][aria-selected="true"] *,
    button[data-variant="segmented_control"][data-selected="true"] * {{
        color: #FFFFFF !important;
    }}

    /* ── Table & DataFrame ── */
    [data-testid="stTable"] th,
    [data-testid="stDataFrame"] th,
    .dvn-scroller thead th {{
        background: {tab_active_bg} !important;
        color: {accent} !important;
        font-weight: 600 !important;
        font-size: 12px !important;
    }}
    [data-testid="stTable"],
    [data-testid="stDataFrame"] {{
        border-radius: 10px !important;
        overflow: hidden !important;
        font-size: 13px !important;
    }}

    /* ── Buttons ── */
    .stButton > button[kind="primary"],
    button[kind="primary"] {{
        background-color: {accent} !important;
        border: none !important;
        color: #FFFFFF !important;
        font-weight: 600 !important;
        border-radius: 9px !important;
        padding: 0.38rem 0.9rem !important;
        font-size: 13px !important;
        box-shadow: 0 2px 7px rgba(0,0,0,0.08) !important;
        transition: opacity 0.15s, transform 0.1s !important;
    }}
    .stButton > button[kind="primary"] *,
    button[kind="primary"] * {{
        color: #FFFFFF !important;
        font-weight: 600 !important;
    }}
    .stButton > button[kind="primary"]:hover,
    button[kind="primary"]:hover {{
        opacity: 0.9 !important;
        transform: translateY(-1px) !important;
    }}
    .stButton > button[kind="primary"]:disabled,
    button[kind="primary"]:disabled {{
        opacity: 0.45 !important;
        cursor: not-allowed !important;
        transform: none !important;
    }}
    .stButton > button:not([kind="primary"]) {{
        background-color: #FFFFFF !important;
        border: 1px solid #E6D8E2 !important;
        color: #2B2433 !important;
        font-weight: 500 !important;
        border-radius: 9px !important;
        font-size: 13px !important;
    }}
    .stButton > button:not([kind="primary"]):hover {{
        border-color: {accent} !important;
        color: {accent} !important;
        background-color: {tint} !important;
    }}

    /* ── Inputs & Textareas ── */
    [data-testid="stTextInput"] input,
    [data-testid="stTextArea"] textarea {{
        border: 1px solid #E6D8E2 !important;
        border-radius: 9px !important;
        background: #FFFFFF !important;
        color: #2B2433 !important;
        font-size: 13px !important;
    }}
    [data-testid="stTextArea"] textarea {{
        min-height: 96px !important;
        height: 96px !important;
    }}
    [data-testid="stTextInput"] input:focus,
    [data-testid="stTextArea"] textarea:focus {{
        border-color: {accent} !important;
        box-shadow: 0 0 0 2px {tint} !important;
    }}

    /* ── Two-card heights & inner scroll control ── */
    [data-testid="column"]:nth-child(1) [data-testid="stVerticalBlockBorderWrapper"] > div {{
        overflow-y: auto !important;
    }}
    [data-testid="column"]:nth-child(2) [data-testid="stVerticalBlockBorderWrapper"],
    [data-testid="column"]:nth-child(2) [data-testid="stVerticalBlockBorderWrapper"] > div {{
        overflow-y: hidden !important;
    }}

    /* ── Compact File Uploader ── */
    [data-testid="stFileUploader"] {{
        padding: 0 !important;
    }}
    [data-testid="stFileUploaderDropzone"] {{
        padding: 0.6rem !important;
        min-height: 80px !important;
    }}

    /* ── Disabled button helper text: 12px grey ── */
    .btn-disabled-note {{
        font-size: 12px !important;
        color: #8C8496 !important;
        text-align: center;
        margin-top: 4px;
    }}

    /* ── Character counter (only when close to limit) ── */
    .counter-warning {{
        font-size: 11px;
        color: #B5541B;
        text-align: right;
        margin-top: -2px;
    }}

    /* ── Search Results Compact Rows ── */
    .search-result-row {{
        border-left: 3px solid {accent};
        background: rgba(255,255,255,0.7);
        border-radius: 0 8px 8px 0;
        padding: 5px 8px;
        margin-bottom: 5px;
    }}
    .score-bar-bg {{
        background: #EAE8EE;
        border-radius: 3px;
        height: 4px;
        width: 100%;
        margin: 3px 0;
    }}
    .score-bar-fill {{
        background: {accent};
        border-radius: 3px;
        height: 4px;
    }}

    /* ── Footer: 12px muted line ── */
    .app-footer {{
        font-size: 12px !important;
        color: #8C8496 !important;
        margin-top: 12px;
        margin-bottom: 6px;
    }}

    /* ── Spacing reductions ── */
    [data-testid="stVerticalBlock"] {{
        gap: 0.35rem !important;
    }}
    .main > [data-testid="stVerticalBlock"] {{
        gap: 0.5rem !important;
    }}
    [data-testid="column"] {{
        padding-left: 0.35rem !important;
        padding-right: 0.35rem !important;
    }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)
