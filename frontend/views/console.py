"""Three-panel live coaching console for conversation, coaching, and knowledge."""

import streamlit as st

from backend.services import pipeline_stub as pipe
from backend.services import rag_stub, storage
from backend.services.validation import validate_message


# Show a prominent warning when escalation risk reaches this value.
RISK_ALERT = 70


def add_message(role, text):
    """Append a message, analyze customer messages, and save the session."""
    session = st.session_state
    session.messages.append({"role": role, "text": text})

    if role == "customer":
        session.analyses.append(
            pipe.analyze_turn(text, session.messages, session.config)
        )
    else:
        session.tone.append(pipe.evaluate_agent_reply(text))

    storage.save(session)


def n_customer():
    """Count customer messages in the current conversation."""
    return sum(
        message["role"] == "customer"
        for message in st.session_state.messages
    )


def conversation_panel():
    """Display the conversation and controls for the selected mode."""
    session = st.session_state
    config = session.config

    st.markdown(
        '<p class="section-heading">Conversation</p>',
        unsafe_allow_html=True,
    )

    conversation_box = st.container(height=380, border=True)
    with conversation_box:
        if not session.messages:
            st.caption("No messages yet.")

        for message in session.messages:
            chat_role = (
                "user" if message["role"] == "customer" else "assistant"
            )
            with st.chat_message(chat_role):
                st.write(message["text"])

    mode = config["mode"]

    if mode == "Simulator":
        if not session.messages:
            if st.button(
                "Start simulation",
                type="primary",
                use_container_width=True,
            ):
                add_message("customer", pipe.simulate_customer(config, 0))
                st.rerun()
        else:
            reply_form("Your reply to the customer", after=simulate_next)

    elif mode == "Manual":
        with st.form("customer_message", clear_on_submit=True):
            text = st.text_area("Paste incoming customer message", height=80)
            submitted = st.form_submit_button(
                "Add message and coach",
                use_container_width=True,
            )

            if submitted:
                error = validate_message(text, "Customer message")
                if error:
                    st.error(error)
                else:
                    add_message("customer", text.strip())
                    st.rerun()

        reply_form("Your reply")

    else:  # Replay mode
        script = config.get("replay_script", [])
        index = session.replay_idx
        total = len(script)

        progress = index / total if total else 0
        st.progress(progress, text=f"Message {index} of {total}")

        col_next, col_restart = st.columns(2)

        if col_next.button(
            "Next message",
            type="primary",
            disabled=index >= total,
            use_container_width=True,
        ):
            message = script[index]
            session.replay_idx += 1
            add_message(message["role"], message["text"])
            st.rerun()

        if col_restart.button("Restart replay", use_container_width=True):
            session.messages = []
            session.analyses = []
            session.tone = []
            session.replay_idx = 0
            storage.save(session)
            st.rerun()

        if index >= total:
            st.success("Replay finished. End the session to see the report.")


def simulate_next():
    """Add the next simulated customer message after an agent reply."""
    config = st.session_state.config
    customer_count = n_customer()

    if customer_count < config["max_turns"]:
        add_message(
            "customer",
            pipe.simulate_customer(config, customer_count),
        )
    else:
        st.session_state.flash = (
            "Simulation complete. End the session to see the report."
        )


def reply_form(label, after=None):
    """Display a form for the agent to submit a reply."""
    with st.form(
        f"reply_{len(st.session_state.messages)}",
        clear_on_submit=True,
    ):
        text = st.text_area(label, height=80)
        submitted = st.form_submit_button(
            "Send reply",
            use_container_width=True,
        )

        if submitted:
            error = validate_message(text, "Reply")
            if error:
                st.error(error)
            else:
                add_message("agent", text.strip())
                if after:
                    after()
                st.rerun()


def coaching_panel(analysis):
    """Show the latest sentiment, intent, risk, and reply feedback."""
    st.markdown(
        '<p class="section-heading">Coaching Feed</p>',
        unsafe_allow_html=True,
    )

    if not analysis:
        st.info("Waiting for the first customer message...")
        return

    col_sentiment, col_intent = st.columns(2)
    col_sentiment.metric(
        "Sentiment",
        analysis["sentiment"],
        analysis["emotion"],
        delta_color="off",
    )
    col_intent.metric("Intent", analysis["intent"])

    st.caption(f"Frustration — {analysis['frustration']}%")
    st.progress(analysis["frustration"] / 100)

    st.caption(f"Escalation risk — {analysis['risk']}%")
    st.progress(analysis["risk"] / 100)

    st.write(f"**Why:** {analysis['risk_reason']}")

    if analysis["risk"] >= RISK_ALERT:
        st.warning(f"**Recommended strategy:** {analysis['strategy']}")

    with st.container(border=True):
        st.markdown("**Suggested response**")
        st.write(analysis["suggestion"])

    session = st.session_state
    if session.tone:
        latest_tone = session.tone[-1]
        with st.container(border=True):
            st.markdown(
                f"**Your last reply — tone and clarity: "
                f"{latest_tone['score']}/100**"
            )
            for note in latest_tone["notes"]:
                st.write(note)


def knowledge_panel(analysis):
    """Show the most relevant knowledge-base chunks for the latest message."""
    st.markdown(
        '<p class="section-heading">Knowledge</p>',
        unsafe_allow_html=True,
    )

    if not analysis:
        st.caption("Relevant articles appear after each customer message.")
        return

    if rag_stub.stats()["total"] == 0:
        st.warning("Knowledge base is empty. Upload PDFs on the setup page.")
        return

    if not analysis["chunks"]:
        st.info("No relevant chunks found for this message.")
        return

    for index, chunk in enumerate(analysis["chunks"], 1):
        with st.container(border=True):
            st.markdown(
                f"**#{index} — {chunk['source']}** "
                f"— page {chunk['page']} "
                f'<span class="badge-orange">score {chunk["score"]}</span>',
                unsafe_allow_html=True,
            )

            preview = chunk["text"][:350]
            if len(chunk["text"]) > 350:
                preview += "..."
            st.caption(preview)


def render():
    """Render the page header and the three main console panels."""
    session = st.session_state
    config = session.config

    col_title, col_back, col_end = st.columns([5, 2, 2])

    col_title.markdown(
        "<h1>Live Coaching Console</h1>",
        unsafe_allow_html=True,
    )
    col_title.caption(
        f"Mode: **{config['mode']}** — Product: {config['product']} "
        f"— Session `{session.sid}`"
    )

    if col_back.button("Back to setup", use_container_width=True):
        session.view = "setup"
        storage.save(session)
        st.rerun()

    if col_end.button(
        "End session",
        type="primary",
        use_container_width=True,
    ):
        session.view = "report"
        storage.save(session)
        st.rerun()

    if session.get("flash"):
        st.info(session.pop("flash"))

    analysis = session.analyses[-1] if session.analyses else None
    if analysis and analysis["risk"] >= RISK_ALERT:
        st.error(
            f"HIGH ESCALATION RISK ({analysis['risk']}%) — "
            f"{analysis['risk_reason']}"
        )

    left, middle, right = st.columns([5, 4, 4], gap="medium")

    with left:
        conversation_panel()

    # Refresh the latest analysis after the conversation panel renders.
    analysis = session.analyses[-1] if session.analyses else None

    with middle:
        coaching_panel(analysis)

    with right:
        knowledge_panel(analysis)
