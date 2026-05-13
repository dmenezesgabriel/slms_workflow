from __future__ import annotations

import re
from typing import Protocol

from src.patterns import PROPER_NOUN_RE as _PROPER_NOUN_RE
from src.patterns import RETRIEVAL_SIGNALS_RE as _RETRIEVAL_SIGNALS
from src.patterns import URL_RE as _URL_PATTERN
from src.patterns import WHAT_IS_RE as _WHAT_IS_RE
from src.techniques import ner

_WORD_TOKENS_RE = re.compile(r"[A-Za-z0-9]+")
_ACRONYM_RE = re.compile(r"\b(?:[A-Za-z]\.){2,}[A-Za-z]?\b|\b[A-Z]{3,}\b")
_NON_ALPHA_RE = re.compile(r"[^A-Za-z]")

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


class Retriever(Protocol):
    def fetch_context(self, user_input: str) -> str:
        """Return compressed grounding context, or an empty string."""


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
    match = _PROPER_NOUN_RE.search(prompt, wi_match.end())
    return match.group(1) if match else None


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
    return "No Wikipedia article" not in text and "failed" not in text.lower()
