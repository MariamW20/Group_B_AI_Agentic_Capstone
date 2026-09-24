"""
Tool definitions.

Each tool below is deliberately written as: a plain Python function (the
actual capability) + a ToolSpec (the contract the orchestrator enforces --
name, purpose, input/output schema, required authorization level, whether
it's "higher-impact" and therefore needs human approval, and how it fails).

Tool 1: search_knowledge_base
    Read-only. Retrieves current application data (the RAG corpus) for a
    query. Low risk -> no approval gate, minimal authorization.

Tool 2: create_support_ticket
    Simulated side effect. Writes a new record to a (fake, in-memory)
    ticketing system. Higher-impact -> requires human approval before it
    is allowed to execute, and a higher authorization level to even request.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable
import uuid

from pipeline import RagPipeline


# ---------------------------------------------------------------------------
# Tool contracts
# ---------------------------------------------------------------------------

@dataclass
class ToolSpec:
    name: str
    purpose: str
    input_schema: dict[str, Any]     # {field: {"type": ..., "required": bool}}
    output_schema: dict[str, Any]    # {field: type name}
    required_auth_level: int         # caller must have auth_level >= this
    higher_impact: bool              # if True, needs human approval before running
    failure_modes: dict[str, str]    # documented for the catalogue / report
    func: Callable[..., dict]


# ---------------------------------------------------------------------------
# Tool 1: search_knowledge_base (read-only, low risk)
# ---------------------------------------------------------------------------

class KnowledgeBaseUnavailable(Exception):
    """Simulated downstream failure -- e.g. the vector/index store is down."""


def make_search_knowledge_base_tool(pipeline: RagPipeline, simulate_down: dict) -> ToolSpec:
    """
    simulate_down is a mutable dict like {"value": False} so tests can flip
    the service to 'unavailable' without rebuilding the tool.
    """

    def search_knowledge_base(query: str, k: int = 4) -> dict:
        if simulate_down["value"]:
            raise KnowledgeBaseUnavailable("knowledge base index is temporarily unreachable")

        result = pipeline.answer(query, k=k)
        return {
            "query": query,
            "results": [
                {
                    "marker": s.marker,
                    "doc_id": s.doc_id,
                    "doc_title": s.doc_title,
                    "score": s.score,
                    "text": s.text,
                }
                for s in result.sources
            ],
        }

    return ToolSpec(
        name="search_knowledge_base",
        purpose="Retrieve relevant passages from the bank's approved knowledge base to ground an answer.",
        input_schema={
            "query": {"type": "string", "required": True},
            "k": {"type": "integer", "required": False, "default": 4},
        },
        output_schema={
            "query": "string",
            "results": "array of {marker, doc_id, doc_title, score, text}",
        },
        required_auth_level=1,  # any authenticated session, guest or logged-in
        higher_impact=False,
        failure_modes={
            "invalid_arguments": "query missing or empty",
            "service_unavailable": "knowledge base index unreachable -- retry later",
            "empty_result": "not a failure -- zero results above confidence threshold means out-of-corpus question",
        },
        func=search_knowledge_base,
    )


# ---------------------------------------------------------------------------
# Tool 2: create_support_ticket (simulated side effect, higher-impact)
# ---------------------------------------------------------------------------

class TicketingServiceUnavailable(Exception):
    pass


def make_create_support_ticket_tool(ticket_store: list[dict], simulate_down: dict, simulate_malformed: dict) -> ToolSpec:

    def create_support_ticket(customer_ref: str, subject: str, description: str, priority: str = "medium") -> dict:
        if simulate_down["value"]:
            raise TicketingServiceUnavailable("ticketing service did not respond")

        if priority not in ("low", "medium", "high"):
            raise ValueError(f"invalid priority: {priority}")

        ticket = {
            "ticket_id": str(uuid.uuid4())[:8],
            "customer_ref": customer_ref,
            "subject": subject,
            "description": description,
            "priority": priority,
            "status": "open",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        if simulate_malformed["value"]:
            # Simulate a downstream system returning something that doesn't
            # match the agreed output schema, to prove the orchestrator
            # catches this rather than passing garbage back to the model.
            ticket.pop("ticket_id")

        ticket_store.append(ticket)
        return ticket

    return ToolSpec(
        name="create_support_ticket",
        purpose="Create a draft support ticket for a customer issue the agent could not resolve itself.",
        input_schema={
            "customer_ref": {"type": "string", "required": True},
            "subject": {"type": "string", "required": True},
            "description": {"type": "string", "required": True},
            "priority": {"type": "string", "required": False, "default": "medium", "enum": ["low", "medium", "high"]},
        },
        output_schema={
            "ticket_id": "string",
            "customer_ref": "string",
            "subject": "string",
            "status": "string",
            "created_at": "string (ISO 8601)",
        },
        required_auth_level=2,  # elevated -- this writes a record
        higher_impact=True,     # requires human approval before executing
        failure_modes={
            "invalid_arguments": "customer_ref, subject or description missing",
            "unauthorized": "caller auth_level below 2",
            "service_unavailable": "ticketing backend unreachable -- do not silently drop the request",
            "unexpected_response": "backend returned a record missing required fields (e.g. no ticket_id)",
        },
        func=create_support_ticket,
    )
