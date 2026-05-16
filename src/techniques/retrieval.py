from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

from src.lexical_scoring import best_lexical_match
from src.patterns import PROPER_NOUN_RE as _PROPER_NOUN_RE
from src.patterns import RECOMMENDATION_RE as _RECOMMENDATION_RE
from src.patterns import RETRIEVAL_SIGNALS_RE as _RETRIEVAL_SIGNALS
from src.patterns import URL_RE as _URL_PATTERN
from src.patterns import WHAT_IS_RE as _WHAT_IS_RE
from src.techniques import ner
from src.text_normalization import normalize_lookup_query, normalize_text, tokenize

_WORD_TOKENS_RE = re.compile(r"[A-Za-z0-9]+")
_ACRONYM_RE = re.compile(r"\b(?:[A-Za-z]\.){2,}[A-Za-z]?\b|\b[A-Z]{3,}\b")
_NON_ALPHA_RE = re.compile(r"[^A-Za-z]")
_REFERENCE_LOOKUP_RE = re.compile(
    r"\b(?:which|what|who|where|quando|qual|que)\b.*"
    r"\b(?:movie|film|book|song|quote|says|said|called|reference|meme|"
    r"filme|livro|música|frase|cita(?:ção|cao)|diz|disse|refer[eê]ncia)\b|"
    r"\b(?:movie|film|book|song|quote|reference|meme|filme|livro|música|frase)\b.*"
    r"\b(?:which|what|who|where|qual|que)\b",
    re.IGNORECASE,
)
_CONCEPT_EXPLANATION_RE = re.compile(
    r"\b(?:explain|explique|explica|what\s+are|o\s+que\s+s[aã]o)\b.*"
    r"\b(?:principles|principles?|princ[ií]pios|patterns|conceitos)\b",
    re.IGNORECASE,
)
_PROGRAMMING_LANGUAGE_RE = re.compile(r"\bprogramming language\b", re.IGNORECASE)
_CREATOR_RELEASE_RE = re.compile(
    r"\b(?:who\s+created|created\s+the|first\s+released|when\s+was\s+it\s+first\s+released)\b",
    re.IGNORECASE,
)

_REFERENCE_STOPWORDS = {
    "which",
    "what",
    "who",
    "where",
    "movie",
    "film",
    "book",
    "song",
    "quote",
    "says",
    "said",
    "that",
    "the",
    "qual",
    "filme",
    "livro",
    "frase",
}

_REFERENCE_PROTOTYPES = (
    "which song says",
    "what movie is this quote from",
    "which book has this quote",
    "qual filme tem essa frase",
)
_CONCEPT_PROTOTYPES = (
    "explain the principles",
    "what are the principles",
    "explique os principios",
    "explain the patterns",
)


class Retriever(Protocol):
    def fetch_context(self, user_input: str) -> str:
        """Return compressed grounding context, or an empty string."""


@dataclass(frozen=True)
class RetrievalPlan:
    strategy: str
    score: float
    query: str | None = None


def needs_retrieval(text: str) -> bool:
    return (
        bool(_URL_PATTERN.search(text))
        or _RETRIEVAL_SIGNALS.search(text) is not None
        or ner.is_temporal(text)
    )


def extract_direct_what_is_entity(prompt: str) -> str | None:
    wi_match = _WHAT_IS_RE.search(prompt)
    if wi_match is None:
        return None

    proper_match = _PROPER_NOUN_RE.search(prompt, wi_match.end())
    if proper_match:
        return proper_match.group(1)

    tail = prompt[wi_match.end() :].strip(" .,!?:;\n\t")
    if not tail:
        return None
    normalized_tail = normalize_text(tail, strip_punctuation=True)
    blocked_prefixes = (
        "the capital of",
        "capital of",
        "the price of",
        "price of",
        "the weather",
        "weather",
    )
    if any(normalized_tail.startswith(prefix) for prefix in blocked_prefixes):
        return None

    tokens = tokenize(tail)
    if not tokens or len(tokens) > 3:
        return None
    if tokens[0] in {"the", "a", "an", "o", "a", "os", "as", "um", "uma"}:
        return None
    return normalize_lookup_query(tail)


def _concept_search_queries(user_input: str) -> list[str]:
    queries = [user_input]
    acronym_match = _ACRONYM_RE.search(user_input)
    if acronym_match:
        acronym = _NON_ALPHA_RE.sub("", acronym_match.group()).upper()
        queries.append(f"{acronym} stands for principles")
    return queries


def _reference_search_queries(user_input: str) -> list[str]:
    clue_terms = [
        token
        for token in _WORD_TOKENS_RE.findall(user_input.lower())
        if (len(token) > 2 or token.isdigit()) and token not in _REFERENCE_STOPWORDS
    ]
    clue_query = " ".join(clue_terms + ["quote", "source"])
    queries = [user_input]
    if clue_query and clue_query.lower() != user_input.lower():
        queries.append(clue_query)
    return queries


def _is_successful_wikipedia_result(text: str) -> bool:
    normalized = normalize_text(text, strip_punctuation=True)
    failure_markers = (
        "no wikipedia article",
        "failed",
        "error",
        "not found",
        "disambiguation page",
    )
    return bool(normalized) and not any(marker in normalized for marker in failure_markers)


def plan_retrieval(user_input: str) -> RetrievalPlan:
    url_match = _URL_PATTERN.search(user_input)
    if url_match:
        return RetrievalPlan(strategy="url_fetch", score=1.0, query=url_match.group())

    normalized = normalize_text(user_input, strip_punctuation=True)
    candidates: list[RetrievalPlan] = []

    if _RETRIEVAL_SIGNALS.search(user_input) or ner.is_temporal(user_input):
        candidates.append(RetrievalPlan(strategy="time_sensitive", score=0.98, query=user_input))

    if _REFERENCE_LOOKUP_RE.search(user_input):
        lexical = best_lexical_match(normalized, list(_REFERENCE_PROTOTYPES))
        score = 0.75 if lexical is None else max(0.75, lexical.score)
        candidates.append(RetrievalPlan(strategy="reference_lookup", score=score, query=user_input))

    if _RECOMMENDATION_RE.search(user_input):
        candidates.append(
            RetrievalPlan(strategy="recommendation_lookup", score=0.78, query=user_input)
        )

    if _CONCEPT_EXPLANATION_RE.search(user_input):
        lexical = best_lexical_match(normalized, list(_CONCEPT_PROTOTYPES))
        score = 0.8 if lexical is None else max(0.8, lexical.score)
        candidates.append(RetrievalPlan(strategy="concept_lookup", score=score, query=user_input))

    entity = ner.best_lookup_entity(user_input)
    if entity is not None:
        score = 0.72
        if _PROGRAMMING_LANGUAGE_RE.search(user_input):
            score = 0.77
        candidates.append(RetrievalPlan(strategy="entity_lookup", score=score, query=entity.text))

    direct_entity = extract_direct_what_is_entity(user_input)
    if direct_entity is not None:
        candidates.append(RetrievalPlan(strategy="direct_what_is", score=0.85, query=direct_entity))

    if not candidates:
        return RetrievalPlan(strategy="none", score=0.0, query=None)
    return max(candidates, key=lambda candidate: candidate.score)
