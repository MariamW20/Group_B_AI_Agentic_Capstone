"""
Planner adapter: sends context to the Gemini REST API and returns one JSON action.

Calls https://generativelanguage.googleapis.com directly with urllib so that no
SDK is required. Works on Python 3.8+.

The planner only proposes; it never executes. Identity fields (customer_id,
human_approval_token) are never in the model output — the action gate enforces
this before anything runs.
"""
from __future__ import annotations

import json
import os
import urllib.request
import urllib.error
from typing import Optional

from agent_state import AgentState

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

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

_SYSTEM_PROMPT = """\
You are the PLANNING component of a Centenary Bank customer-support agent.
Your only job is to choose the next action given the current state.

Return EXACTLY one JSON object — no markdown fences, no prose outside the JSON.
Shape:
{
  "intent":     "<classified support intent>",
  "action":     "<one of the allowed actions>",
  "tool":       "<tool name or null>",
  "arguments":  { ... tool arguments ... },
  "reason":     "<one sentence explaining the choice>"
}

Allowed actions and when to use them:
- answer_from_evidence     : you already have enough retrieved evidence to answer
- check_service_status     : customer asks whether a service is working
- check_ticket_status      : customer asks about a specific ticket they own
- create_support_ticket    : issue needs a new ticket and customer gave enough detail
- request_escalation_approval : issue needs human intervention
- ask_for_clarification    : required information is missing
- refuse_or_handoff        : request is outside scope or unsafe

Tool names (only when the action needs one):
  search_knowledge_base, get_service_status, get_ticket_status,
  create_support_ticket, escalate_support_case

CRITICAL RULES:
1. NEVER include customer_id or human_approval_token in arguments.
2. Use only the approved tool names above.
3. Return valid JSON only.
"""


def _build_prompt(state: AgentState, iterations_left: int) -> str:
    evidence = "\n".join(
        f"  [{e['marker']}] {e['text']}" for e in state.retrieved_evidence
    ) or "  (none yet)"

    calls = "\n".join(
        f"  - {tc['tool']}: status={tc['result'].get('status')} "
        f"status_code={tc['result'].get('result', {}).get('status_code') if isinstance(tc['result'].get('result'), dict) else ''}"
        for tc in state.tool_calls
    ) or "  (none yet)"

    return (
        f"Customer request : {state.user_request}\n"
        f"Current intent   : {state.intent or 'not yet classified'}\n"
        f"Iterations left  : {iterations_left}\n\n"
        f"Retrieved evidence:\n{evidence}\n\n"
        f"Earlier tool results:\n{calls}\n\n"
        "Choose the best next action and return ONLY the JSON object."
    )


def _call_gemini(prompt: str, api_key: str) -> Optional[str]:
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={api_key}"
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
        print(f"[Planner] Gemini HTTP error {e.code}: {e.read().decode()[:200]}")
        return None
    except Exception as e:
        print(f"[Planner] Gemini call failed: {e}")
        return None


def _parse_json(text: str) -> Optional[dict]:
    text = text.strip()
    # Strip markdown fences if the model added them
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(
            line for line in lines
            if not line.strip().startswith("```") and line.strip() != "json"
        )
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


class Planner:
    def __init__(self, api_key: str = ""):
        self._api_key = api_key or GEMINI_API_KEY

    def decide(self, state: AgentState, iterations_left: int) -> Optional[dict]:
        """Call Gemini and return a parsed action dict, or None on failure."""
        prompt = _build_prompt(state, iterations_left)
        raw = _call_gemini(prompt, self._api_key)
        if raw is None:
            return None
        return _parse_json(raw)
