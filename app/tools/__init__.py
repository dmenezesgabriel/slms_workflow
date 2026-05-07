from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.schemas import ToolDecision
from app.tools import calculator
from app import trace


@dataclass(frozen=True)
class ToolResult:
    success: bool
    tool_name: str
    result: str
    error: str | None = None


TOOL_REGISTRY: dict[str, Callable[[dict[str, Any]], str]] = {
    "calculator": calculator.run,
}


def execute(decision: ToolDecision) -> ToolResult:
    if not decision.needs_tool:
        return ToolResult(success=False, tool_name="none", result="No tool needed.")

    tool = TOOL_REGISTRY.get(decision.tool_name or "")
    if tool is None:
        return ToolResult(
            success=False,
            tool_name=decision.tool_name or "unknown",
            result="",
            error=f"Unknown tool: {decision.tool_name}",
        )

    trace.tool_call(decision.tool_name, decision.arguments)
    try:
        result = tool(decision.arguments)
        trace.tool_result(decision.tool_name, True, result)
        return ToolResult(success=True, tool_name=decision.tool_name, result=result)
    except Exception as exc:
        trace.tool_result(decision.tool_name, False, str(exc))
        return ToolResult(
            success=False,
            tool_name=decision.tool_name,
            result="",
            error=str(exc),
        )
