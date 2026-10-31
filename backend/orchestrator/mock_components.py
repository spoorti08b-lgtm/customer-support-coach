import logging
import sys
from pathlib import Path


from backend.core.data_models import (
    AgentResult,
    InteractionMode,
    Session,
    Speaker,
)

logger = logging.getLogger(__name__)

# Temporary Session Manager

class MockSessionManager:
    def __init__(self):
        self._store: dict[str, Session] = {}       # Pre-load a couple of test sessions so demos work out of the box.
        self._add_default_sessions()

    def _add_default_sessions(self) -> None:        #Add sessions that tests and the demo script can rely on.
        demo_session = Session(
            session_id="sess-demo01",
            mode=InteractionMode.MANUAL,
            scenario=None,
        )
        self._store[demo_session.session_id] = demo_session

        sim_session = Session(
            session_id="sess-sim01",
            mode=InteractionMode.SIMULATOR,
            scenario="Customer is asking about a delayed shipment.",
        )
        self._store[sim_session.session_id] = sim_session

    def create_session(self, session_id: str | None = None) -> Session:
        kwargs = {}
        if session_id is not None:
            kwargs["session_id"] = session_id

        session = Session(mode=InteractionMode.MANUAL, scenario=None, **kwargs)
        self._store[session.session_id] = session
        logger.debug("MockSessionManager: created session %s", session.session_id)
        return session

    def get_session(self, session_id: str) -> Session | None:
        return self._store.get(session_id)

# Temporary Mock Agent

class MockAgent:

    AGENT_TYPE = "mock-coaching-agent"

    def __init__(
        self,
        force_failure: bool = False,
        return_bad_result: bool = False,
    ):
        self._force_failure = force_failure
        self._return_bad_result = return_bad_result

    def run(self, session: Session, message: str) -> AgentResult:
       
        if self._force_failure:
            raise RuntimeError("MockAgent: simulated agent failure.")

        if self._return_bad_result:
            # Returns a plain dict, not an AgentResult — triggers validation.
            return {"response": "This is not an AgentResult object."}

        # Normal happy-path output.
        result_data = {
            "response": (
                "[MOCK] Thank you for contacting us. "
                "I can see your concern about: "
                f'"{message[:60]}". Let me help you right away.'
            ),
            "coaching_tip": (
                "[MOCK] Good job acknowledging the customer's concern. "
                "Remember to confirm the next action step."
            ),
            "confidence": 0.85,
        }

        return AgentResult(
            session_id=session.session_id,
            agent_type=self.AGENT_TYPE,
            result=result_data,
        )
