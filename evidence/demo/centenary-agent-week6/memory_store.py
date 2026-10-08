"""
MemoryStore: in-process persistent case-history for the Week 6 demo.

WHY this exists:
  Without persistent case history a returning customer must repeat their entire
  issue and ticket reference every time they contact support. Storing a small,
  validated case record lets the agent continue an existing case without asking
  the customer to repeat themselves.

WHAT is stored:
  ticket_id, category, summary, status, last_action, last_updated, request_id

WHAT is NEVER stored:
  passwords, PINs, approval_tokens, account_numbers, card numbers, transcripts.

ACCESS RULES (from Week 6 Memory Design Note §4):
  - customer_id always comes from the trusted session — never from model output.
  - One customer cannot read another customer's records.
  - The model proposes memory updates; trusted controller code validates and writes.
  - Memory cannot authorize escalation, change identity, or override approval checks.

This is an in-process store for demonstration only.  A production system would
use a secure database with encryption, access logging, and a formal retention policy.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional


# Fields the store will accept — any other field is silently rejected.
_ALLOWED_FIELDS = {
    "ticket_id", "category", "summary", "status",
    "last_action", "last_updated", "request_id",
}

# Fields that must NEVER appear in case data — rejected with an explanation.
_FORBIDDEN_FIELDS = {
    "password", "pin", "approval_token", "account_number",
    "card_number", "cvv", "transcript", "customer_id",
}

_REQUIRED_FIELDS = {"ticket_id", "category", "summary", "status", "last_action"}


@dataclass
class CaseRecord:
    """One support case stored in memory for a single customer."""
    customer_id: str    # always from trusted session, never model-supplied
    ticket_id: str
    category: str
    summary: str
    status: str
    last_action: str
    last_updated: str   # ISO 8601 UTC
    request_id: str     # the workflow request that created/updated this record


@dataclass
class AuditEvent:
    """Immutable audit record for every memory read, write, and delete."""
    event_type: str           # "read" | "write" | "delete"
    customer_id: str
    ticket_id: Optional[str]
    request_id: str
    timestamp: str            # ISO 8601 UTC


class MemoryStore:
    """
    Bounded in-process case-history store.

    All public methods require a trusted customer_id from the application
    session.  The model never calls these methods directly; the controller does.

    Key guarantee: a caller cannot access another customer's records, and the
    model cannot inject a customer_id through case_data.
    """

    def __init__(self) -> None:
        # Primary store: { customer_id: { ticket_id: CaseRecord } }
        self._records: Dict[str, Dict[str, CaseRecord]] = {}
        self._audit_log: List[AuditEvent] = []

    # ── Helpers ────────────────────────────────────────────────────────────────

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def _log(self, event_type: str, customer_id: str,
             ticket_id: Optional[str], request_id: str) -> None:
        self._audit_log.append(AuditEvent(
            event_type=event_type,
            customer_id=customer_id,
            ticket_id=ticket_id,
            request_id=request_id,
            timestamp=self._now(),
        ))

    # ── Public API ─────────────────────────────────────────────────────────────

    def read_cases(self, customer_id: str, request_id: str) -> List[dict]:
        """
        Return all case records for customer_id.

        customer_id is provided by the authenticated session (never by a message
        or model output).  This is the primary ownership enforcement point.
        """
        self._log("read", customer_id, None, request_id)
        bucket = self._records.get(customer_id, {})
        return [
            {
                "ticket_id":   r.ticket_id,
                "category":    r.category,
                "summary":     r.summary,
                "status":      r.status,
                "last_action": r.last_action,
                "last_updated": r.last_updated,
            }
            for r in bucket.values()
        ]

    def write_case(self, customer_id: str, case_data: dict,
                   request_id: str) -> bool:
        """
        Create or update a case record after a validated support event.

        Validation rules (all must pass):
          1. No forbidden fields are present in case_data.
          2. All required fields are present.
          3. customer_id is NOT in case_data (it comes from the session).

        Returns True on success, False on any validation failure.
        """
        # Rule 1 — reject forbidden fields
        for f in _FORBIDDEN_FIELDS:
            if f in case_data:
                print(f"[MemoryStore] REJECTED write: forbidden field '{f}'")
                return False

        # Rule 2 — require essential fields
        missing = _REQUIRED_FIELDS - set(case_data.keys())
        if missing:
            print(f"[MemoryStore] REJECTED write: missing required fields {sorted(missing)}")
            return False

        # Build and store the record
        record = CaseRecord(
            customer_id=customer_id,
            ticket_id=case_data["ticket_id"],
            category=case_data["category"],
            summary=case_data["summary"][:200],   # hard cap — no full transcripts
            status=case_data["status"],
            last_action=case_data["last_action"],
            last_updated=case_data.get("last_updated") or self._now(),
            request_id=request_id,
        )
        if customer_id not in self._records:
            self._records[customer_id] = {}
        self._records[customer_id][record.ticket_id] = record
        self._log("write", customer_id, record.ticket_id, request_id)
        return True

    def delete_case(self, customer_id: str, ticket_id: str,
                    request_id: str) -> bool:
        """
        Remove a case record and log the deletion.

        Audit metadata records that deletion occurred; it does not retain the
        deleted sensitive content.
        """
        bucket = self._records.get(customer_id, {})
        if ticket_id not in bucket:
            return False
        del bucket[ticket_id]
        self._log("delete", customer_id, ticket_id, request_id)
        return True

    def get_audit_log(self) -> List[dict]:
        """Return the full audit trail for inspection (without raw record content)."""
        return [
            {
                "event_type":  e.event_type,
                "customer_id": e.customer_id,
                "ticket_id":   e.ticket_id,
                "request_id":  e.request_id,
                "timestamp":   e.timestamp,
            }
            for e in self._audit_log
        ]
