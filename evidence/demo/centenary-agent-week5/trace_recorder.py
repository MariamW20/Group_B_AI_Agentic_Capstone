"""
Trace recorder: appends one JSON record per iteration to
evidence/traces/week5/<request_id>.json.

The file is a JSON array; each element is one iteration record plus one
final record at stop. Identity and token fields are always redacted.
"""
from __future__ import annotations

import json
from pathlib import Path

_TRACES_DIR = Path(__file__).resolve().parents[2] / "traces" / "week5"
_REDACTED = {"customer_id", "human_approval_token"}


def _redact(obj):
    """Recursively remove protected fields from a dict so they never reach disk."""
    if isinstance(obj, dict):
        return {k: _redact(v) for k, v in obj.items() if k not in _REDACTED}
    if isinstance(obj, list):
        return [_redact(i) for i in obj]
    return obj


def append_trace(request_id: str, record: dict) -> None:
    _TRACES_DIR.mkdir(parents=True, exist_ok=True)
    path = _TRACES_DIR / f"{request_id}.json"
    records = []
    if path.exists():
        try:
            records = json.loads(path.read_text())
        except Exception:
            records = []
    records.append(_redact(record))
    path.write_text(json.dumps(records, indent=2))
