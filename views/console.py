"""Three-panel live coaching console for Manual, Replay and Simulator modes.

Panel 1 (left)   - conversation window and the mode's controls.
Panel 2 (middle) - real-time coaching feed: intent, sentiment, emotion,
                   frustration, sentiment trend, escalation risk, coaching
                   focus, suggested response and agent-reply feedback.
Panel 3 (right)  - knowledge recommendations retrieved for the latest
                   customer message.

Manual Mode and Replay Mode both submit turns through
:mod:`backend.modes.manual` / :mod:`backend.modes.replay`, which delegate
analysis to :mod:`backend.modes.coaching` (the existing Intent & Sentiment
Analysis Agent plus the existing knowledge and tone helpers).  Simulator Mode
keeps its original flow.
"""

import time

import streamlit as st

from backend.modes import coaching, manual, replay
from utils import pipeline_stub as pipe
from utils import rag_stub, storage
from utils.validation import validate_message

# Show a prominent warning when escalation risk reaches this value.
RISK_ALERT = coaching.RISK_ALERT


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------


def _save():
    storage.save(st.session_state)


def _flash(kind, text):
    """Queue a message shown at the top of the console after a rerun."""
    st.session_state.flash = (kind, text)


def _show_flash():
    flash = st.session_state.pop("flash", None)
    if not flash:
        return

    kind, text = flash if isinstance(flash, tuple) else ("info", flash)
    {
        "error": st.error,
        "warning": st.warning,
        "success": st.success,
        "ok": st.success,
    }.get(kind, st.info)(text)


def add_message(role, text):
    """Append a Simulator message, analyse it, and save the session."""
    session = st.session_state
    session.messages.append(
        {"id": manual.next_message_id(session), "role": role, "text": text}
    )

    if role == "customer":
        session.analyses.append(
            coaching.analyze_customer_turn(
                text, session.messages[:-1], session.config
            )
        )
    else:
        session.tone.append(coaching.evaluate_agent_turn(text))

    _save()


def n_customer():
    """Count customer messages in the current conversation."""
    return sum(
        message["role"] == "customer"
        for message in st.session_state.messages
    )


# ---------------------------------------------------------------------------
# Panel 1 - conversation and mode controls
# ---------------------------------------------------------------------------


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
        manual_panel()

    else:  # Replay mode
        replay_panel()


def manual_panel():
    """Paste-a-message input for Manual Mode."""
    session = st.session_state

    st.caption(
        f"Session `{session.get('sid')}` - paste what the customer said and "
        "the coaching feed updates for this turn."
    )

    with st.form("m3_manual_customer", clear_on_submit=True):
        text = st.text_area(
            "Paste incoming customer message",
            height=90,
            max_chars=manual.MAX_MESSAGE_CHARS,
            key="m3_manual_input",
        )
        submitted = st.form_submit_button(
            "Add message and coach",
            use_container_width=True,
        )

        if submitted:
            turn = manual.submit_customer_message(st.session_state, text)
            if turn.ok:
                _save()
                _flash("success", "Customer message analysed.")
            elif turn.message is not None:
                _save()
                _flash("error", turn.error)
            else:
                _flash("warning" if turn.duplicate else "error", turn.error)
            st.rerun()

    reply_form("Your reply")


