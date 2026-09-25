"""In-memory Week 4 tools implementing the contracts in the tool catalogue."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable
import re


@dataclass
class ToolSpec:
    name: str
    purpose: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    required_auth_level: int
    higher_impact: bool
    failure_modes: dict[str, str]
    func: Callable[..., dict]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


SERVICE_NAMES = ("mobile_banking", "internet_banking", "atm_network", "agent_banking", "card_services", "ussd_banking")
TICKET_CATEGORIES = SERVICE_NAMES + ("account_access", "other")


class ServiceUnavailable(Exception):
    pass


def make_get_service_status_tool(service_data: dict[str, dict], simulate_down: dict) -> ToolSpec:
    def get_service_status(service_name: str | None = None) -> dict:
        if simulate_down["value"]:
            raise ServiceUnavailable("status service is temporarily unreachable")
        names = [service_name] if service_name else list(SERVICE_NAMES)
        return {"status_code": "OK", "services": [dict(service_data[n]) for n in names]}

    return ToolSpec("get_service_status", "Retrieve current public status of supported banking services.",
        {"service_name": {"type": "string", "required": False, "enum": list(SERVICE_NAMES)}},
        {"status_code": "string", "services": "array"}, 1, False,
        {"invalid_arguments": "unknown service name", "unauthorized": "session is not authenticated", "service_unavailable": "status service unavailable", "unexpected_response": "response does not match service status schema"}, get_service_status)


def make_get_ticket_status_tool(ticket_store: dict[str, dict], simulate_down: dict) -> ToolSpec:
    def get_ticket_status(ticket_id: str, customer_id: str) -> dict:
        if simulate_down["value"]:
            raise ServiceUnavailable("ticketing service is temporarily unreachable")
        ticket = ticket_store.get(ticket_id)
        if ticket is None:
            return {"status_code": "NOT_FOUND", "ticket_id": ticket_id}
        if ticket["customer_id"] != customer_id:
            return {"status_code": "UNAUTHORIZED", "ticket_id": ticket_id}
        return {"status_code": "OK", **{k: ticket[k] for k in ("ticket_id", "status", "category", "created_at", "last_updated", "summary")}}

    return ToolSpec("get_ticket_status", "Retrieve a ticket belonging to the authenticated customer.",
        {"ticket_id": {"type": "string", "required": True}, "customer_id": {"type": "string", "required": True, "source": "session"}},
        {"status_code": "string", "ticket_id": "string"}, 2, False,
        {"invalid_arguments": "ticket ID missing or malformed", "unauthorized": "session is not authenticated or ticket belongs to another customer", "service_unavailable": "ticketing service unavailable", "unexpected_response": "ticket record is malformed"}, get_ticket_status)


def make_create_support_ticket_tool(ticket_store: dict[str, dict], simulate_down: dict, simulate_malformed: dict) -> ToolSpec:
    def create_support_ticket(customer_id: str, category: str, description: str, channel: str = "chat", suggested_priority: str = "medium") -> dict:
        if simulate_down["value"]:
            raise ServiceUnavailable("ticketing service is temporarily unreachable")
        ticket_id = f"CS-{len(ticket_store) + 10245:05d}"
        created_at = _now()
        ticket = {"ticket_id": ticket_id, "customer_id": customer_id, "status": "open", "category": category,
                  "created_at": created_at, "last_updated": created_at, "summary": description[:200],
                  "description": description, "channel": channel, "suggested_priority": suggested_priority}
        ticket_store[ticket_id] = ticket
        response = {"status_code": "OK", "ticket_id": ticket_id, "status": "open", "created_at": created_at,
                    "confirmation_message": f"Ticket {ticket_id} has been created."}
        if simulate_malformed["value"]:
            # Simulate a response lost/malformed after the in-memory write.
            response.pop("ticket_id")
        return response

    return ToolSpec("create_support_ticket", "Create a low-risk simulated support ticket for the authenticated customer.",
        {"customer_id": {"type": "string", "required": True, "source": "session"},
         "category": {"type": "string", "required": True, "enum": list(TICKET_CATEGORIES)},
         "description": {"type": "string", "required": True, "min_length": 10, "max_length": 1000},
         "channel": {"type": "string", "required": False, "default": "chat", "enum": ["chat", "ussd", "mobile_app"]},
         "suggested_priority": {"type": "string", "required": False, "default": "medium", "enum": ["low", "medium", "high"]}},
        {"status_code": "string", "ticket_id": "string", "status": "string", "created_at": "string", "confirmation_message": "string"},
        2, False, {"invalid_arguments": "category or description missing/invalid", "unauthorized": "session is not authenticated", "service_unavailable": "ticketing service unavailable", "unexpected_response": "creation response is malformed; do not claim success"}, create_support_ticket)


def make_escalate_support_case_tool(approved_tokens: dict[str, dict], simulate_down: dict) -> ToolSpec:
    escalations: list[dict] = []
    def escalate_support_case(case_reference: str, reason: str, urgency: str, human_approval_token: str) -> dict:
        if simulate_down["value"]:
            raise ServiceUnavailable("escalation service is temporarily unreachable")
        approval = approved_tokens.get(human_approval_token)
        if not approval or approval != {"case_reference": case_reference, "reason": reason, "urgency": urgency}:
            return {"status_code": "UNAUTHORIZED"}
        approved_tokens.pop(human_approval_token)
        escalation = {"status_code": "OK", "escalation_id": f"ESC-{len(escalations)+1:05d}",
                      "status": "assigned", "assigned_to": "Human Support Team", "timestamp": _now()}
        escalations.append(escalation)
        return escalation

    return ToolSpec("escalate_support_case", "Submit a human-approved support case for human follow-up.",
        {"case_reference": {"type": "string", "required": True},
         "reason": {"type": "string", "required": True, "min_length": 10, "max_length": 500},
         "urgency": {"type": "string", "required": True, "enum": ["low", "medium", "high"]},
         "human_approval_token": {"type": "string", "required": True, "source": "approval"}},
        {"status_code": "string"}, 2, True,
        {"invalid_arguments": "required escalation detail missing or invalid", "unauthorized": "session or approval token invalid", "service_unavailable": "escalation service unavailable", "unexpected_response": "escalation response is malformed; do not claim success"}, escalate_support_case)


def default_service_data() -> dict[str, dict]:
    return {name: {"service_name": name, "status": "unknown", "last_updated": _now(), "message": "Demo status data; not live bank status."} for name in SERVICE_NAMES}

# ---------------------------------------------------------------------------
# Backward-compatible Week 3/early Week 4 tools retained for existing callers.
# The catalogue tools above remain the canonical Week 4 demonstration.
# ---------------------------------------------------------------------------
class KnowledgeBaseUnavailable(Exception):
    """The injected RAG pipeline/index is unavailable."""


class TicketingServiceUnavailable(Exception):
    """The legacy simulated ticket service is unavailable."""


def make_search_knowledge_base_tool(pipeline: "RagPipeline", simulate_down: dict) -> ToolSpec:
    """Retained RAG search tool for existing demo callers."""
    def search_knowledge_base(query: str, k: int = 4) -> dict:
        if simulate_down["value"]:
            raise KnowledgeBaseUnavailable("knowledge base index is temporarily unreachable")
        answer = pipeline.answer(query, k=k)
        return {"query": query, "results": [
            {"marker": source.marker, "doc_id": source.doc_id,
             "doc_title": source.doc_title, "score": source.score, "text": source.text}
            for source in answer.sources
        ]}

    return ToolSpec("search_knowledge_base", "Retrieve relevant passages from the approved knowledge base.",
        {"query": {"type": "string", "required": True},
         "k": {"type": "integer", "required": False, "default": 4}},
        {"query": "string", "results": "array"}, 1, False,
        {"invalid_arguments": "query is missing or empty", "service_unavailable": "knowledge base unavailable",
         "unexpected_response": "response does not match search output schema"}, search_knowledge_base)


def make_legacy_create_support_ticket_tool(ticket_store: list[dict], simulate_down: dict,
                                           simulate_malformed: dict) -> ToolSpec:
    """Retain the original customer_ref/subject/description ticket-call contract."""
    def create_support_ticket_legacy(customer_ref: str, subject: str, description: str,
                                     priority: str = "medium") -> dict:
        if simulate_down["value"]:
            raise TicketingServiceUnavailable("ticketing service did not respond")
        ticket = {"ticket_id": f"LEGACY-{len(ticket_store) + 1:05d}",
                  "customer_ref": customer_ref, "subject": subject,
                  "description": description, "priority": priority,
                  "status": "open", "created_at": _now()}
        ticket_store.append(ticket)
        if simulate_malformed["value"]:
            ticket.pop("ticket_id")
        return ticket

    return ToolSpec("create_support_ticket_legacy",
        "Backward-compatible simulated ticket creation using customer_ref, subject, and description.",
        {"customer_ref": {"type": "string", "required": True},
         "subject": {"type": "string", "required": True},
         "description": {"type": "string", "required": True},
         "priority": {"type": "string", "required": False, "default": "medium",
                       "enum": ["low", "medium", "high"]}},
        {"ticket_id": "string", "customer_ref": "string", "subject": "string",
         "status": "string", "created_at": "string"}, 2, True,
        {"invalid_arguments": "customer_ref, subject, or description missing",
         "unauthorized": "caller is not authorized", "service_unavailable": "ticket service unavailable",
         "unexpected_response": "legacy ticket response is malformed"}, create_support_ticket_legacy)
