"""UI-level tests for Milestone 3 using Streamlit's AppTest harness.

These drive the real ``app.py``: the setup form creates a session, Manual
Mode submits pasted customer messages through the console form, and Replay
Mode's Previous/Next/Restart buttons move through a transcript.  Sessions are
written to a temporary directory so the developer's saved sessions are not
touched.

AppTest cannot follow a view switch and then keep driving widgets from the
previous view (stale widget ids), so setup-flow tests assert the resulting
session state, while console-flow tests seed the session state directly and
then exercise the console controls.
"""

from __future__ import annotations

import pytest

from utils import storage

pytest.importorskip("streamlit.testing.v1")
from streamlit.testing.v1 import AppTest  # noqa: E402

PRODUCT = "Acme Wireless Router X200"
SCENARIO = "Customer's order has not arrived after ten days."

REPLAY_SCRIPT = [
    {"id": "msg-0001", "role": "customer", "text": "My order has not arrived yet."},
    {
        "id": "msg-0002",
        "role": "agent",
        "text": "I'm sorry about the delay. Let me check the tracking.",
    },
    {
        "id": "msg-0003",
        "role": "customer",
        "text": "I have contacted support twice. This is ridiculous!",
    },
    {
        "id": "msg-0004",
        "role": "agent",
        "text": "I understand. I'm escalating this to a specialist now.",
    },
]


@pytest.fixture
def sessions_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "DIR", tmp_path)
    return tmp_path


def app() -> AppTest:
    return AppTest.from_file("app.py", default_timeout=90)


def click(at: AppTest, label: str, index: int = 0) -> AppTest:
    matches = [button for button in at.button if button.label == label]
    assert matches, f"button {label!r} not found in {[b.label for b in at.button]}"
    matches[index].click().run()
    return at


def seed_console(at: AppTest, config: dict, sid: str = "uitest01") -> AppTest:
    for key, value in {
        "_ready": True,
        "sid": sid,
        "view": "console",
        "config": config,
        "messages": [],
        "analyses": [],
        "tone": [],
        "replay_idx": 0,
        "replay_status": "idle",
        "replay_analyses": {},
        "replay_tones": {},
    }.items():
        at.session_state[key] = value
    at.run()
    return at


def manual_config() -> dict:
    return {
        "mode": "Manual",
        "product": PRODUCT,
        "scenario": SCENARIO,
        "persona": "Calm",
        "max_turns": 5,
        "replay_script": [],
    }


def replay_config() -> dict:
    return {
        "mode": "Replay",
        "product": PRODUCT,
        "scenario": "Customer reports a delayed order after two contacts.",
        "persona": "Calm",
        "max_turns": 5,
        "replay_script": REPLAY_SCRIPT,
        "replay_conversation_id": "ui_replay_001",
        "replay_source_format": "json",
    }


# ---------------------------------------------------------------------------
# Setup page
# ---------------------------------------------------------------------------


def test_setup_starts_manual_session(sessions_dir):
    at = app()
    at.run()

    at.radio(key="f_mode").set_value("Manual").run()
    at.text_input(key="f_product").set_value(PRODUCT)
    at.text_area(key="f_scenario").set_value(SCENARIO)
    at.run()

    click(at, "Start coaching session")

    assert not at.exception
    assert at.session_state["view"] == "console"
    assert at.session_state["config"]["mode"] == "Manual"
    assert at.session_state["messages"] == []
    assert (sessions_dir / f"{at.session_state['sid']}.json").exists()


def test_setup_previews_and_starts_bundled_replay(sessions_dir):
    at = app()
    at.run()

    at.radio(key="f_mode").set_value("Replay").run()
    at.text_input(key="f_product").set_value(PRODUCT)
    at.text_area(key="f_scenario").set_value(SCENARIO)
    at.run()

    assert not at.exception
    # Preview table and message count are shown before starting.
    assert len(at.dataframe) == 1
    assert len(at.dataframe[0].value) == 7
    captions = " ".join(caption.value for caption in at.caption)
    assert "Conversation `sample_transcript`" in captions
    assert "messages" in captions

    click(at, "Start coaching session")

    assert not at.exception
    assert at.session_state["view"] == "console"
    config = at.session_state["config"]
    assert config["mode"] == "Replay"
    assert len(config["replay_script"]) == 7
    assert config["replay_source_format"] == "txt"
    assert config["replay_conversation_id"] == "sample_transcript"


def test_setup_blocks_replay_without_a_transcript(sessions_dir):
    at = app()
    at.run()

    at.radio(key="f_mode").set_value("Replay").run()
    at.text_input(key="f_product").set_value(PRODUCT)
    at.text_area(key="f_scenario").set_value(SCENARIO)
    at.run()

    # Switch to upload mode but provide no file.
    at.radio(key="f_src").set_value("Upload file").run()
    click(at, "Start coaching session")

    assert at.session_state["view"] == "setup"
    assert any("transcript" in error.value.lower() for error in at.error)


