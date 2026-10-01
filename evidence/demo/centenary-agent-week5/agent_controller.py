"""
AgentController: runs the bounded Sense→Plan→Act→Observe→Stop/Re-plan loop.

Architecture (Week 5):
  - Maximum 4 iterations (attempt_count < 4).
  - Model proposes one action per iteration; code validates, executes, observes.
  - Identity (customer_id, auth_level) and approval tokens come only from the
    trusted session — never from model output.
  - One retry per tool call when error is service_unavailable (safe because
    every current tool raises that before writing anything).
  - Trace written per iteration + one final record to evidence/traces/week5/.
"""
from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path
from typing import Callable, Dict, Optional

# Allow imports from the Week 3/4 demo directory (sibling folder)
_DEMO = Path(__file__).resolve().parent.parent / "centenary-RAG"
sys.path.insert(0, str(_DEMO))

from orchestrator import CallerContext, ToolOrchestrator  # noqa: E402
from tools import (                                        # noqa: E402
    default_service_data,
    make_get_service_status_tool,
    make_get_ticket_status_tool,
    make_create_support_ticket_tool,
    make_escalate_support_case_tool,
    make_search_knowledge_base_tool,
)

from agent_state import AgentState
from planner import Planner, ALLOWED_ACTIONS, ALLOWED_TOOLS
from trace_recorder import append_trace

MAX_ITERATIONS = 4

# Actions that stop immediately without calling a tool
_NO_TOOL_ACTIONS = {"answer_from_evidence", "ask_for_clarification", "refuse_or_handoff"}


