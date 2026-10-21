"""Three-panel live coaching console: conversation | coaching feed | knowledge panel."""
import streamlit as st

from utils import pipeline_stub as pipe
from utils import rag_stub, storage
from utils.validation import validate_message

RISK_ALERT = 70


def add_message(role, text):
    s = st.session_state
    s.messages.append({"role": role, "text": text})
    if role == "customer":
        s.analyses.append(pipe.analyze_turn(text, s.messages, s.config))
    else:
        s.tone.append(pipe.evaluate_agent_reply(text))
    storage.save(s)


def n_customer():
    return sum(m["role"] == "customer" for m in st.session_state.messages)


def conversation_panel():
    s, cfg = st.session_state, st.session_state.config
    st.subheader("💬 Conversation")
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
            if st.button("▶ Start simulation", type="primary", use_container_width=True):
                add_message("customer", pipe.simulate_customer(cfg, 0))
                st.rerun()
        else:
            reply_form("Your reply to the customer", after=simulate_next)
    elif mode == "Manual":
        with st.form("cust", clear_on_submit=True):
            txt = st.text_area("Paste incoming customer message", height=80)
            if st.form_submit_button("➕ Add customer message & coach", use_container_width=True):
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
        c1, c2 = st.columns(2)
        if c1.button("⏭ Next message", type="primary", disabled=i >= len(script), use_container_width=True):
            m = script[i]
            s.replay_idx += 1
            add_message(m["role"], m["text"])
            st.rerun()
        if c2.button("↺ Restart replay", use_container_width=True):
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
        st.session_state.flash = "Simulation complete — end the session to see the report."


def reply_form(label, after=None):
    with st.form(f"reply_{len(st.session_state.messages)}", clear_on_submit=True):
        txt = st.text_area(label, height=80)
        if st.form_submit_button("📤 Send reply", use_container_width=True):
            err = validate_message(txt, "Reply")
            if err:
                st.error(err)
            else:
                add_message("agent", txt.strip())
                if after:
                    after()
                st.rerun()


def coaching_panel(a):
    s = st.session_state
    st.subheader("🧠 Coaching feed")
    if not a:
        st.info("Waiting for the first customer message…")
        return
    c1, c2 = st.columns(2)
    c1.metric("Sentiment", a["sentiment"], a["emotion"], delta_color="off")
    c2.metric("Intent", a["intent"])
    st.caption(f"Frustration · {a['frustration']}%")
    st.progress(a["frustration"] / 100)
    st.caption(f"Escalation risk · {a['risk']}%")
    st.progress(a["risk"] / 100)
    st.write(f"**Why:** {a['risk_reason']}")
    if a["risk"] >= RISK_ALERT:
        st.warning(f"**Recommended strategy:** {a['strategy']}")
    with st.container(border=True):
        st.markdown("**💡 Suggested response**")
        st.write(a["suggestion"])
    if s.tone:
        t = s.tone[-1]
        with st.container(border=True):
            st.markdown(f"**🎯 Your last reply — tone & clarity: {t['score']}/100**")
            for n in t["notes"]:
                st.write(n)


def knowledge_panel(a):
    st.subheader("📚 Knowledge")
    if not a:
        st.caption("Relevant articles appear after each customer message.")
        return
    if rag_stub.stats()["total"] == 0:
        st.warning("Knowledge base is empty — upload PDFs on the setup page.")
        return
    if not a["chunks"]:
        st.info("No relevant chunks found for this message.")
    for i, c in enumerate(a["chunks"], 1):
        with st.container(border=True):
            st.markdown(f"**#{i} · 📄 {c['source']}** · p.{c['page']} · score {c['score']}")
            st.caption(c["text"][:350] + ("…" if len(c["text"]) > 350 else ""))


def render():
    s, cfg = st.session_state, st.session_state.config
    h1, h2, h3 = st.columns([5, 2, 2])
    h1.title("🎧 Live Coaching Console")
    h1.caption(f"Mode: **{cfg['mode']}** · Product: {cfg['product']} · Session `{s.sid}`")
    if h2.button("⬅ Back to setup", use_container_width=True):
        s.view = "setup"
        storage.save(s)
        st.rerun()
    if h3.button("🏁 End session", type="primary", use_container_width=True):
        s.view = "report"
        storage.save(s)
        st.rerun()
    if s.get("flash"):
        st.info(s.pop("flash"))
    a = s.analyses[-1] if s.analyses else None
    if a and a["risk"] >= RISK_ALERT:
        st.error(f"🚨 **HIGH ESCALATION RISK ({a['risk']}%)** — {a['risk_reason']}")
    left, mid, right = st.columns([5, 4, 4], gap="medium")
    with left:
        conversation_panel()
    a = s.analyses[-1] if s.analyses else None  # refresh after new message
    with mid:
        coaching_panel(a)
    with right:
        knowledge_panel(a)
