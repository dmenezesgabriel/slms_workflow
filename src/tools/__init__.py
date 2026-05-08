from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, cast

from src import trace
from src.schemas import ToolDecision, ToolName
from src.tools import calculator, web_fetch, web_search, wikipedia


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, str]
    fn: Callable[[dict[str, Any]], str]

    def prompt_line(self) -> str:
        params = ", ".join(f"{k}: {v}" for k, v in self.parameters.items())
        return f"- {self.name}: {self.description}. Parameters: {{{params}}}"


@dataclass(frozen=True)
class ToolResult:
    success: bool
    tool_name: str
    result: str
    error: str | None = None


TOOL_ACTION_ARGUMENTS: Mapping[ToolName, str] = {
    "web_search": "query",
    "web_fetch": "url",
    "wikipedia": "query",
    "calculator": "expression",
}
TOOL_ACTIONS = frozenset(TOOL_ACTION_ARGUMENTS)


TOOL_REGISTRY: dict[str, ToolSpec] = {
    "calculator": ToolSpec(
        name="calculator",
        description="Evaluates a Python arithmetic expression safely",
        parameters={"expression": "Python arithmetic string, e.g. '3 + 4 * 2'"},
        fn=calculator.run,
    ),
    "web_search": ToolSpec(
        name="web_search",
        description="Searches the web via DuckDuckGo and returns page snippets",
        parameters={
            "query": "search query string",
            "max_results": "number of results to return (default 3, max 5)",
        },
        fn=web_search.run,
    ),
    "web_fetch": ToolSpec(
        name="web_fetch",
        description="Fetches and extracts readable text from a URL",
        parameters={"url": "full https:// URL to retrieve"},
        fn=web_fetch.run,
    ),
    "wikipedia": ToolSpec(
        name="wikipedia",
        description="Returns the introductory section of a Wikipedia article",
        parameters={"query": "article title or subject to look up"},
        fn=wikipedia.run,
    ),
}


def tool_prompt() -> str:
    """Build the tool list section for the function_calling system prompt."""
    return "\n".join(spec.prompt_line() for spec in TOOL_REGISTRY.values())


def is_tool_action(action: str) -> bool:
    """Return True when an agent action maps directly to a registered tool."""
    return action in TOOL_ACTION_ARGUMENTS


def decision_for_action(action: str, action_input: str) -> ToolDecision | None:
    """Translate an agent tool action into the stable ToolDecision interface."""
    argument_name = TOOL_ACTION_ARGUMENTS.get(cast(ToolName, action))
    if argument_name is None:
        return None
    return ToolDecision(
        needs_tool=True,
        tool_name=cast(ToolName, action),
        arguments={argument_name: action_input},
        reason="Agent tool action.",
    )


def execute(decision: ToolDecision) -> ToolResult:
    if not decision.needs_tool or decision.tool_name == "none":
        return ToolResult(success=False, tool_name="none", result="No tool needed.")

    name = decision.tool_name
    spec = TOOL_REGISTRY.get(name)
    if spec is None:
        return ToolResult(
            success=False,
            tool_name=name,
            result="",
            error=f"Unknown tool: {name}",
        )

    trace.tool_call(name, decision.arguments)
    try:
        result = spec.fn(decision.arguments)
        from src.scoring import score_result

        score = score_result(result)
        trace.tool_result(name, score.is_usable, result[:120])
        return ToolResult(
            success=score.is_usable,
            tool_name=name,
            result=result,
            error=None if score.is_usable else score.reason,
        )
    except Exception as exc:
        trace.tool_result(name, False, str(exc))
        return ToolResult(success=False, tool_name=name, result="", error=str(exc))


def execute_action(action: str, action_input: str) -> ToolResult | None:
    """Execute a direct tool action, or return None for non-tool actions."""
    decision = decision_for_action(action, action_input)
    if decision is None:
        return None
    return execute(decision)
