from __future__ import annotations

import re
from dataclasses import dataclass

from src.lexical_scoring import combined_lexical_score
from src.schemas import ToolDecision, ToolName
from src.techniques import ner
from src.techniques.fuzzy import normalize_query
from src.text_normalization import normalize_text
from src.tools import ToolRegistry

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

_FETCH_RE = re.compile(r"(?:fetch|get|retrieve|open)\s+(https?://\S+)", re.IGNORECASE)

_SEARCH_PATTERNS = (
    re.compile(r"search\s+(?:for\s+|about\s+|the\s+web\s+for\s+)(.+)", re.IGNORECASE),
    re.compile(r"(?:pesquise|procure|busque)\s+por\s+(.+)", re.IGNORECASE),
)

_WIKIPEDIA_PATTERNS = (
    re.compile(r"wikipedia\s+(?:\w+\s+){0,3}(?:about|on|for)\s+(.+)", re.IGNORECASE),
    re.compile(
        r"(?:look\s+up|find|fetch)\s+(?:the\s+)?(?:wikipedia\s+)?"
        r"(?:article|page)\s+(?:about|on|for)\s+(.+)",
        re.IGNORECASE,
    ),
    re.compile(r"(?:look\s+up|find|search)\s+(.+?)\s+on\s+wikipedia", re.IGNORECASE),
    re.compile(
        r"(?:me\s+fale\s+sobre|me\s+conte\s+sobre|me\s+diga\s+sobre|o\s+que\s+e|quem\s+e)\s+(.+)",
        re.IGNORECASE,
    ),
)

_TOOL_INTENT_PROTOTYPES: dict[ToolName, tuple[str, ...]] = {
    "web_search": (
        "search the web for python decorators",
        "search for python decorators",
        "latest news about openai",
        "pesquise por python decorators",
        "procure por noticias recentes sobre openai",
    ),
    "wikipedia": (
        "look up the wikipedia article about Ada Lovelace",
        "tell me about OpenAI",
        "what is spaCy",
        "me fale sobre OpenAI",
        "o que e spaCy",
        "quem e Ada Lovelace",
    ),
    "web_fetch": (
        "fetch https://example.com/docs",
        "open https://example.com",
        "retrieve https://example.com/reference",
    ),
    "calculator": (
        "what is 3 plus 5",
        "calculate 10 divided by 2",
        "quanto e 3 mais 5",
    ),
    "none": (),
    "playwright": (),
    "duckdb": (),
}

_LOOKUP_WORDS_RE = re.compile(
    r"^(?:tell me about|what is|who is|who was|explain|describe|about|"
    r"me\s+fale\s+sobre|me\s+conte\s+sobre|me\s+diga\s+sobre|"
    r"o\s+que\s+e|quem\s+e|quem\s+foi)\s+",
    re.IGNORECASE,
)

