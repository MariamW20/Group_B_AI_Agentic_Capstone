"""
Trace recorder for the Week 6 demo.

Records one JSON array per request under evidence/traces/week6/<request_id>.json.
Each record is redacted before writing so identity and approval tokens never reach disk.
"""
from __future__ import annotations

import json
from pathlib import Path

_TRACES_DIR = Path(__file__).resolve().parents[2] / "traces" / "week6"
_REDACTED = {"customer_id", "human_approval_token"}


def _redact(obj):
    if isinstance(obj, dict):
        return {k: _redact(v) for k, v in obj.items() if k not in _REDACTED}
    if isinstance(obj, list):
        return [_redact(item) for item in obj]
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