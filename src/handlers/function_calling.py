from __future__ import annotations

from pydantic import BaseModel

from src import tool_selection, trace
from src.llm_client import LLMClient, LLMRequest
from src.model_registry import MODEL_REGISTRY, ModelProfile
from src.schemas import FinalAnswer, ToolDecision
from src.tools import ToolRegistry


class FunctionCallingHandler:
    id = "function_calling"
    intent = id

    def __init__(
        self,
        tool_registry: ToolRegistry,
        profile: ModelProfile | None = None,
    ) -> None:
        self._tool_registry = tool_registry
        self._profile = profile or MODEL_REGISTRY["function_calling"]

    def _build_system_prompt(self) -> str:
        return (
            "You select and invoke a tool to fulfill the user's request.\n"
            "Available tools:\n"
            f"{self._tool_registry.prompt()}\n"
            "Return needs_tool=true and the exact tool name from the list above "
            "with its arguments.\n"
            "Return needs_tool=false and tool_name='none' when no tool applies."
        )

    def _dispatch(self, decision: ToolDecision) -> BaseModel:
        result = self._tool_registry.execute(decision)
        if result.success:
            return FinalAnswer(answer=f"{result.tool_name} result: {result.result}")
        message = "Tool execution failed for {}: {}".format(result.tool_name, result.error)
        return FinalAnswer(answer=message)

    def execute(self, input: str, llm: LLMClient) -> BaseModel:
        return self.handle(input, llm)

    def handle(self, user_input: str, llm: LLMClient) -> BaseModel:
        trace.handler("function_calling", user_input)
        expression = tool_selection.extract_math(user_input)
        if expression is not None and "calculator" in self._tool_registry:
            trace.fast_path("math_regex", expression)
            return self._dispatch(
                ToolDecision(
                    needs_tool=True,
                    tool_name="calculator",
                    arguments={"expression": expression},
                    reason="Deterministic math extraction.",
                )
            )

        decision = tool_selection.deterministic_tool(user_input)
        if decision is not None:
            trace.fast_path("regex_tool", decision.tool_name)
            return self._dispatch(decision)

        decision = tool_selection.ner_tool(user_input)
        if decision is not None:
            trace.fast_path("ner_entity", decision.tool_name)
            return self._dispatch(decision)

        decision = llm.structured(
            LLMRequest(
                model=self._profile.model,
                system=self._build_system_prompt(),
                user=user_input,
                max_tokens=self._profile.max_tokens,
                temperature=self._profile.temperature,
            ),
            ToolDecision,
        )

        if not decision.needs_tool or decision.tool_name == "none":
            return FinalAnswer(answer=decision.reason)

        return self._dispatch(decision)
