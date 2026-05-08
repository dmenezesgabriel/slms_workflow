from __future__ import annotations

from pydantic import BaseModel

from src import tool_selection, trace
from src.llm_client import LLMClient, LLMRequest
from src.model_registry import MODEL_REGISTRY
from src.schemas import FinalAnswer, ToolDecision
from src.tools import TOOL_REGISTRY, execute, tool_prompt

# Module-level aliases kept for test patching compatibility.
_extract_math = tool_selection.extract_math
_deterministic_tool = tool_selection.deterministic_tool
_ner_tool = tool_selection.ner_tool


def _build_system_prompt() -> str:
    return (
        "You select and invoke a tool to fulfill the user's request.\n"
        "Available tools:\n"
        f"{tool_prompt()}\n"
        "Return needs_tool=true and the exact tool name from the list above with its arguments.\n"
        "Return needs_tool=false and tool_name='none' when no tool applies."
    )


def _dispatch(decision: ToolDecision) -> BaseModel:
    result = execute(decision)
    if result.success:
        return FinalAnswer(answer=f"{result.tool_name} result: {result.result}")
    return FinalAnswer(answer=f"Tool execution failed for {result.tool_name}: {result.error}")


def deterministic_decision(user_input: str) -> ToolDecision | None:
    """Return a ToolDecision using only deterministic paths, no LLM."""
    expression = _extract_math(user_input)
    if expression is not None and "calculator" in TOOL_REGISTRY:
        return ToolDecision(
            needs_tool=True,
            tool_name="calculator",
            arguments={"expression": expression},
            reason="Deterministic math extraction.",
        )
    return _deterministic_tool(user_input) or _ner_tool(user_input)


class FunctionCallingHandler:
    intent = "function_calling"

    def handle(self, user_input: str, llm: LLMClient) -> BaseModel:
        expression = _extract_math(user_input)
        if expression is not None and "calculator" in TOOL_REGISTRY:
            trace.fast_path("math_regex", expression)
            return _dispatch(
                ToolDecision(
                    needs_tool=True,
                    tool_name="calculator",
                    arguments={"expression": expression},
                    reason="Deterministic math extraction.",
                )
            )

        decision = _deterministic_tool(user_input)
        if decision is not None:
            trace.fast_path("regex_tool", decision.tool_name)
            return _dispatch(decision)

        decision = _ner_tool(user_input)
        if decision is not None:
            trace.fast_path("ner_entity", decision.tool_name)
            return _dispatch(decision)

        profile = MODEL_REGISTRY["function_calling"]
        decision = llm.structured(
            LLMRequest(
                model=profile.model,
                system=_build_system_prompt(),
                user=user_input,
                max_tokens=profile.max_tokens,
                temperature=profile.temperature,
            ),
            ToolDecision,
        )

        if not decision.needs_tool or decision.tool_name == "none":
            return FinalAnswer(answer=decision.reason)

        return _dispatch(decision)


_handler = FunctionCallingHandler()
handle = _handler.handle
