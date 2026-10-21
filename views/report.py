"""Post-interaction report (frontend placeholder until the Summary Agent is plugged in)."""
import streamlit as st

from utils import storage


def render():
    s = st.session_state
    st.title("📊 Post-Interaction Report")
    an = s.analyses
    if not an:
        st.info("No customer messages were analysed in this session.")
    else:
        fr = [a["frustration"] for a in an]
        peak = max(a["risk"] for a in an)
        tone = [t["score"] for t in s.tone] or [0]
        quality = int(max(0, min(100, 100 - fr[-1] * 0.5 - peak * 0.2 + sum(tone) / len(tone) * 0.2)))
        c1, c2, c3 = st.columns(3)
        c1.metric("Resolution quality", f"{quality}/100")
        c2.metric("Peak escalation risk", f"{peak}%")
        c3.metric("Customer turns", len(an))
        st.subheader("Sentiment journey")
        st.line_chart({"Frustration %": fr, "Escalation risk %": [a["risk"] for a in an]})
        st.subheader("Coaching recommendations")
        st.write("- Open with empathy when frustration rises above 50%.\n"
                 "- Give a concrete next step and timeline in every reply.\n"
                 "- Offer a supervisor early when the customer mentions cancelling or a refund.")
        with st.expander("Full transcript"):
            for m in s.messages:
                st.write(f"**{m['role'].title()}:** {m['text']}")
    if st.button("➕ New session", type="primary"):
        s.view = "setup"
        s.sid = None
        st.query_params.clear()
        st.rerun()
