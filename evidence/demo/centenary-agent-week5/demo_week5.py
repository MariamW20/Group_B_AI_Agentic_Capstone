"""
Week 5 demo: three scenarios that produce the required traces.

  Scenario 1 — Grounded knowledge answer
      Customer asks a policy question → agent searches KB → answers from evidence
      Expected outcome: ANSWERED_FROM_KNOWLEDGE

  Scenario 2 — Ticket workflow
      Customer asks for their ticket status → agent checks it → returns status
      Expected outcome: TICKET_STATUS_RETURNED

  Scenario 3 — Failure / recovery (service unavailable then handoff)
      Customer asks for service status → service is down → retry fails → handoff
      Expected outcome: TOOL_FAILURE_HANDOFF

Run from the project root:
    cd /path/to/Group_B_AI_Agentic_Capstone
    GEMINI_API_KEY=your_key python3 evidence/demo/centenary-agent-week5/demo_week5.py

Traces are written to evidence/traces/week5/<request_id>.json
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Make this directory importable (agent_state, planner, etc. live here)
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

# Add the centenary-RAG demo to path (sibling folder — ToolOrchestrator, tools)
_DEMO = _HERE.parent / "centenary-RAG"
sys.path.insert(0, str(_DEMO))

from simple_pipeline import SimplePipeline
from agent_controller import AgentController
from ingest import load_project_corpus

# ------------------------------------------------------------------
# Shared fixture data
# ------------------------------------------------------------------

TICKETS = {
    "CS-10245": {
        "ticket_id": "CS-10245",
        "customer_id": "CUST-88213",
        "status": "in_progress",
        "category": "mobile_banking",
        "created_at": "2026-09-20T10:02:00Z",
        "last_updated": "2026-09-21T14:30:00Z",
        "summary": "Repeated mobile app login failures.",
    },
    "CS-10246": {
        "ticket_id": "CS-10246",
        "customer_id": "CUST-OTHER",
        "status": "open",
        "category": "card_services",
        "created_at": "2026-09-20T10:02:00Z",
        "last_updated": "2026-09-21T14:30:00Z",
        "summary": "Private record — ownership check demo.",
    },
}


def _make_pipeline() -> SimplePipeline:
    """Load the real Centenary Bank FAQ corpus from the project CSVs."""
    docs = load_project_corpus()
    chunks = [
        {"doc_id": d.doc_id, "doc_title": d.title, "text": d.text}
        for d in docs
    ]
    print(f"[Demo] Loaded {len(chunks)} documents from project corpus.")
    return SimplePipeline(chunks)


def _separator(title: str) -> None:
    print("\n" + "=" * 60)
    print(f"  SCENARIO: {title}")
    print("=" * 60)


# ------------------------------------------------------------------
# Scenario 1: Grounded knowledge answer
# ------------------------------------------------------------------

def run_scenario_1(pipeline: RagPipeline) -> None:
    _separator("1 — Grounded knowledge answer")
    approvals: dict = {}
    controller = AgentController(
        pipeline=pipeline,
        ticket_store=dict(TICKETS),
        approvals=approvals,
        api_key=os.getenv("GEMINI_API_KEY", ""),
    )
    session = {
        "request_id": "demo-week5-s1",
        "customer_id": "CUST-88213",
        "auth_level": 2,
    }
    state = controller.run(
        "How do I activate mobile banking on my phone?",
        session,
    )
    print(f"\n[Trace] Written to evidence/traces/week5/{state.request_id}.json")
    assert state.terminal_outcome in (
        "ANSWERED_FROM_KNOWLEDGE", "CLARIFICATION_REQUIRED", "OUT_OF_SCOPE_HANDOFF"
    ), f"Unexpected outcome: {state.terminal_outcome}"


# ------------------------------------------------------------------
# Scenario 2: Ticket workflow
# ------------------------------------------------------------------

def run_scenario_2(pipeline: RagPipeline) -> None:
    _separator("2 — Ticket status workflow")
    approvals: dict = {}
    controller = AgentController(
        pipeline=pipeline,
        ticket_store=dict(TICKETS),
        approvals=approvals,
        api_key=os.getenv("GEMINI_API_KEY", ""),
    )
    session = {
        "request_id": "demo-week5-s2",
        "customer_id": "CUST-88213",
        "auth_level": 2,
    }
    state = controller.run(
        "What is the status of my ticket CS-10245?",
        session,
    )
    print(f"\n[Trace] Written to evidence/traces/week5/{state.request_id}.json")
    assert state.terminal_outcome in (
        "TICKET_STATUS_RETURNED", "CLARIFICATION_REQUIRED", "AUTHORIZATION_DENIED"
    ), f"Unexpected outcome: {state.terminal_outcome}"


# ------------------------------------------------------------------
# Scenario 3: Failure / recovery — service unavailable → handoff
# ------------------------------------------------------------------

def run_scenario_3(pipeline: RagPipeline) -> None:
    _separator("3 — Failure and recovery (service unavailable → handoff)")
    approvals: dict = {}
    service_down = {"value": True}   # Force the service to be down for this demo
    controller = AgentController(
        pipeline=pipeline,
        ticket_store=dict(TICKETS),
        approvals=approvals,
        simulate_service_down=service_down,
        api_key=os.getenv("GEMINI_API_KEY", ""),
    )
    session = {
        "request_id": "demo-week5-s3",
        "customer_id": "CUST-88213",
        "auth_level": 2,
    }
    state = controller.run(
        "Is the ATM network currently working?",
        session,
    )
    print(f"\n[Trace] Written to evidence/traces/week5/{state.request_id}.json")
    assert state.terminal_outcome in (
        "TOOL_FAILURE_HANDOFF", "SERVICE_STATUS_RETURNED",
        "OUT_OF_SCOPE_HANDOFF", "ITERATION_LIMIT_REACHED"
    ), f"Unexpected outcome: {state.terminal_outcome}"


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

if __name__ == "__main__":
    if not os.getenv("GEMINI_API_KEY"):
        print("[ERROR] GEMINI_API_KEY is not set.")
        print("  Set it with:  export GEMINI_API_KEY=your_key_here")
        sys.exit(1)

    pipeline = _make_pipeline()

    run_scenario_1(pipeline)
    run_scenario_2(pipeline)
    run_scenario_3(pipeline)

    print("\n" + "=" * 60)
    print("  All three demo scenarios completed.")
    print("  Traces written to evidence/traces/week5/")
    print("=" * 60)
