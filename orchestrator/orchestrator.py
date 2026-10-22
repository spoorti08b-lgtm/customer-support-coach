import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from customer_support_coach.data_models import AgentResult

from orchestrator.schemas import WorkflowRequest, WorkflowResponse

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
    request: WorkflowRequest,
    session_manager,
    agent,
) -> WorkflowResponse:
    logger.info(
        "Workflow started | session_id=%r | message_length=%d",
        request.session_id,
        len(request.message),
    )

    session_id = request.session_id
    message = request.message.strip()

    # Step 1: Retrieve the session.
    try:
        session = session_manager.get_session(session_id)
    except Exception:
        logger.exception("Session manager error | session_id=%r", session_id)
        return _failed(session_id, "Could not retrieve the session. Please try again.")

    if session is None:
        logger.warning("Session not found | session_id=%r", session_id)
        return _failed(session_id, f"Session '{session_id}' was not found.")

    # Step 2: Call the agent.
    try:
        agent_result = agent.run(session=session, message=message)
    except Exception:
        logger.exception("Agent error | session_id=%r", session_id)
        return _failed(session_id, "The agent encountered an error. Please try again.")

    # Step 3: Validate the agent's response.
    if not isinstance(agent_result, AgentResult):
        logger.error(
            "Agent returned %s instead of AgentResult | session_id=%r",
            type(agent_result).__name__,
            session_id,
        )
        return _failed(session_id, "The agent returned an unexpected response format.")

    if not agent_result.result:
        logger.error("AgentResult.result is empty | session_id=%r", session_id)
        return _failed(session_id, "The agent returned an empty result.")

    # Step 4: Return success.
    logger.info(
        "Workflow completed | session_id=%r | result_id=%r",
        session_id,
        agent_result.result_id,
    )
    return WorkflowResponse(
        session_id=session_id,
        status="completed",
        result=agent_result.result,
        error=None,
    )
