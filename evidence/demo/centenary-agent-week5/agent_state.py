"""AgentState: holds all mutable workflow state for one customer request."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, List


@dataclass
class AgentState:
    # Trusted, read-only identity fields set by the application
    request_id: str
    customer_id: str
    user_request: str

    # Agent-writable fields (each has a clear mutation rule per contract §7)
    intent: str = ""                            # model, with trace
    retrieved_evidence: List[dict] = field(default_factory=list)   # append-only
    planned_action: str = ""                    # model, with trace
    tool_calls: List[dict] = field(default_factory=list)           # append-only
    attempt_count: int = 0                      # increment-only by orchestrator
    approval_status: str = "not_required"       # controlled by trusted app/human
    final_response: str = ""                    # set once at stop
    stop_reason: str = ""                       # set once at stop
    terminal_outcome: str = ""                  # set once at stop
