from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Mapping, Sequence, cast

from src import trace
from src.schemas import ToolDecision, ToolName
from src.tools.base import Tool
from src.tools.calculator import Calculator
from src.tools.duckdb import DuckDBTool
from src.tools.playwright import PlaywrightTool
from src.tools.web_fetch import WebFetch
from src.tools.web_search import WebSearch
from src.tools.wikipedia import Wikipedia


@dataclass(frozen=True)
class ToolResult:
    success: bool
    tool_name: str
    result: str
    error: str | None = None


class ToolRegistry:
    _ACTION_ARGUMENTS: ClassVar[Mapping[ToolName, str]] = {
        "web_search": "query",
        "web_fetch": "url",
        "wikipedia": "query",
        "calculator": "expression",
        "playwright": "action",
        "duckdb": "query",
    }

    def __init__(self, tools: Sequence[Tool]) -> None:
        self._tools: dict[str, Tool] = {t.name: t for t in tools}

    def __contains__(self, name: object) -> bool:
        return name in self._tools

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def prompt(self) -> str:
        return "\n".join(t.prompt_line() for t in self._tools.values())

    def is_action(self, action: str) -> bool:
        return action in self._ACTION_ARGUMENTS

    def decision_for_action(self, action: str, action_input: str) -> ToolDecision | None:
        argument_name = self._ACTION_ARGUMENTS.get(cast(ToolName, action))
        if argument_name is None:
            return None
        return ToolDecision(
            needs_tool=True,
            tool_name=cast(ToolName, action),
            arguments={argument_name: action_input},
            reason="Agent tool action.",
        )

    def execute(self, decision: ToolDecision) -> ToolResult:
        if not decision.needs_tool or decision.tool_name == "none":
            return ToolResult(success=False, tool_name="none", result="No tool needed.")

        tool = self._tools.get(decision.tool_name)
        if tool is None:
            return ToolResult(
                success=False,
                tool_name=decision.tool_name,
                result="",
                error=f"Unknown tool: {decision.tool_name}",
            )

        trace.tool_call(decision.tool_name, decision.arguments)
        try:
            result = tool.execute(decision.arguments)
            from src.scoring import score_result

            score = score_result(result)
            trace.tool_result(decision.tool_name, score.is_usable, result[:120])
            return ToolResult(
                success=score.is_usable,
                tool_name=decision.tool_name,
                result=result,
                error=None if score.is_usable else score.reason,
            )
        except Exception as exc:
            trace.tool_result(decision.tool_name, False, str(exc))
            return ToolResult(
                success=False, tool_name=decision.tool_name, result="", error=str(exc)
            )

    def execute_action(self, action: str, action_input: str) -> ToolResult | None:
        decision = decision_for_action(action, action_input)
        if decision is None:
            return None
        return execute(decision)


TOOL_REGISTRY = ToolRegistry(
    [
        Calculator(),
        WebSearch(),
        WebFetch(),
        Wikipedia(),
        PlaywrightTool(),
        DuckDBTool(),
    ]
)

# Module-level public API — callers and tests use these names directly.
# execute_action deliberately calls the module-level execute so monkeypatching
# src.tools.execute in tests also affects execute_action.

TOOL_ACTIONS = frozenset(ToolRegistry._ACTION_ARGUMENTS)


def execute(decision: ToolDecision) -> ToolResult:
    return TOOL_REGISTRY.execute(decision)


def execute_action(action: str, action_input: str) -> ToolResult | None:
    decision = decision_for_action(action, action_input)
    if decision is None:
        return None
    return execute(decision)


def is_tool_action(action: str) -> bool:
    return TOOL_REGISTRY.is_action(action)


def tool_prompt() -> str:
    return TOOL_REGISTRY.prompt()


def decision_for_action(action: str, action_input: str) -> ToolDecision | None:
    return TOOL_REGISTRY.decision_for_action(action, action_input)
