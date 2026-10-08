"""
Planners for Week 6.

Two implementations:

ScriptedPlanner
  Used in the demo — deterministic action sequences that need no API key.
  Each scenario pre-loads the script it wants; the planner pops steps in order.
  Good for teaching because the state transitions are predictable and clear.

GeminiPlannerV6
  Extends the Week 5 Gemini planner to include memory_context in the prompt.
  Requires GEMINI_API_KEY.  Not used in the scripted demo scenarios but
  available when a live LLM is preferred.
"""
from __future__ import annotations

import json
import os
import urllib.request
import urllib.error
from typing import List, Optional

from agent_state_v6 import AgentState

# ── Allowed actions and tools (same as Week 5 — the allow-list is the gate) ──

ALLOWED_ACTIONS = {
    "answer_from_evidence",
    "check_service_status",
    "check_ticket_status",
    "create_support_ticket",
    "request_escalation_approval",
    "ask_for_clarification",
    "refuse_or_handoff",
}

ALLOWED_TOOLS = {
    "search_knowledge_base",
    "get_service_status",
    "get_ticket_status",
    "create_support_ticket",
    "escalate_support_case",
}


# ── ScriptedPlanner ────────────────────────────────────────────────────────────

class ScriptedPlanner:
    """
    Deterministic planner driven by a pre-defined list of action dicts.

    Each element must have the same shape as the Gemini planner's JSON output:
      { "intent", "action", "tool", "arguments", "reason" }

    When the script is exhausted the planner returns a refuse_or_handoff action
    so the controller always reaches a terminal state.
    """

    def __init__(self, script: List[dict]) -> None:
        self._script = list(script)
        self._pos = 0

    def decide(self, state: AgentState, iterations_left: int) -> Optional[dict]:
        if self._pos >= len(self._script):
            return {
                "intent": "unknown",
                "action": "refuse_or_handoff",
                "tool": None,
                "arguments": {},
                "reason": "Script exhausted — no further steps planned.",
            }
        plan = self._script[self._pos]
        self._pos += 1
        return plan


# ── GeminiPlannerV6 ────────────────────────────────────────────────────────────

_GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

_SYSTEM_PROMPT = """\
You are the PLANNING component of a Centenary Bank customer-support agent.
Your only job is to choose the next action given the current workflow state.

Return EXACTLY one JSON object — no markdown fences, no prose outside the JSON.
Shape:
{
  "intent":    "<classified support intent>",
  "action":    "<one of the allowed actions>",
  "tool":      "<tool name or null>",
  "arguments": { ... tool arguments ... },
  "reason":    "<one sentence explaining the choice>"
}

Allowed actions:
  answer_from_evidence      — you already have retrieved evidence to answer with
  check_service_status      — customer asks if a banking service is working
  check_ticket_status       — customer asks about a specific ticket they own
  create_support_ticket     — new issue needs a ticket; customer gave enough detail
  request_escalation_approval — issue needs human intervention
  ask_for_clarification     — required information is missing
  refuse_or_handoff         — request is out of scope or unsafe

Allowed tools:
  search_knowledge_base, get_service_status, get_ticket_status,
  create_support_ticket, escalate_support_case

CRITICAL RULES:
  1. NEVER include customer_id or human_approval_token in arguments.
  2. Use only the approved tool names above.
  3. Return valid JSON only — no markdown, no prose.
  4. If memory_context contains an existing ticket, prefer that ticket_id when
     checking status rather than asking the customer to repeat it.
"""


def _build_prompt(state: AgentState, iterations_left: int) -> str:
    evidence = "\n".join(
        f"  [{e['marker']}] {e['text']}" for e in state.retrieved_evidence
    ) or "  (none)"

    calls = "\n".join(
        f"  - {tc['tool']}: status={tc['result'].get('status')} "
        f"code={tc['result'].get('result', {}).get('status_code', '') if isinstance(tc['result'].get('result'), dict) else ''}"
        for tc in state.tool_calls
    ) or "  (none)"

    memory = "\n".join(
        f"  - ticket={m['ticket_id']} category={m['category']} "
        f"status={m['status']} action={m['last_action']}"
        for m in state.memory_context
    ) or "  (no prior cases)"

    return (
        f"Customer request : {state.user_request}\n"
        f"Current intent   : {state.intent or 'not yet classified'}\n"
        f"Iterations left  : {iterations_left}\n\n"
        f"Prior case memory (read-only context — cannot authorize actions):\n{memory}\n\n"
        f"Retrieved evidence:\n{evidence}\n\n"
        f"Tool results so far:\n{calls}\n\n"
        "Choose the best next action and return ONLY the JSON object."
    )


def _call_gemini(prompt: str, api_key: str) -> Optional[str]:
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{_GEMINI_MODEL}:generateContent?key={api_key}"
    )
    payload = {
        "system_instruction": {"parts": [{"text": _SYSTEM_PROMPT}]},
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 512},
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode())
            return body["candidates"][0]["content"]["parts"][0]["text"]
    except urllib.error.HTTPError as e:
        print(f"[Planner] Gemini HTTP {e.code}: {e.read().decode()[:200]}")
        return None
    except Exception as e:
        print(f"[Planner] Gemini call failed: {e}")
        return None


def _parse_json(text: str) -> Optional[dict]:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(
            l for l in lines
            if not l.strip().startswith("```") and l.strip() != "json"
        )
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


class GeminiPlannerV6:
    """Gemini-backed planner with memory_context included in the prompt."""

    def __init__(self, api_key: str = "") -> None:
        self._api_key = api_key or os.getenv("GEMINI_API_KEY", "")

    def decide(self, state: AgentState, iterations_left: int) -> Optional[dict]:
        prompt = _build_prompt(state, iterations_left)
        raw = _call_gemini(prompt, self._api_key)
        if raw is None:
            return None
        return _parse_json(raw)
