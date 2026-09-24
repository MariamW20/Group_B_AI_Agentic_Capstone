"""
Orchestration layer.

This is the piece that sits between "the model wants to call a tool" and
"the tool actually runs." It never trusts the caller: every request is
validated against the tool's input schema, checked against the caller's
authorization level, and -- for higher-impact tools -- checked for human
approval before execution. Every outcome (success or failure) comes back as
a structured dict with a `status`, never a raw exception leaking to the model.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any

from tools import ToolSpec


@dataclass
class CallerContext:
    """Who is making this tool call -- normally derived from the session."""
    auth_level: int
    human_approved: bool = False  # set True only once a human has explicitly approved this specific call


class ToolOrchestrator:
    def __init__(self, tools: list[ToolSpec]):
        self.registry: dict[str, ToolSpec] = {t.name: t for t in tools}

    def call(self, tool_name: str, arguments: dict[str, Any], caller: CallerContext) -> dict:
        # 1. Does the tool exist?
        spec = self.registry.get(tool_name)
        if spec is None:
            return {"status": "error", "error_type": "unknown_tool", "message": f"no such tool: {tool_name}"}

        # 2. Validate arguments against the input schema.
        validation_error = self._validate_arguments(spec, arguments)
        if validation_error:
            return {"status": "error", "error_type": "invalid_arguments", "message": validation_error}

        # 3. Authorization check.
        if caller.auth_level < spec.required_auth_level:
            return {
                "status": "error",
                "error_type": "unauthorized",
                "message": f"tool '{tool_name}' requires auth_level >= {spec.required_auth_level}, "
                           f"caller has {caller.auth_level}",
            }

        # 4. Human approval gate for higher-impact tools.
        if spec.higher_impact and not caller.human_approved:
            return {
                "status": "pending_approval",
                "message": f"tool '{tool_name}' is higher-impact and requires human approval before it runs",
                "proposed_arguments": arguments,
            }

        # 5. Execute, catching downstream failures explicitly rather than
        #    letting them propagate as raw exceptions.
        filled_args = self._apply_defaults(spec, arguments)
        try:
            result = spec.func(**filled_args)
        except Exception as e:
            return {
                "status": "error",
                "error_type": "service_unavailable",
                "message": f"{tool_name} failed while executing: {e}",
            }

        # 6. Validate the output against the schema before handing it back --
        #    catches a downstream service silently returning a malformed record.
        output_error = self._validate_output(spec, result)
        if output_error:
            return {"status": "error", "error_type": "unexpected_response", "message": output_error, "raw_result": result}

        return {"status": "success", "result": result}

    @staticmethod
    def _validate_arguments(spec: ToolSpec, arguments: dict) -> str | None:
        for field, rule in spec.input_schema.items():
            if rule.get("required") and field not in arguments:
                return f"missing required argument: '{field}'"
            if field in arguments and "enum" in rule and arguments[field] not in rule["enum"]:
                return f"'{field}' must be one of {rule['enum']}, got {arguments[field]!r}"
        unknown = set(arguments) - set(spec.input_schema)
        if unknown:
            return f"unexpected argument(s): {sorted(unknown)}"
        return None

    @staticmethod
    def _apply_defaults(spec: ToolSpec, arguments: dict) -> dict:
        filled = dict(arguments)
        for field, rule in spec.input_schema.items():
            if field not in filled and "default" in rule:
                filled[field] = rule["default"]
        return filled

    @staticmethod
    def _validate_output(spec: ToolSpec, result: dict) -> str | None:
        missing = [f for f in spec.output_schema if f not in result]
        if missing:
            return f"tool response missing required field(s): {missing}"
        return None
