"""Post-interaction report — metrics, sentiment chart, coaching recommendations."""
import streamlit as st

from utils import storage


def render():
    s = st.session_state

    st.markdown(
        "<h1>Post-Interaction Report</h1>"
        '<p class="page-subtitle">Review your session performance and coaching feedback below.</p>',
        unsafe_allow_html=True,
    )

    an = s.analyses
    if not an:
        st.info("No customer messages were analysed in this session.")
    else:
        fr   = [a["frustration"] for a in an]
        peak = max(a["risk"] for a in an)
        tone = [t["score"] for t in s.tone] or [0]
        quality = int(
            max(0, min(100,
                100 - fr[-1] * 0.5 - peak * 0.2 + sum(tone) / len(tone) * 0.2
            ))
        )

        # Summary metrics
        with st.container(border=True):
            col1, col2, col3 = st.columns(3)
            col1.metric("Resolution quality", f"{quality}/100")
            col2.metric("Peak escalation risk", f"{peak}%")
            col3.metric("Customer turns", len(an))

        st.write("")

        # Sentiment journey chart
        with st.container(border=True):
            st.markdown('<p class="section-heading">Sentiment Journey</p>', unsafe_allow_html=True)
            st.line_chart({
                "Frustration %":      fr,
                "Escalation risk %":  [a["risk"] for a in an],
            })

        st.write("")

        # Coaching recommendations
        with st.container(border=True):
            st.markdown('<p class="section-heading">Coaching Recommendations</p>', unsafe_allow_html=True)
            st.write(
                "- Open with empathy when frustration rises above 50%.\n"
                "- Give a concrete next step and timeline in every reply.\n"
                "- Offer a supervisor early when the customer mentions cancelling or a refund."
            )

        with st.expander("Full transcript"):
            for m in s.messages:
                st.write(f"**{m['role'].title()}:** {m['text']}")

    st.write("")
    if st.button("Start new session", type="primary"):
        s.view = "setup"
        s.sid = None
        st.query_params.clear()
        st.rerun()
