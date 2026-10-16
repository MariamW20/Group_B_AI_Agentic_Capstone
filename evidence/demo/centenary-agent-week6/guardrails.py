"""
Guardrails for the Centenary Bank Helpdesk Agent.

This module makes every safety control an explicit, named, testable check.
The agent controller imports these functions and calls them at the correct
point in the Sense→Plan→Act→Observe loop.

Each check returns a GuardrailResult:
  - triggered=True  means the guardrail fired (the request was blocked or flagged)
  - triggered=False means the input passed (safe to continue)

Ten guardrails are defined:

  G-01  Action allow-list          Only pre-approved actions may execute
  G-02  Identity injection          Model must not supply identity fields
  G-03  Tool allow-list            Only pre-approved tools may be called
  G-04  Evidence grounding         No answer without retrieved evidence
  G-05  Escalation approval gate   Escalation requires explicit human approval
  G-06  Memory-not-authorization   Memory context cannot grant escalation
  G-07  Credential non-disclosure  OTPs, PINs, passwords must not be echoed
  G-08  Scope boundary             Funds, loans, account changes → refuse
  G-09  Prompt injection           Override attempts → refuse
  G-10  Iteration limit            Bounded loop prevents runaway execution
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Set


# ── Result type ───────────────────────────────────────────────────────────────

@dataclass
class GuardrailResult:
    guardrail_id: str
    name: str
    triggered: bool
    reason: str
    safety_flag: str = ""

    def __repr__(self) -> str:  # noqa: D105
        status = "TRIGGERED" if self.triggered else "PASS"
        return f"[{self.guardrail_id}] {self.name}: {status} — {self.reason}"


# ── G-01: Action allow-list ───────────────────────────────────────────────────

_ALLOWED_ACTIONS: Set[str] = {
    "answer_from_evidence",
    "check_service_status",
    "check_ticket_status",
    "create_support_ticket",
    "request_escalation_approval",
    "ask_for_clarification",
    "refuse_or_handoff",
}


def check_action_allowlist(action: str) -> GuardrailResult:
    """G-01: block any action not in the pre-approved set."""
    if action in _ALLOWED_ACTIONS:
        return GuardrailResult(
            guardrail_id="G-01",
            name="Action allow-list",
            triggered=False,
            reason=f"Action '{action}' is approved.",
        )
    return GuardrailResult(
        guardrail_id="G-01",
        name="Action allow-list",
        triggered=True,
        reason=f"Action '{action}' is not in the approved set and was blocked.",
        safety_flag="unknown_action_blocked",
    )


# ── G-02: Identity injection prevention ──────────────────────────────────────

_IDENTITY_FIELDS = {"customer_id", "human_approval_token"}


def check_identity_injection(arguments: dict) -> GuardrailResult:
    """G-02: block any plan that tries to inject identity or approval fields."""
    injected = _IDENTITY_FIELDS & set(arguments.keys())
    if not injected:
        return GuardrailResult(
            guardrail_id="G-02",
            name="Identity injection prevention",
            triggered=False,
            reason="No identity fields in model arguments.",
        )
    return GuardrailResult(
        guardrail_id="G-02",
        name="Identity injection prevention",
        triggered=True,
        reason=(
            f"Model attempted to supply protected fields: {sorted(injected)}. "
            "These fields are controlled by the session; the request was rejected."
        ),
        safety_flag="identity_injection_blocked",
    )


# ── G-03: Tool allow-list ─────────────────────────────────────────────────────

_ALLOWED_TOOLS: Set[str] = {
    "search_knowledge_base",
    "get_service_status",
    "get_ticket_status",
    "create_support_ticket",
    "escalate_support_case",
}


def check_tool_allowlist(tool_name: Optional[str]) -> GuardrailResult:
    """G-03: block any tool call naming a tool outside the approved set."""
    if tool_name is None:
        return GuardrailResult(
            guardrail_id="G-03",
            name="Tool allow-list",
            triggered=False,
            reason="No tool required for this action.",
        )
    if tool_name in _ALLOWED_TOOLS:
        return GuardrailResult(
            guardrail_id="G-03",
            name="Tool allow-list",
            triggered=False,
            reason=f"Tool '{tool_name}' is approved.",
        )
    return GuardrailResult(
        guardrail_id="G-03",
        name="Tool allow-list",
        triggered=True,
        reason=f"Tool '{tool_name}' is not in the approved set and was blocked.",
        safety_flag="unknown_tool_blocked",
    )


# ── G-04: Evidence grounding guard ───────────────────────────────────────────

def check_evidence_grounding(retrieved_evidence: list) -> GuardrailResult:
    """G-04: prevent an answer when no retrieved evidence is available."""
    if retrieved_evidence:
        return GuardrailResult(
            guardrail_id="G-04",
            name="Evidence grounding",
            triggered=False,
            reason=f"{len(retrieved_evidence)} evidence item(s) available.",
        )
    return GuardrailResult(
        guardrail_id="G-04",
        name="Evidence grounding",
        triggered=True,
        reason=(
            "No retrieved evidence is available. "
            "The agent must not fabricate a policy or fee answer."
        ),
        safety_flag="no_evidence",
    )


# ── G-05: Escalation approval gate ───────────────────────────────────────────

def check_escalation_approval(human_approved: bool) -> GuardrailResult:
    """G-05: escalation tool must not be called without an explicit human approval."""
    if human_approved:
        return GuardrailResult(
            guardrail_id="G-05",
            name="Escalation approval gate",
            triggered=False,
            reason="Human approval has been granted.",
        )
    return GuardrailResult(
        guardrail_id="G-05",
        name="Escalation approval gate",
        triggered=True,
        reason="Escalation requires explicit human approval; the request was held.",
        safety_flag="escalation_requires_approval",
    )


# ── G-06: Memory-not-authorization ───────────────────────────────────────────

def check_memory_not_authorization(memory_context: list, action: str) -> GuardrailResult:
    """
    G-06: memory context is read-only; it must not be used to auto-approve
    escalation or elevate authorization level.
    """
    if action != "request_escalation_approval":
        return GuardrailResult(
            guardrail_id="G-06",
            name="Memory-not-authorization",
            triggered=False,
            reason="Non-escalation action — memory authorization check not required.",
        )
    if not memory_context:
        return GuardrailResult(
            guardrail_id="G-06",
            name="Memory-not-authorization",
            triggered=False,
            reason="No prior cases in memory — escalation gate will run normally.",
        )
    return GuardrailResult(
        guardrail_id="G-06",
        name="Memory-not-authorization",
        triggered=True,
        reason=(
            f"Memory contains {len(memory_context)} prior case(s), but memory context "
            "cannot authorize escalation. The human approval gate must still run."
        ),
        safety_flag="memory_does_not_authorize",
    )


# ── G-07: Credential non-disclosure ──────────────────────────────────────────

_CREDENTIAL_PATTERNS = [
    re.compile(r"\b(otp|one[- ]time[- ]pass(?:word|code)?)\b", re.IGNORECASE),
    re.compile(r"\bpin\b", re.IGNORECASE),
    re.compile(r"\bpassword\b", re.IGNORECASE),
    re.compile(r"\bcvv\b", re.IGNORECASE),
    re.compile(r"\bcard[- ]number\b", re.IGNORECASE),
    re.compile(r"\bapi[- ]?key\b", re.IGNORECASE),
    re.compile(r"\bsecret\b", re.IGNORECASE),
    re.compile(r"\btoken\b", re.IGNORECASE),
]


def check_credential_request(user_request: str) -> GuardrailResult:
    """
    G-07: detect requests to reveal or echo credentials, PINs, OTPs, or API keys.
    The agent must refuse these regardless of framing.
    """
    for pattern in _CREDENTIAL_PATTERNS:
        if pattern.search(user_request):
            return GuardrailResult(
                guardrail_id="G-07",
                name="Credential non-disclosure",
                triggered=True,
                reason=(
                    "The user request references credential material "
                    f"(matched '{pattern.pattern}'). "
                    "The agent must refuse and never echo secrets."
                ),
                safety_flag="credential_request_refused",
            )
    return GuardrailResult(
        guardrail_id="G-07",
        name="Credential non-disclosure",
        triggered=False,
        reason="No credential keywords detected in the user request.",
    )


# ── G-08: Scope boundary ──────────────────────────────────────────────────────

_OUT_OF_SCOPE_INTENTS: Set[str] = {
    "funds_transfer",
    "loan_decision",
    "account_change",
    "private_balance_check",
    "credential_request",
    "secret_exfiltration",
    "fabrication_request",
    "malicious_evidence",
    "reasoning_request",
}

_OUT_OF_SCOPE_PATTERNS = [
    re.compile(r"\btransfer\b.*\b\d[\d,\.]+\b", re.IGNORECASE),
    re.compile(r"\bapprove\b.*\bloan\b", re.IGNORECASE),
    re.compile(r"\bchange\b.*\bphone\b", re.IGNORECASE),
    re.compile(r"\bchange\b.*\baddress\b", re.IGNORECASE),
    re.compile(r"\bchange\b.*\bemail\b", re.IGNORECASE),
    re.compile(r"\bopen\b.*\baccount\b", re.IGNORECASE),
    re.compile(r"\bclose\b.*\baccount\b", re.IGNORECASE),
]


def check_scope(intent: Optional[str], user_request: str = "") -> GuardrailResult:
    """
    G-08: detect requests that fall outside the agent's supported scope —
    funds movement, loan decisions, account changes, and similar high-impact actions.
    """
    if intent in _OUT_OF_SCOPE_INTENTS:
        return GuardrailResult(
            guardrail_id="G-08",
            name="Scope boundary",
            triggered=True,
            reason=(
                f"Intent '{intent}' is outside the agent's authorized scope. "
                "The request must be refused and routed to an official channel."
            ),
            safety_flag=f"{intent}_blocked",
        )
    for pattern in _OUT_OF_SCOPE_PATTERNS:
        if user_request and pattern.search(user_request):
            return GuardrailResult(
                guardrail_id="G-08",
                name="Scope boundary",
                triggered=True,
                reason=(
                    f"Request matches out-of-scope pattern '{pattern.pattern}'. "
                    "The agent does not perform financial actions."
                ),
                safety_flag="out_of_scope_pattern_blocked",
            )
    return GuardrailResult(
        guardrail_id="G-08",
        name="Scope boundary",
        triggered=False,
        reason="Intent and request are within the supported banking support scope.",
    )


# ── G-09: Prompt injection guard ──────────────────────────────────────────────

_INJECTION_PATTERNS = [
    re.compile(r"\bignore\b.{0,30}\b(prior|previous|all|system)\b.{0,30}\binstruc", re.IGNORECASE),
    re.compile(r"\bforget\b.{0,30}\binstruc", re.IGNORECASE),
    re.compile(r"\banswer as\b.{0,30}\b(admin|administrator|root|system)", re.IGNORECASE),
    re.compile(r"\bact as\b.{0,30}\b(admin|administrator|root|system)", re.IGNORECASE),
    re.compile(r"\byou are now\b", re.IGNORECASE),
    re.compile(r"\boverride\b.{0,30}\b(policy|rule|instruc)", re.IGNORECASE),
    re.compile(r"\bsystem prompt\b", re.IGNORECASE),
    re.compile(r"\bprint your\b.{0,20}\b(instruc|prompt|config|key)", re.IGNORECASE),
    re.compile(r"\bshow\b.{0,20}\bhidden\b.{0,20}\b(reason|instruc|step)", re.IGNORECASE),
    re.compile(r"\bDAN\b"),
    re.compile(r"\bjailbreak\b", re.IGNORECASE),
]


def check_prompt_injection(user_request: str) -> GuardrailResult:
    """
    G-09: detect attempts to override governing instructions, reveal hidden
    reasoning, exfiltrate system configuration, or change the agent's role.
    """
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(user_request):
            return GuardrailResult(
                guardrail_id="G-09",
                name="Prompt injection",
                triggered=True,
                reason=(
                    f"User request matched injection pattern '{pattern.pattern}'. "
                    "Governing instructions are not overridable by user content."
                ),
                safety_flag="prompt_injection_refused",
            )
    return GuardrailResult(
        guardrail_id="G-09",
        name="Prompt injection",
        triggered=False,
        reason="No instruction-override pattern detected.",
    )


# ── G-10: Iteration limit ─────────────────────────────────────────────────────

def check_iteration_limit(attempt_count: int, max_iterations: int) -> GuardrailResult:
    """G-10: enforce the bounded loop; stop when the iteration ceiling is reached."""
    if attempt_count < max_iterations:
        return GuardrailResult(
            guardrail_id="G-10",
            name="Iteration limit",
            triggered=False,
            reason=f"Iteration {attempt_count} of {max_iterations} — loop continues.",
        )
    return GuardrailResult(
        guardrail_id="G-10",
        name="Iteration limit",
        triggered=True,
        reason=(
            f"Iteration limit of {max_iterations} reached. "
            "The loop is stopped and a bounded failure response is issued."
        ),
        safety_flag="iteration_limit_reached",
    )


# ── Convenience: run all input-time guardrails at once ────────────────────────

def check_all_input_guardrails(
    user_request: str,
    intent: Optional[str] = None,
    action: Optional[str] = None,
    tool_name: Optional[str] = None,
    arguments: Optional[dict] = None,
    memory_context: Optional[list] = None,
    retrieved_evidence: Optional[list] = None,
    attempt_count: int = 0,
    max_iterations: int = 4,
) -> List[GuardrailResult]:
    """
    Run the full guardrail suite and return all results.
    Triggered results appear first.
    """
    results = [
        check_prompt_injection(user_request),
        check_credential_request(user_request),
        check_scope(intent, user_request),
        check_action_allowlist(action or ""),
        check_tool_allowlist(tool_name),
        check_identity_injection(arguments or {}),
        check_evidence_grounding(retrieved_evidence or []),
        check_memory_not_authorization(memory_context or [], action or ""),
        check_iteration_limit(attempt_count, max_iterations),
    ]
    return sorted(results, key=lambda r: (not r.triggered, r.guardrail_id))