# ---------------------------------------------------------------------------
# Manual Mode console
# ---------------------------------------------------------------------------


def test_manual_console_submits_message_and_updates_panels(sessions_dir):
    at = seed_console(app(), manual_config())

    at.text_area(key="m3_manual_input").set_value(
        "My order has not arrived yet. This is the third time I have contacted you!"
    )
    click(at, "Add message and coach")

    assert not at.exception
    assert len(at.session_state["messages"]) == 1
    assert len(at.session_state["analyses"]) == 1
    assert [message.name for message in at.chat_message] == ["user"]

    metrics = {metric.label: metric.value for metric in at.metric}
    assert metrics["Intent"] == "Order or service status"
    assert metrics["Sentiment"] in {"Negative", "Mixed", "Neutral", "Positive"}

    markdown = " ".join(element.value for element in at.markdown)
    assert "Coaching Feed" in markdown
    assert "Knowledge" in markdown
    assert at.session_state["analyses"][0]["suggestion"]


def test_manual_console_rejects_empty_and_duplicate_messages(sessions_dir):
    at = seed_console(app(), manual_config())

    click(at, "Add message and coach")
    assert at.session_state["messages"] == []
    assert any("empty" in error.value.lower() for error in at.error)

    at.text_area(key="m3_manual_input").set_value("My order has not arrived yet.")
    click(at, "Add message and coach")
    at.text_area(key="m3_manual_input").set_value("  My order has not arrived yet. ")
    click(at, "Add message and coach")

    assert len(at.session_state["messages"]) == 1
    assert any(
        "already submitted" in message.value for message in at.warning
    )


def test_manual_console_records_agent_reply(sessions_dir):
    at = seed_console(app(), manual_config(), sid="uitest02")

    at.text_area(key="m3_manual_input").set_value("My order has not arrived yet.")
    click(at, "Add message and coach")
    at.text_area(key="m3_reply_input").set_value(
        "I'm sorry about the delay. I've checked tracking and it arrives tomorrow."
    )
    click(at, "Send reply")

    assert not at.exception
    assert [message["role"] for message in at.session_state["messages"]] == [
        "customer",
        "agent",
    ]
    assert len(at.session_state["tone"]) == 1
    assert at.session_state["tone"][0]["score"] is not None


# ---------------------------------------------------------------------------
# Replay Mode console
# ---------------------------------------------------------------------------


def test_replay_console_next_previous_restart(sessions_dir):
    at = seed_console(app(), replay_config(), sid="uitest03")

    assert [button.label for button in at.button] == [
        "Back to setup",
        "End session",
        "Previous message",
        "Next message",
        "Start",
        "Pause",
        "Resume",
        "Restart",
    ]

    for _ in range(3):
        click(at, "Next message")

    assert at.session_state["replay_idx"] == 3
    assert len(at.session_state["messages"]) == 3
    assert len(at.session_state["analyses"]) == 2
    assert len(at.session_state["tone"]) == 1
    assert [message.name for message in at.chat_message] == [
        "user",
        "assistant",
        "user",
    ]

    click(at, "Previous message")
    assert at.session_state["replay_idx"] == 2
    assert len(at.session_state["messages"]) == 2
    assert len(at.session_state["analyses"]) == 1

    click(at, "Next message")
    click(at, "Next message")
    assert at.session_state["replay_idx"] == 4
    assert len(at.session_state["messages"]) == 4
    assert len(at.session_state["analyses"]) == 2

    click(at, "Restart")
    assert at.session_state["replay_idx"] == 0
    assert at.session_state["messages"] == []
    assert at.session_state["analyses"] == []


def test_replay_console_finishes_and_alerts_on_escalation(sessions_dir):
    script = [
        {"id": "msg-0001", "role": "customer", "text": "My card was charged twice."},
        {
            "id": "msg-0002",
            "role": "agent",
            "text": "I'm sorry, I have started a refund for the duplicate charge.",
        },
        {
            "id": "msg-0003",
            "role": "customer",
            "text": (
                "This is the worst service ever! I'm furious and want to cancel "
                "my account. I will file a complaint and contact my lawyer!"
            ),
        },
    ]
    config = {**replay_config(), "replay_script": script}
    at = seed_console(app(), config, sid="uitest04")

    for _ in range(3):
        click(at, "Next message")

    assert at.session_state["replay_status"] == "finished"
    assert len(at.session_state["analyses"]) == 2
    assert any("HIGH ESCALATION RISK" in error.value for error in at.error)
    assert any(
        "End of transcript" in message.value for message in at.success
    )

    markdown = " ".join(element.value for element in at.markdown)
    assert "Coaching Feed" in markdown
    assert "Knowledge" in markdown