class AgentController:
    """
    Runs one customer request through the bounded agent loop.

    Parameters
    ----------
    pipeline : RagPipeline
        Injected Week 3 RAG pipeline.
    ticket_store : dict
        Shared in-memory ticket store (mutated by create/status tools).
    approvals : dict
        Shared approval-token store (managed by the escalation gate).
    simulate_* : dict with {"value": bool}
        Fault-injection handles for tests and demos.
    approval_handler : callable, optional
        Called when the planner requests escalation approval.
        Signature: (case_reference, reason, urgency) -> bool
        True = approved, False = denied.
        Defaults to an interactive console prompt.
    api_key : str, optional
        Gemini API key. Falls back to GEMINI_API_KEY env var.
    """

    def __init__(
        self,
        pipeline,
        ticket_store: dict,
        approvals: dict,
        simulate_service_down: Optional[dict] = None,
        simulate_ticket_down: Optional[dict] = None,
        simulate_escalation_down: Optional[dict] = None,
        simulate_malformed: Optional[dict] = None,
        approval_handler: Optional[Callable] = None,
        api_key: str = "",
    ):
        self._approvals = approvals
        self._simulate_service_down = simulate_service_down or {"value": False}
        self._simulate_ticket_down = simulate_ticket_down or {"value": False}
        self._simulate_escalation_down = simulate_escalation_down or {"value": False}
        self._simulate_malformed = simulate_malformed or {"value": False}
        self._approval_handler = approval_handler or _console_approval_gate

        self.planner = Planner(api_key=api_key or os.getenv("GEMINI_API_KEY", ""))

        service_data = default_service_data()
        tools = [
            make_search_knowledge_base_tool(pipeline, {"value": False}),
            make_get_service_status_tool(service_data, self._simulate_service_down),
            make_get_ticket_status_tool(ticket_store, self._simulate_ticket_down),
            make_create_support_ticket_tool(
                ticket_store, self._simulate_ticket_down, self._simulate_malformed
            ),
            make_escalate_support_case_tool(approvals, self._simulate_escalation_down),
        ]
        self.orchestrator = ToolOrchestrator(tools)

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(self, user_request: str, session: dict) -> AgentState:
        """
        Process one customer request and return the final AgentState.

        session must contain:
          customer_id : str  — authenticated customer identity
          auth_level  : int  — caller's authorization level (1 or 2)
          request_id  : str  — optional; generated if absent
        """
        state = AgentState(
            request_id=session.get("request_id") or str(uuid.uuid4()),
            customer_id=session["customer_id"],
            user_request=user_request,
        )

        print(f"\n[Agent] request_id={state.request_id} customer={state.customer_id}")
        print(f"[Agent] Request: {user_request}\n")

        while state.attempt_count < MAX_ITERATIONS:
            iterations_left = MAX_ITERATIONS - state.attempt_count

            # ── Step 2: Plan / Decide ──────────────────────────────────
            plan = self.planner.decide(state, iterations_left)

            trace = _new_trace(state)

            if plan is None:
                state.attempt_count += 1
                trace["gate_decision"] = "rejected_bad_json"
                append_trace(state.request_id, trace)
                print("[Agent] Planner returned invalid JSON — re-planning.")
                continue

            action = plan.get("action", "")
            tool_name = plan.get("tool") or None
            arguments = plan.get("arguments") or {}
            if plan.get("intent"):
                state.intent = plan["intent"]
            state.planned_action = action

            trace["intent"] = state.intent
            trace["planned_action"] = action

            print(f"[Agent] iter={state.attempt_count + 1} action={action} tool={tool_name}")

            # ── Step 3: Action gate ────────────────────────────────────
            state.attempt_count += 1

            if action not in ALLOWED_ACTIONS:
                trace["gate_decision"] = "rejected_unknown_action"
                append_trace(state.request_id, trace)
                continue

            if "customer_id" in arguments or "human_approval_token" in arguments:
                trace["gate_decision"] = "rejected_identity_in_arguments"
                append_trace(state.request_id, trace)
                continue

            if tool_name and tool_name not in ALLOWED_TOOLS:
                trace["gate_decision"] = "rejected_unknown_tool"
                append_trace(state.request_id, trace)
                continue

            trace["gate_decision"] = "approved"
            trace["tool_name"] = tool_name
            trace["arguments"] = {
                k: v for k, v in arguments.items()
                if k not in ("customer_id", "human_approval_token")
            }

            # ── No-tool actions: answer, clarify, refuse ───────────────
            if action == "answer_from_evidence":
                if state.retrieved_evidence:
                    state.final_response = _compose_knowledge_answer(state)
                    _set_stop(state, "grounded_answer_produced", "ANSWERED_FROM_KNOWLEDGE")
                    _finish_trace(trace, state)
                    append_trace(state.request_id, trace)
                    break
                # No evidence yet — search first before answering
                result = self._tool_call("search_knowledge_base",
                                         {"query": user_request}, session, state)
                _absorb_search(result, state)
                trace["status"] = result.get("status")
                trace["error_type"] = result.get("error_type")
                if result.get("status") == "error" and result.get("error_type") == "service_unavailable":
                    # Retry once
                    result = self._tool_call("search_knowledge_base",
                                             {"query": user_request}, session, state)
                    trace["retried"] = True
                    _absorb_search(result, state)
                    if result.get("status") == "error":
                        state.final_response = (
                            "The knowledge base is temporarily unavailable. "
                            "Please contact Centenary Bank support."
                        )
                        _set_stop(state, "kb_unavailable", "TOOL_FAILURE_HANDOFF")
                        _finish_trace(trace, state)
                        append_trace(state.request_id, trace)
                        break
                append_trace(state.request_id, trace)
                continue

            elif action == "ask_for_clarification":
                state.final_response = (
                    plan.get("reason")
                    or "Could you please provide more details so I can help you?"
                )
                _set_stop(state, "clarification_needed", "CLARIFICATION_REQUIRED")
                _finish_trace(trace, state)
                append_trace(state.request_id, trace)
                break

            elif action == "refuse_or_handoff":
                state.final_response = (
                    "I'm sorry, but this request is outside the scope of what I can "
                    "help with. Please contact Centenary Bank directly or visit a branch."
                )
                _set_stop(state, "out_of_scope", "OUT_OF_SCOPE_HANDOFF")
                _finish_trace(trace, state)
                append_trace(state.request_id, trace)
                break

            # ── Escalation: approval gate then tool ────────────────────
            elif action == "request_escalation_approval":
                approved = self._run_escalation_gate(plan, session, state, trace)
                _finish_trace(trace, state)
                append_trace(state.request_id, trace)
                if state.terminal_outcome:
                    break
                # Gate returned without a terminal outcome (shouldn't happen)
                continue

            # ── Tool-calling actions ───────────────────────────────────
            else:
                result = self._tool_call(tool_name, arguments, session, state)

                # Safe retry on service_unavailable
                if result.get("error_type") == "service_unavailable":
                    print(f"[Agent] {tool_name} unavailable — retrying once.")
                    result = self._tool_call(tool_name, arguments, session, state)
                    trace["retried"] = True
                    if result.get("error_type") == "service_unavailable":
                        state.final_response = (
                            "A required service is temporarily unavailable. "
                            "Please try again later or contact support."
                        )
                        _set_stop(state, "service_unavailable_after_retry", "TOOL_FAILURE_HANDOFF")
                        _finish_trace(trace, state)
                        append_trace(state.request_id, trace)
                        break

                stop = self._observe(tool_name, result, state, trace)
                _finish_trace(trace, state)
                append_trace(state.request_id, trace)
                if stop:
                    break
                continue

        # ── Iteration limit ────────────────────────────────────────────
        if not state.terminal_outcome:
            state.final_response = (
                "I was unable to fully resolve your request within the allowed steps. "
                "Please contact Centenary Bank support for further assistance."
            )
            _set_stop(state, "iteration_limit_reached", "ITERATION_LIMIT_REACHED")
            append_trace(state.request_id, {
                "iteration": state.attempt_count,
                "stop_reason": state.stop_reason,
                "terminal_outcome": state.terminal_outcome,
            })

        print(f"\n[Agent] DONE — outcome={state.terminal_outcome}")
        print(f"[Agent] Response: {state.final_response}")
        return state

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _tool_call(self, tool_name: str, arguments: dict,
                   session: dict, state: AgentState) -> dict:
        """Build CallerContext from trusted session and call the orchestrator."""
        caller = CallerContext(
            auth_level=session.get("auth_level", 2),
            customer_id=session["customer_id"],
        )
        result = self.orchestrator.call(tool_name, arguments, caller)
        # Append to tool_calls with identity fields redacted
        state.tool_calls.append({
            "tool": tool_name,
            "arguments": {k: v for k, v in arguments.items()
                          if k not in ("customer_id", "human_approval_token")},
            "result": result,
        })
        return result

    def _observe(self, tool_name: str, result: dict,
                 state: AgentState, trace: dict) -> bool:
        """
        Inspect the tool result and update state.
        Returns True if the loop should stop.
        """
        status = result.get("status")
        error_type = result.get("error_type")
        res_data = result.get("result") or {}
        status_code = res_data.get("status_code") if isinstance(res_data, dict) else None

        trace["status"] = status
        trace["status_code"] = status_code
        trace["error_type"] = error_type

        # ── Error outcomes ─────────────────────────────────────────────
        if status == "error":
            if error_type == "unauthorized":
                state.final_response = (
                    "You are not authorized to perform this action. "
                    "Only your own tickets can be accessed."
                )
                _set_stop(state, "authorization_denied", "AUTHORIZATION_DENIED")
                return True
            if error_type == "unexpected_response":
                state.final_response = (
                    "An unexpected error occurred. "
                    "Please contact Centenary Bank support."
                )
                _set_stop(state, "unexpected_tool_response", "TOOL_FAILURE_HANDOFF")
                return True
            # invalid_arguments → re-plan without repeating the same call
            return False

        # ── Success outcomes ───────────────────────────────────────────
        if status == "success":

            if tool_name == "search_knowledge_base":
                _absorb_search(result, state)
                return False  # re-plan to answer

            if tool_name == "get_service_status":
                if status_code == "OK":
                    svcs = res_data.get("services", [])
                    lines = "\n".join(
                        f"  {s['service_name']}: {s['status']}" for s in svcs
                    )
                    state.final_response = f"Current service status:\n{lines}"
                    _set_stop(state, "service_status_returned", "SERVICE_STATUS_RETURNED")
                    return True

            if tool_name == "get_ticket_status":
                if status_code == "OK":
                    state.final_response = (
                        f"Ticket {res_data['ticket_id']} — "
                        f"Status: {res_data.get('status', 'unknown')}, "
                        f"Category: {res_data.get('category', 'unknown')}. "
                        f"Summary: {res_data.get('summary', '')}"
                    )
                    _set_stop(state, "ticket_status_returned", "TICKET_STATUS_RETURNED")
                    return True
                if status_code == "NOT_FOUND":
                    state.final_response = (
                        f"Ticket {res_data.get('ticket_id', '')} was not found. "
                        "Please check the ticket ID and try again."
                    )
                    _set_stop(state, "ticket_not_found", "CLARIFICATION_REQUIRED")
                    return True
                if status_code == "UNAUTHORIZED":
                    state.final_response = (
                        "I can only access tickets that belong to your account."
                    )
                    _set_stop(state, "ticket_unauthorized", "AUTHORIZATION_DENIED")
                    return True

            if tool_name == "create_support_ticket":
                if status_code == "OK":
                    tid = res_data.get("ticket_id", "")
                    state.final_response = (
                        f"Your support ticket has been created: {tid}. "
                        f"{res_data.get('confirmation_message', '')}"
                    )
                    _set_stop(state, "ticket_created", "TICKET_CREATED")
                    return True

            if tool_name == "escalate_support_case":
                if status_code == "OK":
                    state.final_response = (
                        f"Your case has been escalated (ID: {res_data.get('escalation_id', '')}). "
                        f"Assigned to: {res_data.get('assigned_to', 'Human Support Team')}."
                    )
                    _set_stop(state, "escalated_after_approval", "ESCALATED_AFTER_APPROVAL")
                    return True
                if status_code == "UNAUTHORIZED":
                    state.final_response = (
                        "The escalation could not be completed — approval mismatch."
                    )
                    _set_stop(state, "escalation_token_mismatch", "AUTHORIZATION_DENIED")
                    return True

        return False

    def _run_escalation_gate(self, plan: dict, session: dict,
                              state: AgentState, trace: dict) -> bool:
        """
        Simulate the human approval gate.
        Issues a single-use token on approval; makes no tool call on denial.
        Returns True if approved and escalation completed, False otherwise.
        """
        args = plan.get("arguments") or {}
        case_reference = args.get("case_reference", state.tool_calls[-1]["result"].get("result", {}).get("ticket_id", "UNKNOWN") if state.tool_calls else "UNKNOWN")
        reason = args.get("reason", "Customer escalation request.")
        urgency = args.get("urgency", "medium")

        state.approval_status = "pending"
        trace["approval_status"] = "pending"

        approved = self._approval_handler(case_reference, reason, urgency)

        if approved:
            state.approval_status = "approved"
            token = f"APPR-{state.request_id[:8]}-{state.attempt_count:02d}"
            self._approvals[token] = {
                "case_reference": case_reference,
                "reason": reason,
                "urgency": urgency,
            }
            approved_ctx = CallerContext(
                auth_level=session.get("auth_level", 2),
                customer_id=session["customer_id"],
                human_approved=True,
                human_approval_token=token,
            )
            result = self.orchestrator.call(
                "escalate_support_case",
                {"case_reference": case_reference, "reason": reason, "urgency": urgency},
                approved_ctx,
            )
            state.tool_calls.append({
                "tool": "escalate_support_case",
                "arguments": {"case_reference": case_reference, "reason": reason, "urgency": urgency},
                "result": result,
            })
            res_data = result.get("result") or {}
            if result.get("status") == "success" and res_data.get("status_code") == "OK":
                state.final_response = (
                    f"Your case has been escalated (ID: {res_data.get('escalation_id', '')}). "
                    f"Assigned to: {res_data.get('assigned_to', 'Human Support Team')}."
                )
                _set_stop(state, "escalated_after_approval", "ESCALATED_AFTER_APPROVAL")
            else:
                state.final_response = "Escalation failed after approval. Please contact support directly."
                _set_stop(state, "escalation_failed", "TOOL_FAILURE_HANDOFF")
            trace["approval_status"] = "approved"
            return True
        else:
            state.approval_status = "denied"
            state.final_response = (
                "The escalation was not approved at this time. "
                "For urgent matters, please contact Centenary Bank through another channel."
            )
            _set_stop(state, "escalation_denied", "OUT_OF_SCOPE_HANDOFF")
            trace["approval_status"] = "denied"
            return False


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------

