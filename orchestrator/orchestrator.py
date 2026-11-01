
import logging
import sys
from pathlib import Path
from typing import Any
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from customer_support_coach.data_models import AgentResult, InteractionMode
from orchestrator.schemas import WorkflowRequest, WorkflowResponse

logger = logging.getLogger(__name__)


def _failed(session_id: str | None, error: str) -> WorkflowResponse:
    """Return a safe failed workflow response."""
    return WorkflowResponse(
        session_id=session_id,
        status="failed",
        result=None,
        error=error,
    )


def _as_dict(value: Any, component_name: str) -> dict:
    """Normalize supported component responses into dictionaries."""
    if isinstance(value, AgentResult):
        result = value.result

        if isinstance(result, dict) and result:
            return result

        if isinstance(result, str) and result.strip():
            return {"result": result.strip()}

        raise ValueError(
            f"{component_name} returned an empty AgentResult."
        )

    if isinstance(value, dict):
        if not value:
            raise ValueError(
                f"{component_name} returned an empty dictionary."
            )
        return value

    if isinstance(value, str) and value.strip():
        return {"result": value.strip()}

    raise ValueError(
        f"{component_name} returned an unsupported response."
    )


def _call_component(component, method_names, **kwargs):
    """Call the first supported method on a component."""
    if component is None:
        raise ValueError("A required workflow component was not provided.")

    for method_name in method_names:
        method = getattr(component, method_name, None)

        if callable(method):
            return method(**kwargs)

    raise AttributeError(
        f"{type(component).__name__} does not implement any of: "
        f"{', '.join(method_names)}"
    )


def _get_session(session_manager, session_id):
    """Retrieve a session from the session manager."""
    session = session_manager.get_session(session_id)

    if session is None:
        raise LookupError(f"Session '{session_id}' was not found.")

    return session


# ------------------------------------------------------------------
# Milestone 1: Existing single-agent workflow
# ------------------------------------------------------------------

def run_workflow(
    request: WorkflowRequest,
    session_manager,
    agent,
) -> WorkflowResponse:
    """Run the original single-agent workflow."""
    session_id = request.session_id
    message = request.message.strip()

    logger.info(
        "Workflow started | session_id=%r | message_length=%d",
        session_id,
        len(message),
    )

    try:
        session = _get_session(session_manager, session_id)
    except LookupError:
        logger.warning("Session not found | session_id=%r", session_id)
        return _failed(
            session_id,
            f"Session '{session_id}' was not found.",
        )
    except Exception:
        logger.exception(
            "Session manager error | session_id=%r",
            session_id,
        )
        return _failed(
            session_id,
            "Could not retrieve the session. Please try again.",
        )

    try:
        agent_result = agent.run(session=session, message=message)
    except Exception:
        logger.exception("Agent error | session_id=%r", session_id)
        return _failed(
            session_id,
            "The agent encountered an error. Please try again.",
        )

    if not isinstance(agent_result, AgentResult):
        logger.error(
            "Agent returned %s instead of AgentResult | session_id=%r",
            type(agent_result).__name__,
            session_id,
        )
        return _failed(
            session_id,
            "The agent returned an unexpected response format.",
        )

    if not agent_result.result:
        logger.error(
            "AgentResult.result is empty | session_id=%r",
            session_id,
        )
        return _failed(
            session_id,
            "The agent returned an empty result.",
        )

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


# ------------------------------------------------------------------
# Milestone 2: Multi-agent orchestration workflow
# ------------------------------------------------------------------

def run_multi_agent_workflow(
    request: WorkflowRequest,
    session_manager,
    simulator_agent=None,
    sentiment_agent=None,
    knowledge_agent=None,
) -> WorkflowResponse:
    """
    Coordinate the customer simulator, sentiment agent,
    and knowledge recommendation agent.
    """
    session_id = request.session_id
    message = request.message.strip()

    logger.info(
        "Multi-agent workflow started | session_id=%r",
        session_id,
    )

    # Step 1: Retrieve the session.
    try:
        session = _get_session(session_manager, session_id)
    except LookupError:
        logger.warning("Session not found | session_id=%r", session_id)
        return _failed(
            session_id,
            f"Session '{session_id}' was not found.",
        )
    except Exception:
        logger.exception(
            "Session manager error | session_id=%r",
            session_id,
        )
        return _failed(
            session_id,
            "Could not retrieve the session. Please try again.",
        )

    customer_message = message
    simulator_output = {"used": False}

    # Step 2: Generate a customer message in Simulator mode.
    session_mode = getattr(session, "mode", "")
    session_mode = getattr(session_mode, "value", session_mode)
    normalized_mode = str(session_mode).strip().lower()

    if normalized_mode in {
        InteractionMode.SIMULATOR.value.lower(),
        "simulator",
    }:
        try:
            raw_simulator = _call_component(
                simulator_agent,
                ("generate_message", "run", "simulate"),
                session=session,
                message=message,
                prompt=message,
                conversation_history=getattr(session, "messages", []),
                scenario=getattr(session, "scenario", None),
                customer_persona=getattr(
                    session,
                    "customer_persona",
                    getattr(session, "persona", None),
                ),
            )

            simulator_output = _as_dict(
                raw_simulator,
                "simulator",
            )

            generated_message = (
                simulator_output.get("message")
                or simulator_output.get("customer_message")
                or simulator_output.get("response")
                or simulator_output.get("text")
                or simulator_output.get("result")
            )

            if (
                not isinstance(generated_message, str)
                or not generated_message.strip()
            ):
                raise ValueError(
                    "Simulator did not return a customer message."
                )

            customer_message = generated_message.strip()
            simulator_output["used"] = True

        except Exception:
            logger.exception(
                "Customer simulator error | session_id=%r",
                session_id,
            )
            return _failed(
                session_id,
                "The customer simulator failed. Please try again.",
            )

    # Step 3: Analyze customer intent and sentiment.
    try:
        raw_sentiment = _call_component(
            sentiment_agent,
            ("analyze", "run", "predict"),
            session=session,
            message=customer_message,
            customer_message=customer_message,
            conversation_history=getattr(session, "messages", []),
        )

        sentiment_output = _as_dict(
            raw_sentiment,
            "sentiment agent",
        )

    except Exception:
        logger.exception(
            "Sentiment agent error | session_id=%r",
            session_id,
        )
        return _failed(
            session_id,
            "Intent and sentiment analysis failed. Please try again.",
        )

    # Step 4: Retrieve relevant knowledge recommendations.
    try:
        raw_knowledge = _call_component(
            knowledge_agent,
            ("recommend", "run", "retrieve", "search"),
            session=session,
            message=customer_message,
            query=customer_message,
            customer_message=customer_message,
            intent_sentiment=sentiment_output,
            conversation_history=getattr(session, "messages", []),
        )

        knowledge_output = _as_dict(
            raw_knowledge,
            "knowledge agent",
        )

    except Exception:
        logger.exception(
            "Knowledge agent error | session_id=%r",
            session_id,
        )
        return _failed(
            session_id,
            "Knowledge recommendations failed. Please try again.",
        )

    # Step 5: Return the combined workflow result.
    combined_result = {
        "customer_message": customer_message,
        "simulator": simulator_output,
        "intent_sentiment": sentiment_output,
        "knowledge_recommendation": knowledge_output,
    }

    logger.info(
        "Multi-agent workflow completed | session_id=%r",
        session_id,
    )

    return WorkflowResponse(
        session_id=session_id,
        status="completed",
        result=combined_result,
        error=None,
    )
