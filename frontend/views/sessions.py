"""Sessions view for viewing, inspecting, and managing saved coaching sessions."""

from __future__ import annotations

import json
from datetime import datetime
import pandas as pd
import streamlit as st

from backend.services import storage


def _format_created(ts_str: str) -> str:
    """Format an ISO timestamp to '23 Oct, 12:48'."""
    try:
        dt = datetime.fromisoformat(str(ts_str))
        return dt.strftime("%d %b, %H:%M")
    except Exception:
        return str(ts_str)[:16]


def render() -> None:
    """Render the Sessions management page in lavender theme."""
    # 16px top padding
    st.markdown('<div style="height: 16px;"></div>', unsafe_allow_html=True)
    st.markdown("<h1>Saved Sessions</h1>", unsafe_allow_html=True)

    all_sessions = storage.list_sessions()

    # Metric row: Total, Simulator, Manual, Replay counts
    total_count = len(all_sessions)
    sim_count = sum(1 for _, _, m, _, _, _ in all_sessions if m.capitalize() == "Simulator")
    man_count = sum(1 for _, _, m, _, _, _ in all_sessions if m.capitalize() == "Manual")
    rep_count = sum(1 for _, _, m, _, _, _ in all_sessions if m.capitalize() == "Replay")

    c1, c2, c3, c4 = st.columns(4, gap="small")
    with c1:
        st.markdown(
            f"""
            <div class="stat-card" style="background:#ECE8FB;height:68px;">
                <div class="stat-val" style="color:#6D5BD0;">{total_count}</div>
                <div class="stat-lbl" style="color:#6D5BD0;">Total Sessions</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f"""
            <div class="stat-card" style="background:#ECE8FB;height:68px;">
                <div class="stat-val" style="color:#6D5BD0;">{sim_count}</div>
                <div class="stat-lbl" style="color:#6D5BD0;">Simulator</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            f"""
            <div class="stat-card" style="background:#ECE8FB;height:68px;">
                <div class="stat-val" style="color:#6D5BD0;">{man_count}</div>
                <div class="stat-lbl" style="color:#6D5BD0;">Manual</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c4:
        st.markdown(
            f"""
            <div class="stat-card" style="background:#ECE8FB;height:68px;">
                <div class="stat-val" style="color:#6D5BD0;">{rep_count}</div>
                <div class="stat-lbl" style="color:#6D5BD0;">Replay</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.write("")

    if not all_sessions:
        with st.container(border=True):
            st.write("No saved sessions yet.")
        return

    # Table: Session, Mode, Product, Persona, Turns, Created
    table_rows = []
    for sid, created_at, mode, product, persona, max_turns in all_sessions:
        table_rows.append({
            "Session": sid,
            "Mode": mode,
            "Product": product,
            "Persona": persona if persona else "—",
            "Turns": max_turns if max_turns else "—",
            "Created": _format_created(created_at),
        })

    df_sessions = pd.DataFrame(table_rows)
    st.dataframe(df_sessions, use_container_width=True, hide_index=True)

    st.write("")

    # Detail card
    with st.container(border=True):
        st.markdown('<div class="card-title-16" style="color:#6D5BD0;">Session Detail</div>', unsafe_allow_html=True)

        session_ids = [sid for sid, _, _, _, _, _ in all_sessions]
        selected_sid = st.selectbox(
            "Select session",
            options=session_ids,
            key="sessions_picker",
            label_visibility="collapsed",
        )

        session_data = storage.load(selected_sid) if selected_sid else None

        if session_data:
            col_left, col_right = st.columns([1, 1], gap="medium")

            mode = session_data.get("mode", "Simulator")
            product = session_data.get("product", "—")
            scenario = session_data.get("scenario", "")
            persona = session_data.get("persona") or "—"
            max_turns = session_data.get("max_turns") or "—"
            status = session_data.get("status", "configured")
            created_fmt = _format_created(session_data.get("created_at", ""))
            kb_docs = session_data.get("kb_documents") or []

            with col_left:
                st.markdown(
                    f'<div style="margin-bottom:6px;">'
                    f'<span style="font-weight:600;font-size:1.05rem;color:#2B2433;">{session_data["session_id"]}</span> '
                    f'<span class="sb-mode-badge" style="background:#ECE8FB;color:#6D5BD0;font-size:0.75rem;padding:2px 8px;border-radius:6px;font-weight:600;">{mode}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                st.markdown(f"**Product:** {product}")
                if scenario:
                    st.markdown(
                        f'<div style="background:#F7F6FC;border-left:3px solid #6D5BD0;padding:8px 12px;border-radius:0 8px 8px 0;margin:6px 0;font-style:italic;font-size:0.86rem;">'
                        f'"{scenario}"'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

            with col_right:
                st.markdown(f"**Persona:** `{persona}` · **Turns:** `{max_turns}`")
                st.markdown(f"**Status:** `{status}` · **Created:** {created_fmt}")

                if kb_docs:
                    chips_html = " ".join(
                        f'<span style="display:inline-block;background:#ECE8FB;color:#6D5BD0;padding:2px 7px;border-radius:6px;font-size:0.75rem;margin:2px 4px 2px 0;">📄 {doc}</span>'
                        for doc in kb_docs
                    )
                    st.markdown(f"**KB Documents:** {chips_html}", unsafe_allow_html=True)
                else:
                    st.markdown("**KB Documents:** None linked at start")

            # Raw JSON in collapsed expander
            with st.expander("Raw JSON", expanded=False):
                st.json(session_data)

            # Row for Download JSON and Delete buttons
            col_dl, col_del, col_space = st.columns([1, 1, 2], gap="small")

            with col_dl:
                json_str = json.dumps(session_data, indent=2)
                st.download_button(
                    label="Download JSON",
                    data=json_str,
                    file_name=f"{selected_sid}.json",
                    mime="application/json",
                    use_container_width=True,
                    key=f"btn_dl_{selected_sid}",
                )

            with col_del:
                confirm_key = f"confirm_del_state_{selected_sid}"
                is_confirming = st.session_state.get(confirm_key, False)

                if not is_confirming:
                    if st.button("Delete", key=f"btn_del_init_{selected_sid}", use_container_width=True):
                        st.session_state[confirm_key] = True
                        st.rerun()
                else:
                    col_yes, col_no = st.columns(2, gap="small")
                    if col_yes.button("Confirm", type="primary", use_container_width=True, key=f"btn_del_confirm_{selected_sid}"):
                        storage.delete_session(selected_sid)
                        st.session_state[confirm_key] = False
                        st.toast(f"Session {selected_sid} deleted", icon="🗑️")
                        st.rerun()
                    if col_no.button("Cancel", use_container_width=True, key=f"btn_del_cancel_{selected_sid}"):
                        st.session_state[confirm_key] = False
                        st.rerun()