def replay_panel():
    """Replay controls: start/pause/resume/next/previous/restart."""
    session = st.session_state
    current = replay.state(session)

    if not current["has_script"]:
        st.warning(
            "No transcript loaded. Start a new Replay session and upload a "
            "JSON, CSV or TXT transcript."
        )
        return

    config = session.config
    source_format = str(config.get("replay_source_format") or "").upper()
    conversation_id = config.get("replay_conversation_id") or "replay"

    st.progress(
        current["progress"],
        text=f"Message {current['position']} of {current['total']}",
    )
    st.caption(
        f"Replay status: **{current['status'].title()}** - "
        f"conversation `{conversation_id}`"
        + (f" - {source_format}" if source_format else "")
    )

    with st.container(border=True):
        if current["current"]:
            message = current["current"]
            st.markdown(
                f"**Next message {message['index']} of {current['total']} "
                f"- {message['role'].title()}**"
            )
            st.write(message["text"])
        else:
            st.success(
                "End of transcript. Restart or step back to review earlier "
                "turns."
            )

    col_previous, col_next = st.columns(2)

    col_previous.button(
        "Previous message",
        use_container_width=True,
        disabled=current["position"] <= 0,
        key="replay_previous",
        on_click=_replay_action(replay.previous_message),
    )

    col_next.button(
        "Next message",
        type="primary",
        use_container_width=True,
        disabled=current["finished"],
        key="replay_next",
        on_click=_replay_action(replay.next_message),
    )

    col_start, col_pause, col_resume, col_restart = st.columns(4)

    col_start.button(
        "Start",
        use_container_width=True,
        disabled=current["status"] == "playing" or current["finished"],
        key="replay_start",
        on_click=_replay_action(replay.start, autoplay=True),
    )
    col_pause.button(
        "Pause",
        use_container_width=True,
        disabled=current["status"] != "playing",
        key="replay_pause",
        on_click=_replay_action(replay.pause, autoplay=False),
    )
    col_resume.button(
        "Resume",
        use_container_width=True,
        disabled=current["status"] != "paused" or current["finished"],
        key="replay_resume",
        on_click=_replay_action(replay.resume, autoplay=True),
    )
    col_restart.button(
        "Restart",
        use_container_width=True,
        key="replay_restart",
        on_click=_replay_action(replay.restart, autoplay=False),
    )

    auto_play = st.toggle(
        "Auto-play",
        value=current["status"] == "playing",
        key="replay_auto",
        help="Advance to the next message automatically while the replay "
        "is playing.",
        disabled=current["finished"],
        on_change=_sync_autoplay,
    )
    interval = st.slider(
        "Seconds between messages",
        min_value=0.5,
        max_value=5.0,
        value=1.5,
        step=0.5,
        key="replay_interval",
        disabled=not auto_play,
    )

    if auto_play and current["status"] == "playing" and not current["finished"]:
        time.sleep(interval)
        replay.auto_advance(st.session_state)
        _save()
        st.rerun()

    if current["finished"]:
        st.info(
            "Replay finished. End the session to see the report, or use "
            "Previous/Restart to review."
        )


def _replay_action(action, autoplay=None):
    """Build a Streamlit button callback that moves the replay position."""

    def callback():
        action(st.session_state)
        if autoplay is not None:
            st.session_state["replay_auto"] = autoplay
        _save()

    return callback


def _sync_autoplay():
    """Keep the replay status in step with the Auto-play toggle."""
    if st.session_state.get("replay_auto"):
        replay.resume(st.session_state)
    else:
        replay.pause(st.session_state)
    _save()


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
            "info",
            "Simulation complete. End the session to see the report.",
        )


def reply_form(label, after=None):
    """Display a form for the agent to submit a reply."""
    mode = st.session_state.config.get("mode")

    with st.form("m3_agent_reply", clear_on_submit=True):
        text = st.text_area(
            label,
            height=80,
            max_chars=manual.MAX_MESSAGE_CHARS,
            key="m3_reply_input",
        )
        submitted = st.form_submit_button(
            "Send reply",
            use_container_width=True,
        )

        if submitted:
            if mode == "Manual":
                turn = manual.submit_agent_reply(st.session_state, text)
                if turn.ok:
                    _save()
                    _flash("success", "Reply recorded and scored.")
                else:
                    _flash(
                        "warning" if turn.duplicate else "error", turn.error
                    )
                st.rerun()

            error = validate_message(text, "Reply")
            if error:
                _flash("error", error)
                st.rerun()

            add_message("agent", text.strip())
            if after:
                after()
            st.rerun()


