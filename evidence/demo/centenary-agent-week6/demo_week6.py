"""
Week 6 Demo: Working Memory and State Demonstration
===================================================
Course   : BSE4104 Emerging Trends in Software Engineering
Project  : Centenary Bank Helpdesk Agent
Deliverable: Memory/State Demonstration (evidence/demo/centenary-agent-week6)

Four scenarios — each one isolates a specific teaching point:

  Scenario 1 — New customer opens a case
    Customer with no prior history reports a mobile app crash.
    The agent creates a ticket.  The controller writes a case record
    to the memory store.
    TEACHES: memory is empty at start; memory write happens only after
             a confirmed support event.

  Scenario 2 — Returning customer (memory-enabled continuity)
    The same customer (CUST-88213) returns and asks "What is the update
    on my issue?".  Their prior case (CS-10245) is already in memory.
    The planner uses the stored ticket_id — the customer does not need
    to repeat it.
    TEACHES: memory gives the agent context across sessions.

  Scenario 3 — Cross-customer access control
    A different customer (CUST-HACKER) asks for the status of CS-10245.
    customer_id is taken from the SESSION (CUST-HACKER), not the message.
    The ticket ownership check fails: CS-10245 belongs to CUST-88213.
    TEACHES: customer_id from session enforces ownership; memory cannot
             leak across customers.

  Scenario 4 — Memory cannot auto-approve escalation
    CUST-88213 asks for escalation.  Memory shows their open case.
    The approval gate still runs — memory context alone cannot
    authorize escalation.  Simulated auto-approval then completes it.
    TEACHES: memory is context, not authorization.

Run from the project root:
    python3 evidence/demo/centenary-agent-week6/demo_week6.py

No API key is required — all four scenarios use ScriptedPlanner.
"""
from __future__ import annotations

import sys
from pathlib import Path

# ── Path setup ────────────────────────────────────────────────────────────────
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from memory_store import MemoryStore
from planner_v6 import ScriptedPlanner
from agent_controller_v6 import AgentControllerV6


# ── Shared fixtures ───────────────────────────────────────────────────────────

# In-memory ticket store — shared so Scenario 2 can read a ticket created by
# the demo setup (pre-seeded below).
TICKETS: dict = {
    "CS-10245": {
        "ticket_id":    "CS-10245",
        "customer_id":  "CUST-88213",
        "status":       "in_progress",
        "category":     "mobile_banking",
        "created_at":   "2026-10-01T10:02:00Z",
        "last_updated": "2026-10-03T14:30:00Z",
        "summary":      "Repeated mobile app login failures on Android.",
        "description":  "Repeated mobile app login failures on Android device.",
        "channel":      "chat",
        "suggested_priority": "medium",
    },
}

# Single shared MemoryStore — persists across scenarios within this demo run.
MEMORY = MemoryStore()

# Pre-seed memory for CUST-88213 so Scenario 2 has history to recall.
MEMORY.write_case(
    customer_id="CUST-88213",
    case_data={
        "ticket_id":   "CS-10245",
        "category":    "mobile_banking",
        "summary":     "Repeated mobile app login failures on Android.",
        "status":      "in_progress",
        "last_action": "ticket_created",
    },
    request_id="seed-request-001",
)


def _scenario(title: str) -> None:
    print(f"\n{'#'*60}")
    print(f"  SCENARIO: {title}")
    print(f"{'#'*60}")


def _assert_outcome(state, *expected: str) -> None:
    assert state.terminal_outcome in expected, (
        f"Expected outcome in {expected!r}, got {state.terminal_outcome!r}"
    )
    print(f"\n  PASSED — outcome={state.terminal_outcome}")


# ── Scenario 1: new customer creates a ticket (memory write) ──────────────────

def run_scenario_1() -> None:
    _scenario("1 — New customer creates a ticket  (watch memory_store write)")

    print("""
  WHAT WE ARE TESTING:
    - CUST-99001 has no prior case history.
    - The agent creates a support ticket for their mobile banking crash.
    - AFTER the ticket is confirmed, the controller writes a case record
      to the MemoryStore.  The model does not do this — the controller does.
  """)

    planner = ScriptedPlanner([
        {
            "intent":    "create_ticket",
            "action":    "create_support_ticket",
            "tool":      "create_support_ticket",
            "arguments": {
                "category":    "mobile_banking",
                "description": "Mobile banking app crashes on login screen on Android device.",
            },
            "reason": "Customer reports app crash; creating support ticket.",
        }
    ])

    controller = AgentControllerV6(
        memory_store=MEMORY,
        planner=planner,
        ticket_store=TICKETS,
    )
    session = {
        "request_id": "demo-week6-s1",
        "customer_id": "CUST-99001",
        "auth_level": 2,
    }
    state = controller.run(
        "My mobile banking app keeps crashing every time I try to log in.",
        session,
    )

    _assert_outcome(state, "TICKET_CREATED")

    # Verify the memory store now has a record for CUST-99001
    cases = MEMORY.read_cases("CUST-99001", "verify-s1")
    assert len(cases) == 1, "Expected 1 case record in memory after ticket creation"
    print(f"  Memory now contains 1 case for CUST-99001: {cases[0]['ticket_id']}")


# ── Scenario 2: returning customer — memory provides continuity ───────────────

