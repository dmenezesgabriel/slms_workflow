from __future__ import annotations

import re

from pydantic import BaseModel

from app.llm_client import LLMClient, LLMRequest
from app.model_registry import MODEL_REGISTRY
from app.schemas import FinalAnswer, ToolDecision
from app.tools import TOOL_REGISTRY, execute, tool_prompt

# ── Deterministic math extraction ──────────────────────────────────────────────

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
_NL_OPS_PAT = "|".join(re.escape(k) for k in _NL_OPS)
_NL_OP_RE = re.compile(
    rf"(\d+(?:\.\d+)?)\s+({_NL_OPS_PAT})\s+(\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
_SYMBOL_RE = re.compile(r"(\d+(?:\.\d+)?)\s*([\+\-\*\/\%])\s*(\d+(?:\.\d+)?)")


def _extract_math(text: str) -> str | None:
    m = _NL_OP_RE.search(text)
    if m:
        return f"{m.group(1)} {_NL_OPS[m.group(2).lower()]} {m.group(3)}"
    m = _SYMBOL_RE.search(text)
    return f"{m.group(1)} {m.group(2)} {m.group(3)}" if m else None


# ── Deterministic tool extraction ─────────────────────────────────────────────
# Extends the same principle used for math to other tools.
# The 0.8B model reliably picks a tool name but fails to populate arguments;
# pattern matching here covers the common explicit-invocation forms so the LLM
# only handles genuinely ambiguous requests.

_SEARCH_RE = re.compile(
    r"search\s+(?:for\s+|about\s+|the\s+web\s+for\s+)(.+)",
    re.IGNORECASE,
)
_WIKI_ABOUT_RE = re.compile(
    r"wikipedia\s+(?:\w+\s+){0,3}(?:about|on|for)\s+(.+)",
    re.IGNORECASE,
)
_WIKI_LOOKUP_RE = re.compile(
    r"(?:look\s+up|find|fetch)\s+(?:the\s+)?(?:wikipedia\s+)?"
    r"(?:article|page)\s+(?:about|on|for)\s+(.+)",
    re.IGNORECASE,
)
_FETCH_RE = re.compile(r"(?:fetch|get|retrieve|open)\s+(https?://\S+)", re.IGNORECASE)


def _deterministic_tool(text: str) -> ToolDecision | None:
    m = _SEARCH_RE.search(text)
    if m:
        return ToolDecision(
            needs_tool=True,
            tool_name="web_search",
            arguments={"query": m.group(1).strip()},
            reason="Deterministic search pattern.",
        )

    m = _WIKI_ABOUT_RE.search(text) or _WIKI_LOOKUP_RE.search(text)
    if m:
        topic = re.sub(r"^(?:the|a|an)\s+", "", m.group(1).strip(), flags=re.IGNORECASE)
        return ToolDecision(
            needs_tool=True,
            tool_name="wikipedia",
            arguments={"query": topic},
            reason="Deterministic Wikipedia pattern.",
        )

    m = _FETCH_RE.search(text)
    if m:
        return ToolDecision(
            needs_tool=True,
            tool_name="web_fetch",
            arguments={"url": m.group(1).strip()},
            reason="Deterministic URL fetch pattern.",
        )

    return None


# ── System prompt (LLM fallback only) ─────────────────────────────────────────


def _build_system_prompt() -> str:
    return (
        "You select and invoke a tool to fulfill the user's request.\n"
        "Available tools:\n"
        f"{tool_prompt()}\n"
        "Return needs_tool=true and the exact tool name from the list above with its arguments.\n"
        "Return needs_tool=false and tool_name='none' when no tool applies."
    )


# ── Handler ────────────────────────────────────────────────────────────────────


def _dispatch(decision: ToolDecision) -> BaseModel:
    result = execute(decision)
    if result.success:
        return FinalAnswer(answer=f"{result.tool_name} result: {result.result}")
    return FinalAnswer(answer=f"Tool execution failed for {result.tool_name}: {result.error}")


def handle(user_input: str, llm: LLMClient) -> BaseModel:
    # Fast path 1: math expression
    expression = _extract_math(user_input)
    if expression is not None and "calculator" in TOOL_REGISTRY:
        return _dispatch(
            ToolDecision(
                needs_tool=True,
                tool_name="calculator",
                arguments={"expression": expression},
                reason="Deterministic math extraction.",
            )
        )

    # Fast path 2: explicit tool patterns (search / wikipedia / fetch)
    decision = _deterministic_tool(user_input)
    if decision is not None:
        return _dispatch(decision)

    # LLM path: model handles genuinely ambiguous or compound requests
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