def _console_approval_gate(case_reference: str, reason: str, urgency: str) -> bool:
    print("\n--- HUMAN APPROVAL REQUIRED ---")
    print(f"  Case reference : {case_reference}")
    print(f"  Reason         : {reason}")
    print(f"  Urgency        : {urgency}")
    print("--------------------------------")
    answer = input("Approve escalation? (yes/no): ").strip().lower()
    return answer == "yes"


def _absorb_search(result: dict, state: AgentState) -> None:
    if result.get("status") == "success":
        for item in (result.get("result") or {}).get("results", []):
            state.retrieved_evidence.append({
                "marker": item.get("marker", ""),
                "doc_id": item.get("doc_id", ""),
                "doc_title": item.get("doc_title", ""),
                "text": item.get("text", ""),
                "score": item.get("score", 0),
            })


def _compose_knowledge_answer(state: AgentState) -> str:
    lines = [f"[{e['marker']}] {e['text']}" for e in state.retrieved_evidence]
    evidence_block = "\n\n".join(lines)
    return (
        f"Based on Centenary Bank's knowledge base:\n\n{evidence_block}\n\n"
        "If you need further assistance, please contact Centenary Bank support."
    )


def _set_stop(state: AgentState, reason: str, outcome: str) -> None:
    state.stop_reason = reason
    state.terminal_outcome = outcome


def _new_trace(state: AgentState) -> dict:
    return {
        "iteration": state.attempt_count + 1,
        "intent": state.intent,
        "planned_action": None,
        "gate_decision": None,
        "tool_name": None,
        "arguments": None,
        "status": None,
        "status_code": None,
        "error_type": None,
        "retried": False,
        "approval_status": state.approval_status,
        "stop_reason": None,
        "terminal_outcome": None,
    }


def _finish_trace(trace: dict, state: AgentState) -> None:
    trace["approval_status"] = state.approval_status
    trace["stop_reason"] = state.stop_reason
    trace["terminal_outcome"] = state.terminal_outcome