# ---------------------------------------------------------------------------
# Panels 2 and 3 - coaching and knowledge
# ---------------------------------------------------------------------------


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
        analysis.get("emotion", ""),
        delta_color="off",
    )
    col_intent.metric("Intent", analysis["intent"])

    if analysis.get("emotions"):
        st.caption("Emotions - " + ", ".join(analysis["emotions"]))
    if analysis.get("intent_confidence") is not None:
        st.caption(
            f"Intent confidence - {analysis['intent_confidence']:.0%}"
        )
    if analysis.get("sentiment_trend") not in (None, "unknown"):
        st.caption(
            f"Sentiment trend - {str(analysis['sentiment_trend']).title()}"
        )

    st.caption(
        f"Frustration - {analysis['frustration']}%"
        + (
            f" ({analysis['frustration_level']})"
            if analysis.get("frustration_level")
            else ""
        )
    )
    st.progress(analysis["frustration"] / 100)

    st.caption(f"Escalation risk - {analysis['risk']}%")
    st.progress(analysis["risk"] / 100)

    if analysis.get("escalation_priority_label"):
        st.caption(
            f"Escalation priority - {analysis['escalation_priority_label']}"
        )

    st.write(f"**Why:** {analysis['risk_reason']}")

    if analysis["risk"] >= RISK_ALERT or analysis.get("requires_human_review"):
        st.warning(f"**Recommended strategy:** {analysis['strategy']}")

    if analysis.get("coaching_focus"):
        st.markdown("**Coaching focus**")
        st.write(
            " - ".join(
                area.replace("_", " ") for area in analysis["coaching_focus"]
            )
        )

    if analysis.get("coaching_guidance"):
        st.caption(analysis["coaching_guidance"])

    with st.container(border=True):
        st.markdown("**Suggested response**")
        st.write(analysis["suggestion"])

    if analysis.get("source") == coaching.FALLBACK_SOURCE:
        st.warning(
            "The live Intent and Sentiment Analysis Agent could not run for "
            "this message, so the existing rule-based pipeline provided the "
            "analysis. No agent output was invented."
        )

    session = st.session_state
    if session.tone:
        latest_tone = session.tone[-1]
        with st.container(border=True):
            if latest_tone.get("score") is None:
                st.markdown("**Your last reply - evaluation unavailable**")
            else:
                st.markdown(
                    f"**Your last reply - tone and clarity: "
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

    if analysis.get("knowledge_error"):
        st.warning(analysis["knowledge_error"])

    if rag_stub.stats()["total"] == 0:
        st.warning("Knowledge base is empty. Upload PDFs on the setup page.")
        return

    if not analysis["chunks"]:
        st.info("No relevant chunks found for this message.")
        return

    for index, chunk in enumerate(analysis["chunks"], 1):
        with st.container(border=True):
            st.markdown(
                f"**#{index} - {chunk['source']}** "
                f"- page {chunk['page']} "
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
    mode_note = {
        "Manual": "Paste each incoming customer message.",
        "Replay": "Step through the uploaded transcript.",
        "Simulator": "The AI customer answers turn by turn.",
    }.get(config["mode"], "")
    col_title.caption(
        f"Mode: **{config['mode']}** - Product: {config['product']} "
        f"- Session `{session.get('sid')}`. {mode_note}"
    )

    if col_back.button("Back to setup", use_container_width=True):
        session.view = "setup"
        _save()
        st.rerun()

    if col_end.button(
        "End session",
        type="primary",
        use_container_width=True,
    ):
        session.view = "report"
        _save()
        st.rerun()

    _show_flash()

    analysis = session.analyses[-1] if session.analyses else None
    alert, alert_text = coaching.escalation_alert(analysis)
    if alert:
        st.error(alert_text)

    left, middle, right = st.columns([5, 4, 4], gap="medium")

    with left:
        conversation_panel()

    # Refresh the latest analysis after the conversation panel renders.
    analysis = session.analyses[-1] if session.analyses else None

    with middle:
        coaching_panel(analysis)

    with right:
        knowledge_panel(analysis)
