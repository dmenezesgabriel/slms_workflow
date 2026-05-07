from __future__ import annotations

import re

from pydantic import BaseModel

from app.llm_client import LLMClient, LLMRequest
from app.model_registry import MODEL_REGISTRY
from app.schemas import FinalAnswer, ToolDecision
from app.tools import execute

# Natural-language → Python operator mapping
_NL_OPS: dict[str, str] = {
    "plus": "+",
    "minus": "-",
    "times": "*",
    "multiplied by": "*",
    "divided by": "/",
    "over": "/",
    "mod": "%",
    "modulo": "%",
    "to the power of": "**",
    "squared": "** 2",
}

_NL_OP_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s+(" + "|".join(re.escape(k) for k in _NL_OPS) + r")\s+(\d+(?:\.\d+)?)",
    re.IGNORECASE,
)

_SYMBOL_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*([\+\-\*\/\%])\s*(\d+(?:\.\d+)?)")


def _extract_expression(text: str) -> str | None:
    """Return a Python math expression from natural-language text, or None if not found."""
    m = _NL_OP_PATTERN.search(text)
    if m:
        left, op_str, right = m.group(1), m.group(2).lower(), m.group(3)
        return f"{left} {_NL_OPS[op_str]} {right}"

    m = _SYMBOL_PATTERN.search(text)
    if m:
        return f"{m.group(1)} {m.group(2)} {m.group(3)}"

    return None


def handle(user_input: str, llm: LLMClient) -> BaseModel:
    # Fast path: extract math expression without an LLM call
    expression = _extract_expression(user_input)
    if expression is not None:
        decision = ToolDecision(
            needs_tool=True,
            tool_name="calculator",
            arguments={"expression": expression},
            reason="Deterministic math extraction.",
        )
        result = execute(decision)
        if result.success:
            return FinalAnswer(answer=f"calculator result: {result.result}")
        return FinalAnswer(answer=f"Calculator error: {result.error}")

    # LLM path: complex or ambiguous tool requests
    profile = MODEL_REGISTRY["function_calling"]
    decision = llm.structured(
        LLMRequest(
            model=profile.model,
            system=profile.system,
            user=user_input,
            max_tokens=profile.max_tokens,
            temperature=profile.temperature,
        ),
        ToolDecision,
    )

    if not decision.needs_tool:
        return FinalAnswer(answer=decision.reason)

    result = execute(decision)

    if result.success:
        return FinalAnswer(answer=f"{result.tool_name} result: {result.result}")

    return FinalAnswer(answer=f"Tool execution failed for {result.tool_name}: {result.error}")
