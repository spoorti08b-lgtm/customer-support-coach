"""
Orchestrator demonstration script.

Run from the project root:
    py -3 run_demo.py

Shows four scenarios:
  1. Successful workflow
  2. Invalid input rejected by Pydantic schema validation
  3. Valid session ID that does not exist in the store
  4. Agent failure during an otherwise valid workflow
"""

import logging
import sys
from pathlib import Path

from pydantic import ValidationError

# Bootstrap repository root into sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.orchestrator.mock_components import MockAgent, MockSessionManager
from backend.orchestrator.orchestrator import run_workflow
from backend.orchestrator.schemas import WorkflowRequest

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-8s %(name)s — %(message)s",
)


def show(label: str, response) -> None:
    """Print a scenario heading and the key response fields."""
    print(f"\n{'=' * 60}")
    print(f"  {label}")
    print(f"{'=' * 60}")
    print(f"  session_id : {response.session_id}")
    print(f"  status     : {response.status}")
    if response.result:
        print("  result     :")
        for key, value in response.result.items():
            print(f"    {key}: {value}")
    if response.error:
        print(f"  error      : {response.error}")


def show_schema_error(label: str, error: ValidationError) -> None:
    """Print a Pydantic schema rejection."""
    print(f"\n{'=' * 60}")
    print(f"  {label}")
    print(f"{'=' * 60}")
    print("  status     : rejected by schema validation")
    for issue in error.errors():
        print(f"  error      : [{', '.join(str(l) for l in issue['loc'])}] {issue['msg']}")


def main():
    session_manager = MockSessionManager()
    agent = MockAgent()
    failing_agent = MockAgent(force_failure=True)

    # Scenario 1: Successful workflow
    response = run_workflow(
        WorkflowRequest(
            session_id="sess-demo01",
            message="Where is my order? It is two weeks late.",
        ),
        session_manager,
        agent,
    )
    show("Scenario 1 — Successful workflow", response)

    # Scenario 2: Schema validation rejects an empty session_id
    try:
        WorkflowRequest(session_id="", message="Hello")
    except ValidationError as exc:
        show_schema_error("Scenario 2 — Invalid input (empty session_id)", exc)

    # Scenario 3: Valid request but session does not exist
    response = run_workflow(
        WorkflowRequest(session_id="sess-ghost99", message="I need a refund."),
        session_manager,
        agent,
    )
    show("Scenario 3 — Session not found", response)

    # Scenario 4: Agent raises an exception
    response = run_workflow(
        WorkflowRequest(session_id="sess-demo01", message="My product is broken."),
        session_manager,
        failing_agent,
    )
    show("Scenario 4 — Agent failure", response)

    print(f"\n{'=' * 60}")
    print("  Demo complete.")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
