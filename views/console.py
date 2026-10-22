import streamlit as st

from utils import pipeline_stub as pipe
from utils import rag_stub, storage
from utils.validation import validate_message

# Escalation risk threshold for prominent warning banner
RISK_ALERT = 70

def add_message(role, text):
    """Append a message, run analysis if it is a customer message, then save."""
    s = st.session_state
    s.messages.append({"role": role, "text": text})
    if role == "customer":
        s.analyses.append(pipe.analyze_turn(text, s.messages, s.config))
    else:
        s.tone.append(pipe.evaluate_agent_reply(text))
    storage.save(s)


def n_customer():
    """Count how many customer messages are in the conversation so far."""
    return sum(m["role"] == "customer" for m in st.session_state.messages)

# Conversation panel — left column
def conversation_panel():
    s, cfg = st.session_state, st.session_state.config
    st.markdown('<p class="section-heading">Conversation</p>', unsafe_allow_html=True)
    box = st.container(height=380, border=True)
    with box:
        if not s.messages:
            st.caption("No messages yet.")
        for m in s.messages:
            with st.chat_message("user" if m["role"] == "customer" else "assistant"):
                st.write(m["text"])

    mode = cfg["mode"]

    if mode == "Simulator":
        if not s.messages:
            if st.button("Start simulation", type="primary", use_container_width=True):
                add_message("customer", pipe.simulate_customer(cfg, 0))
                st.rerun()
        else:
            reply_form("Your reply to the customer", after=simulate_next)

    elif mode == "Manual":
        with st.form("cust", clear_on_submit=True):
            txt = st.text_area("Paste incoming customer message", height=80)
            if st.form_submit_button("Add message and coach", use_container_width=True):
                err = validate_message(txt, "Customer message")
                if err:
                    st.error(err)
                else:
                    add_message("customer", txt.strip())
                    st.rerun()
        reply_form("Your reply")

    else:  # Replay
        script, i = cfg["replay_script"], s.replay_idx
        st.progress(i / len(script), text=f"Message {i} of {len(script)}")
        col_next, col_restart = st.columns(2)
        if col_next.button(
            "Next message",
            type="primary",
            disabled=i >= len(script),
            use_container_width=True,
        ):
            m = script[i]
            s.replay_idx += 1
            add_message(m["role"], m["text"])
            st.rerun()
        if col_restart.button("Restart replay", use_container_width=True):
            s.messages, s.analyses, s.tone, s.replay_idx = [], [], [], 0
            storage.save(s)
            st.rerun()
        if i >= len(script):
            st.success("Replay finished — end the session to see the report.")


def simulate_next():
    cfg = st.session_state.config
    k = n_customer()
    if k < cfg["max_turns"]:
        add_message("customer", pipe.simulate_customer(cfg, k))
    else:
        st.session_state.flash = (
            "Simulation complete — end the session to see the report."
        )

def reply_form(label, after=None):
    with st.form(f"reply_{len(st.session_state.messages)}", clear_on_submit=True):
        txt = st.text_area(label, height=80)
        if st.form_submit_button("Send reply", use_container_width=True):
            err = validate_message(txt, "Reply")
            if err:
                st.error(err)
            else:
                add_message("agent", txt.strip())
                if after:
                    after()
                st.rerun()

# Coaching panel — middle column
def coaching_panel(a):
    st.markdown('<p class="section-heading">Coaching Feed</p>', unsafe_allow_html=True)
    if not a:
        st.info("Waiting for the first customer message...")
        return

    col_sent, col_int = st.columns(2)
    col_sent.metric("Sentiment", a["sentiment"], a["emotion"], delta_color="off")
    col_int.metric("Intent", a["intent"])

    st.caption(f"Frustration — {a['frustration']}%")
    st.progress(a["frustration"] / 100)

    st.caption(f"Escalation risk — {a['risk']}%")
    st.progress(a["risk"] / 100)

    st.write(f"**Why:** {a['risk_reason']}")

    if a["risk"] >= RISK_ALERT:
        st.warning(f"**Recommended strategy:** {a['strategy']}")

    with st.container(border=True):
        st.markdown("**Suggested response**")
        st.write(a["suggestion"])

    s = st.session_state
    if s.tone:
        t = s.tone[-1]
        with st.container(border=True):
            st.markdown(f"**Your last reply — tone and clarity: {t['score']}/100**")
            for note in t["notes"]:
                st.write(note)

# Knowledge panel — right column
def knowledge_panel(a):
    st.markdown('<p class="section-heading">Knowledge</p>', unsafe_allow_html=True)
    if not a:
        st.caption("Relevant articles appear after each customer message.")
        return
    if rag_stub.stats()["total"] == 0:
        st.warning("Knowledge base is empty — upload PDFs on the setup page.")
        return
    if not a["chunks"]:
        st.info("No relevant chunks found for this message.")
        return
    for i, chunk in enumerate(a["chunks"], 1):
        with st.container(border=True):
            st.markdown(
                f"**#{i} — {chunk['source']}** "
                f"— p.{chunk['page']} "
                f'<span class="badge-orange">score {chunk["score"]}</span>',
                unsafe_allow_html=True,
            )
            preview = chunk["text"][:350]
            if len(chunk["text"]) > 350:
                preview += "..."
            st.caption(preview)

# Main render
def render():
    s, cfg = st.session_state, st.session_state.config
    
    col_title, col_back, col_end = st.columns([5, 2, 2])
    col_title.markdown(
        "<h1>Live Coaching Console</h1>",
        unsafe_allow_html=True,
    )
    col_title.caption(
        f"Mode: **{cfg['mode']}** — Product: {cfg['product']} — Session `{s.sid}`"
    )
    if col_back.button("Back to setup", use_container_width=True):
        s.view = "setup"
        storage.save(s)
        st.rerun()
    if col_end.button("End session", type="primary", use_container_width=True):
        s.view = "report"
        storage.save(s)
        st.rerun()

    # Flash message
    if s.get("flash"):
        st.info(s.pop("flash"))

    # High-escalation banner
    a = s.analyses[-1] if s.analyses else None
    if a and a["risk"] >= RISK_ALERT:
        st.error(f"HIGH ESCALATION RISK ({a['risk']}%) — {a['risk_reason']}")

    # Three-panel layout
    left, mid, right = st.columns([5, 4, 4], gap="medium")
    with left:
        conversation_panel()
    a = s.analyses[-1] if s.analyses else None  # re-read after any new message
    with mid:
        coaching_panel(a)
    with right:
        knowledge_panel(a)
