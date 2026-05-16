from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class NodeTrace:
    node_id: str
    intent: str
    input_: str
    output: str
    elapsed_ms: float
    error: str | None = None


@dataclass
class ToolCallTrace:
    tool_name: str
    arguments: dict[str, Any]
    result_summary: str
    success: bool
    elapsed_ms: float
    error: str | None = None


_MAX_OUTPUT_CHARS = 1000
_MAX_INPUT_CHARS = 500


def _truncate(value: str, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    return value[:max_chars] + "..."


def _redact_sensitive(data: dict[str, Any]) -> dict[str, Any]:
    sensitive_keys = {"secret", "token", "api_key", "password", "key", "auth"}
    result = {}
    for k, v in data.items():
        if any(s in k.lower() for s in sensitive_keys):
            result[k] = "***REDACTED***"
        elif isinstance(v, dict):
            result[k] = _redact_sensitive(v)  # type: ignore[assignment]
        elif isinstance(v, str) and len(v) > 2000:
            result[k] = v[:2000] + "..."
        else:
            result[k] = v
    return result


@dataclass
class ExecutionTrace:
    version: str = "1.0"
    run_id: str = ""
    workflow_name: str = ""
    workflow_description: str = ""
    route_strategy: str = ""
    route_confidence: float = 0.0
    nodes: dict[str, NodeTrace] = field(default_factory=dict)
    node_order: list[str] = field(default_factory=list)
    tool_calls: list[ToolCallTrace] = field(default_factory=list)
    skipped_nodes: list[dict[str, str]] = field(default_factory=list)
    final_status: str = ""
    start_time: float = 0.0
    end_time: float = 0.0
    elapsed_ms: float = 0.0
    error: str | None = None

    def add_tool_call(self, call: ToolCallTrace) -> None:
        self.tool_calls.append(call)

    def to_dict(self, redact: bool = True) -> dict[str, Any]:
        raw = asdict(self)
        if redact:
            raw = _redact_sensitive(raw)
        nodes_out = {}
        for nid, nt in raw.get("nodes", {}).items():
            nodes_out[nid] = {
                "node_id": nt["node_id"],
                "intent": nt["intent"],
                "input": _truncate(nt.get("input_", ""), _MAX_INPUT_CHARS),
                "output": _truncate(nt.get("output", ""), _MAX_OUTPUT_CHARS),
                "elapsed_ms": nt["elapsed_ms"],
                "error": nt.get("error"),
            }
        raw["nodes"] = nodes_out
        tool_calls_out = []
        for tc in raw.get("tool_calls", []):
            tool_calls_out.append(
                {
                    "tool_name": tc["tool_name"],
                    "arguments": tc.get("arguments", {}),
                    "result_summary": _truncate(tc.get("result_summary", ""), _MAX_OUTPUT_CHARS),
                    "success": tc["success"],
                    "elapsed_ms": tc["elapsed_ms"],
                    "error": tc.get("error"),
                }
            )
        raw["tool_calls"] = tool_calls_out
        skipped = []
        for s in raw.get("skipped_nodes", []):
            skipped.append(
                {
                    "node_id": s.get("node_id", ""),
                    "condition": s.get("condition", ""),
                    "reason": s.get("reason", ""),
                }
            )
        raw["skipped_nodes"] = skipped
        return raw

    def to_json(self, indent: int = 2, redact: bool = True) -> str:
        import json

        return json.dumps(
            self.to_dict(redact=redact), indent=indent, ensure_ascii=False, default=str
        )
