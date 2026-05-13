from __future__ import annotations

import re

from src.schemas import ToolDecision, ToolName
from src.techniques import ner
from src.techniques.fuzzy import normalize_query
from src.tools import TOOL_REGISTRY

# ── Deterministic math extraction ──────────────────────────────────────────────

_NL_OPS: dict[str, str] = {
    # English
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
    # Portuguese
    "mais": "+",
    "menos": "-",
    "vezes": "*",
    "multiplicado por": "*",
    "dividido por": "/",
    "elevado a": "**",
    "ao quadrado": "** 2",
}
_NL_OPS_PAT = "|".join(re.escape(k) for k in _NL_OPS)
_NL_OP_RE = re.compile(
    rf"(\d+(?:\.\d+)?)\s+({_NL_OPS_PAT})\s+(\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
_SYMBOL_RE = re.compile(r"(\d+(?:\.\d+)?)\s*([\+\-\*\/\%])\s*(\d+(?:\.\d+)?)")


def extract_math(text: str) -> str | None:
    m = _NL_OP_RE.search(text)
    if m:
        return f"{m.group(1)} {_NL_OPS[m.group(2).lower()]} {m.group(3)}"
    m = _SYMBOL_RE.search(text)
    return f"{m.group(1)} {m.group(2)} {m.group(3)}" if m else None


# ── Deterministic tool extraction ─────────────────────────────────────────────

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
_WIKI_ON_RE = re.compile(
    r"(?:look\s+up|find|search)\s+(.+?)\s+on\s+wikipedia",
    re.IGNORECASE,
)
_FETCH_RE = re.compile(r"(?:fetch|get|retrieve|open)\s+(https?://\S+)", re.IGNORECASE)


def deterministic_tool(text: str) -> ToolDecision | None:
    m = _SEARCH_RE.search(text)
    if m:
        return ToolDecision(
            needs_tool=True,
            tool_name="web_search",
            arguments={"query": m.group(1).strip()},
            reason="Deterministic search pattern.",
        )

    m = _WIKI_ABOUT_RE.search(text) or _WIKI_LOOKUP_RE.search(text) or _WIKI_ON_RE.search(text)
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


# ── NER fast path ─────────────────────────────────────────────────────────────

_LOOKUP_INTENT_RE = re.compile(
    r"\b(what|who|where|when|tell me|explain|describe|about|"
    r"o que|quem|onde|quando|sobre|explica|explique|"
    r"me\s+(?:fale?|conte?|diga?|diz|explique?))\b",
    re.IGNORECASE,
)


def ner_tool(text: str) -> ToolDecision | None:
    entities = ner.lookup_entities(text)
    if not entities:
        return None

    if not _LOOKUP_INTENT_RE.search(text):
        return None

    entity = entities[0]
    query = normalize_query(entity.text)
    tool: ToolName = "web_search" if ner.is_temporal(text) else "wikipedia"
    return ToolDecision(
        needs_tool=True,
        tool_name=tool,
        arguments={"query": query},
        reason=f"NER {entity.label}: {query!r}.",
    )


def deterministic_decision(user_input: str) -> ToolDecision | None:
    """Return a tool decision using deterministic paths only, without an LLM."""
    expression = extract_math(user_input)
    if expression is not None and "calculator" in TOOL_REGISTRY:
        return ToolDecision(
            needs_tool=True,
            tool_name="calculator",
            arguments={"expression": expression},
            reason="Deterministic math extraction.",
        )
    return deterministic_tool(user_input) or ner_tool(user_input)


def is_math_expression(text: str) -> bool:
    """Check if text contains a math expression."""
    return extract_math(text) is not None


def is_calculator_intent(text: str) -> bool:
    """Check if text indicates calculator intent."""
    expression = extract_math(text)
    return expression is not None
