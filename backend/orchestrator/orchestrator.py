"""Workflow orchestrator for customer support coaching sessions."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

from backend.core.data_models import AgentResult
from backend.orchestrator.schemas import WorkflowRequest, WorkflowResponse

logger = logging.getLogger(__name__)


def _failed(session_id: str | None, error: str) -> WorkflowResponse:
    """Build a failed WorkflowResponse."""
    return WorkflowResponse(
        session_id=session_id,
        status="failed",
        result=None,
        error=error,
    )


def run_workflow(
    request: Any = None,
    session_manager: Any = None,
    agent: Any = None,
    *,
    session_id: str | None = None,
    mode: str = "Simulator",
    **kwargs: Any,
) -> Any:
    """Run orchestrator workflow.
    
    When invoked with (request, session_manager, agent), executes the full multi-agent
    coordination workflow. When invoked in Milestone 1 mode (e.g. at session creation),
    returns a ready stub dictionary: {"status": "ready", "session_id": ..., "mode": ...}.
    """
    # Milestone 1 stub call path (from session setup)
    if session_manager is None and agent is None:
        sid = session_id
        if sid is None and request is not None:
            sid = getattr(request, "session_id", None) or str(request)
        if hasattr(request, "mode"):
            mode = getattr(request.mode, "value", str(request.mode))
        logger.info("Milestone 1 stub workflow ready | session_id=%r | mode=%r", sid, mode)
        return {
            "status": "ready",
            "session_id": sid or "sess-ready",
            "mode": mode,
        }

    # Full orchestration workflow path (for orchestrator unit tests and integration)
    if not isinstance(request, WorkflowRequest):
        try:
            req_sid = getattr(request, "session_id", session_id or "sess-default")
            req_msg = getattr(request, "message", kwargs.get("message", "Ready"))
            request = WorkflowRequest(session_id=req_sid, message=req_msg)
        except Exception as exc:
            return _failed(session_id, f"Invalid request: {exc}")

    logger.info(
        "Workflow started | session_id=%r | message_length=%d",
        request.session_id,
        len(request.message),
    )

    req_id = request.session_id
    message = request.message.strip()

    # Step 1: Retrieve the session
    try:
        session = session_manager.get_session(req_id)
    except Exception:
        logger.exception("Session manager error | session_id=%r", req_id)
        return _failed(req_id, "Could not retrieve the session. Please try again.")

    if session is None:
        logger.warning("Session not found | session_id=%r", req_id)
        return _failed(req_id, f"Session '{req_id}' was not found.")

    # Step 2: Call the agent
    try:
        agent_result = agent.run(session=session, message=message)
    except Exception:
        logger.exception("Agent error | session_id=%r", req_id)
        return _failed(req_id, "The agent encountered an error. Please try again.")

    # Step 3: Validate the agent's response
    if not isinstance(agent_result, AgentResult):
        logger.error(
            "Agent returned %s instead of AgentResult | session_id=%r",
            type(agent_result).__name__,
            req_id,
        )
        return _failed(req_id, "The agent returned an unexpected response format.")

    if not agent_result.result:
        logger.error("AgentResult.result is empty | session_id=%r", req_id)
        return _failed(req_id, "The agent returned an empty result.")

    # Step 4: Return success
    logger.info(
        "Workflow completed | session_id=%r | result_id=%r",
        req_id,
        agent_result.result_id,
    )
    return WorkflowResponse(
        session_id=req_id,
        status="completed",
        result=agent_result.result,
        error=None,
    )