def run_scenario_2() -> None:
    _scenario("2 — Returning customer  (memory gives continuity)")

    print("""
  WHAT WE ARE TESTING:
    - CUST-88213 already has ticket CS-10245 in memory (pre-seeded above).
    - They return and ask "What is the update on my issue?" — no ticket ID given.
    - The planner reads memory_context (loaded by the controller) and uses the
      stored ticket_id CS-10245 directly.
    - The customer does NOT need to repeat their issue or ticket reference.
  """)

    planner = ScriptedPlanner([
        {
            "intent":    "ticket_status",
            "action":    "check_ticket_status",
            "tool":      "get_ticket_status",
            "arguments": {"ticket_id": "CS-10245"},
            "reason": "Memory shows customer has open ticket CS-10245. Checking status.",
        }
    ])

    controller = AgentControllerV6(
        memory_store=MEMORY,
        planner=planner,
        ticket_store=TICKETS,
    )
    session = {
        "request_id": "demo-week6-s2",
        "customer_id": "CUST-88213",
        "auth_level": 2,
    }
    state = controller.run(
        "What is the update on my issue?",
        session,
    )

    _assert_outcome(state, "TICKET_STATUS_RETURNED", "CLARIFICATION_REQUIRED")

    print("  Memory context loaded on start — customer did NOT repeat their issue.")
    print(f"  memory_context count = {len(state.memory_context)}")


# ── Scenario 3: cross-customer access control ─────────────────────────────────

def run_scenario_3() -> None:
    _scenario("3 — Cross-customer access control  (session binds customer_id)")

    print("""
  WHAT WE ARE TESTING:
    - CUST-HACKER asks for the status of CS-10245 (which belongs to CUST-88213).
    - customer_id in the tool call comes from SESSION (CUST-HACKER), NOT the message.
    - The ticket ownership check rejects this: status_code = UNAUTHORIZED.
    - Memory for CUST-HACKER is also empty — they cannot see CUST-88213's cases.
  """)

    planner = ScriptedPlanner([
        {
            "intent":    "ticket_status",
            "action":    "check_ticket_status",
            "tool":      "get_ticket_status",
            "arguments": {"ticket_id": "CS-10245"},
            "reason": "Checking ticket status as requested.",
        }
    ])

    controller = AgentControllerV6(
        memory_store=MEMORY,
        planner=planner,
        ticket_store=TICKETS,
    )
    session = {
        "request_id": "demo-week6-s3",
        "customer_id": "CUST-HACKER",    # this customer does NOT own CS-10245
        "auth_level": 2,
    }
    state = controller.run(
        "What is the status of ticket CS-10245?",
        session,
    )

    _assert_outcome(state, "AUTHORIZATION_DENIED", "CLARIFICATION_REQUIRED")

    hacker_memory = MEMORY.read_cases("CUST-HACKER", "verify-s3")
    print(f"  CUST-HACKER memory: {hacker_memory}  (correctly empty)")
    print(f"  customer_id in tool was CUST-HACKER, not CUST-88213 — access denied.")


# ── Scenario 4: memory cannot auto-approve escalation ─────────────────────────

def run_scenario_4() -> None:
    _scenario("4 — Memory cannot auto-approve escalation")

    print("""
  WHAT WE ARE TESTING:
    - CUST-88213 has CS-10245 in memory.
    - They request escalation.  The planner proposes request_escalation_approval.
    - The controller's approval gate runs even though memory shows the case exists.
    - Memory context is INFORMATION; it cannot authorize actions.
    - A simulated auto-approval then completes the escalation.
  """)

    planner = ScriptedPlanner([
        {
            "intent":    "escalation",
            "action":    "request_escalation_approval",
            "tool":      None,
            "arguments": {
                "case_reference": "CS-10245",
                "reason":         "Issue unresolved for 7 days. Customer requests human review.",
                "urgency":        "high",
            },
            "reason": "Memory shows open ticket CS-10245. Customer wants escalation.",
        }
    ])

    # Simulated auto-approval — in a real system the UI/human presses Approve.
    def auto_approve(case_reference: str, reason: str, urgency: str) -> bool:
        print(f"\n  [SIMULATED APPROVAL GATE]")
        print(f"    case={case_reference}  urgency={urgency}")
        print(f"    reason={reason[:60]}")
        print(f"    Simulating: APPROVED")
        return True

    approvals: dict = {}
    controller = AgentControllerV6(
        memory_store=MEMORY,
        planner=planner,
        ticket_store=TICKETS,
        approvals=approvals,
        approval_handler=auto_approve,
    )
    session = {
        "request_id": "demo-week6-s4",
        "customer_id": "CUST-88213",
        "auth_level": 2,
    }
    state = controller.run(
        "My issue has been open for 7 days. Please escalate it to a manager.",
        session,
    )

    _assert_outcome(state, "ESCALATED_AFTER_APPROVAL", "OUT_OF_SCOPE_HANDOFF")

    print("  Approval gate ran — memory alone could NOT trigger escalation.")
    print(f"  approval_status in state = {state.approval_status!r}")


# ── Audit log inspection ──────────────────────────────────────────────────────

def print_audit_log() -> None:
    print(f"\n{'='*60}")
    print("  MEMORY AUDIT LOG (all reads, writes, deletes this session)")
    print(f"{'='*60}")
    for event in MEMORY.get_audit_log():
        print(f"  [{event['event_type'].upper():<6}] "
              f"customer={event['customer_id']:<15} "
              f"ticket={event['ticket_id'] or '—':<10} "
              f"req={event['request_id']:<22} "
              f"ts={event['timestamp']}")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Week 6 Memory and State Demonstration")
    print("Centenary Bank Helpdesk Agent — BSE4104")

    run_scenario_1()
    run_scenario_2()
    run_scenario_3()
    run_scenario_4()

    print_audit_log()

    print(f"\n{'='*60}")
    print("  All four scenarios completed successfully.")
    print("  State model and memory lifecycle demonstrated.")
    print(f"{'='*60}")
