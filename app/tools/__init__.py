from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app import trace
from app.schemas import ToolDecision
from app.tools import calculator, web_fetch, web_search, wikipedia


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
        from app.scoring import score_result

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
