"""
AgentState for Week 6: the complete state model from the Week 6 State Model spec.

Every field has a clear source and access-control rule.  These are not just data
holders — they represent the security boundary between what the model controls
and what trusted application code controls.

MUTATION RULES (enforced by AgentControllerV6, not by this class):
  - request_id, customer_id, user_request : immutable once set
  - intent, planned_action                : agent-writable, logged with trace
  - retrieved_evidence, tool_calls        : append-only audit trail
  - attempt_count                         : increment-only, maximum 4
  - retry_count                           : increment-only per failed call, maximum 1
  - approval_status                       : controlled by trusted application/human ONLY
  - memory_context                        : read-only for current decision;
                                            loaded from MemoryStore, never from model output
  - final_response, stop_reason,
    terminal_outcome                      : set exactly once at completion
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class AgentState:
    # ── Trusted identity ────────────────────────────────────────────────────
    # Set by the authenticated session. Immutable during the workflow.
    request_id:   str
    customer_id:  str
    user_request: str

    # ── Agent-writable operational fields ───────────────────────────────────
    intent:             str = ""
    retrieved_evidence: List[dict] = field(default_factory=list)   # append-only
    planned_action:     str = ""
    tool_calls:         List[dict] = field(default_factory=list)   # append-only
    attempt_count:      int = 0    # max 4; incremented only by orchestrator
    retry_count:        int = 0    # max 1 per failed call; reset on new call

    # ── Controlled outside the model ────────────────────────────────────────
    approval_status: str = "not_required"
    # not_required | pending | approved | denied

    # Loaded from MemoryStore by the controller before the loop starts.
    # The model reads it to understand prior context; it cannot write to it.
    memory_context: List[dict] = field(default_factory=list)

    # ── Terminal fields — set exactly once at stop ───────────────────────────
    final_response:   str = ""
    stop_reason:      str = ""
    terminal_outcome: str = ""

    # ── Helpers ─────────────────────────────────────────────────────────────

    def snapshot(self) -> dict:
        """Serialise state for display and trace output."""
        return {
            "request_id":              self.request_id,
            "customer_id":             self.customer_id,
            "user_request":            self.user_request,
            "intent":                  self.intent,
            "retrieved_evidence_count": len(self.retrieved_evidence),
            "planned_action":          self.planned_action,
            "tool_calls_count":        len(self.tool_calls),
            "attempt_count":           self.attempt_count,
            "retry_count":             self.retry_count,
            "approval_status":         self.approval_status,
            "memory_context_count":    len(self.memory_context),
            "final_response":          self.final_response,
            "stop_reason":             self.stop_reason,
            "terminal_outcome":        self.terminal_outcome,
        }