_LOOKUP_INTENT_RE = re.compile(
    r"\b(what|who|where|when|tell me|explain|describe|about|"
    r"o que|quem|onde|quando|sobre|explica|explique|"
    r"me\s+(?:fale?|conte?|diga?|diz|explique?))\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ToolCandidate:
    decision: ToolDecision
    score: float
    source: str


def _intent_score(text: str, tool_name: ToolName) -> float:
    prototypes = _TOOL_INTENT_PROTOTYPES.get(tool_name, ())
    if not prototypes:
        return 0.0
    return max(combined_lexical_score(text, prototype).score for prototype in prototypes)


def _extract_with_patterns(text: str, patterns: tuple[re.Pattern[str], ...]) -> str | None:
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            return match.group(1).strip()
    return None


def _search_candidate(text: str) -> ToolCandidate | None:
    query = _extract_with_patterns(text, _SEARCH_PATTERNS)
    if query is None:
        return None
    score = min(1.0, 0.70 + (0.30 * _intent_score(text, "web_search")))
    return ToolCandidate(
        decision=ToolDecision(
            needs_tool=True,
            tool_name="web_search",
            arguments={"query": query},
            reason="Scored search pattern match.",
        ),
        score=score,
        source="search_pattern",
    )


def _wikipedia_candidate(text: str) -> ToolCandidate | None:
    topic = _extract_with_patterns(text, _WIKIPEDIA_PATTERNS)
    if topic is None:
        return None
    query = normalize_query(topic)
    if not query:
        return None
    score = min(1.0, 0.68 + (0.32 * _intent_score(text, "wikipedia")))
    return ToolCandidate(
        decision=ToolDecision(
            needs_tool=True,
            tool_name="wikipedia",
            arguments={"query": query},
            reason="Scored Wikipedia lookup pattern.",
        ),
        score=score,
        source="wikipedia_pattern",
    )


def _fetch_candidate(text: str) -> ToolCandidate | None:
    match = _FETCH_RE.search(text)
    if match is None:
        return None
    return ToolCandidate(
        decision=ToolDecision(
            needs_tool=True,
            tool_name="web_fetch",
            arguments={"url": match.group(1).strip()},
            reason="Deterministic URL fetch pattern.",
        ),
        score=1.0,
        source="fetch_pattern",
    )


def _ranked_candidates(candidates: list[ToolCandidate]) -> list[ToolCandidate]:
    return sorted(candidates, key=lambda candidate: candidate.score, reverse=True)


def _best_candidate(candidates: list[ToolCandidate]) -> ToolDecision | None:
    if not candidates:
        return None
    return _ranked_candidates(candidates)[0].decision


def deterministic_tool(text: str) -> ToolDecision | None:
    candidates = [
        candidate
        for candidate in (
            _search_candidate(text),
            _wikipedia_candidate(text),
            _fetch_candidate(text),
        )
        if candidate is not None
    ]
    return _best_candidate(candidates)


# ── NER fast path ─────────────────────────────────────────────────────────────


def _entity_subject_score(text: str, entity_text: str) -> float:
    normalized_text = normalize_text(text, strip_punctuation=True)
    normalized_entity = normalize_text(entity_text, strip_punctuation=True)
    stripped_text = _LOOKUP_WORDS_RE.sub("", normalized_text)
    return combined_lexical_score(stripped_text or normalized_text, normalized_entity).score


def _ner_candidate(text: str) -> ToolCandidate | None:
    entities = ner.lookup_entities(text)
    if not entities or not _LOOKUP_INTENT_RE.search(text):
        return None

    entity = ner.best_lookup_entity(text, entities)
    if entity is None:
        return None

    query = normalize_query(entity.text)
    tool: ToolName = "web_search" if ner.is_temporal(text) else "wikipedia"
    intent_score = _intent_score(text, tool)
    subject_score = _entity_subject_score(text, entity.text)
    score = max(intent_score, subject_score)
    if score < 0.35:
        return None
    return ToolCandidate(
        decision=ToolDecision(
            needs_tool=True,
            tool_name=tool,
            arguments={"query": query},
            reason=f"NER {entity.label}: {query!r}.",
        ),
        score=min(1.0, 0.45 + (0.30 * intent_score) + (0.25 * subject_score)),
        source="ner_lookup",
    )


def ner_tool(text: str) -> ToolDecision | None:
    candidate = _ner_candidate(text)
    return None if candidate is None else candidate.decision


def rank_tool_candidates(user_input: str, tool_registry: ToolRegistry) -> list[ToolCandidate]:
    """Return scored deterministic candidates sorted best-first."""
    candidates: list[ToolCandidate] = []
    expression = extract_math(user_input)
    if expression is not None and "calculator" in tool_registry:
        candidates.append(
            ToolCandidate(
                decision=ToolDecision(
                    needs_tool=True,
                    tool_name="calculator",
                    arguments={"expression": expression},
                    reason="Deterministic math extraction.",
                ),
                score=1.0,
                source="math_pattern",
            )
        )
    candidates.extend(
        candidate
        for candidate in (
            _search_candidate(user_input),
            _wikipedia_candidate(user_input),
            _fetch_candidate(user_input),
            _ner_candidate(user_input),
        )
        if candidate is not None
    )
    return _ranked_candidates(candidates)


def deterministic_decision(user_input: str, tool_registry: ToolRegistry) -> ToolDecision | None:
    """Return a tool decision using deterministic paths only, without an LLM."""
    ranked = rank_tool_candidates(user_input, tool_registry)
    return None if not ranked else ranked[0].decision


def is_math_expression(text: str) -> bool:
    """Check if text contains a math expression."""
    return extract_math(text) is not None


def is_calculator_intent(text: str) -> bool:
    """Check if text indicates calculator intent."""
    expression = extract_math(text)
    return expression is not None
