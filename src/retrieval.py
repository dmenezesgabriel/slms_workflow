from __future__ import annotations

import re
from typing import Protocol

from src import context, ner, trace
from src.patterns import PROPER_NOUN_RE as _PROPER_NOUN_RE
from src.patterns import RECOMMENDATION_RE as _RECOMMENDATION_RE
from src.patterns import RETRIEVAL_SIGNALS_RE as _RETRIEVAL_SIGNALS
from src.patterns import URL_RE as _URL_PATTERN
from src.patterns import WHAT_IS_RE as _WHAT_IS_RE
from src.rag import store_retrieval_results
from src.tools.base import Tool

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
_MAX_CONTEXT_SENTENCES = 6


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


class DefaultRetriever:
    def __init__(self, web_fetch: Tool, web_search: Tool, wikipedia: Tool) -> None:
        self._web_fetch = web_fetch
        self._web_search = web_search
        self._wikipedia = wikipedia

    def fetch_context(self, user_input: str) -> str:
        url_match = _URL_PATTERN.search(user_input)
        if url_match:
            trace.retrieval("web_fetch", url_match.group())
            raw = self._web_fetch.execute({"url": url_match.group()})
            store_retrieval_results([raw], ["web_fetch"])
            return context.compress(raw, query=user_input, max_sentences=_MAX_CONTEXT_SENTENCES)

        if _RETRIEVAL_SIGNALS.search(user_input):
            return self._fetch_time_sensitive(user_input)

        if _REFERENCE_LOOKUP_RE.search(user_input):
            return self._fetch_reference(user_input)

        if _RECOMMENDATION_RE.search(user_input):
            return self._fetch_recommendation(user_input)

        if _CONCEPT_EXPLANATION_RE.search(user_input):
            return self._fetch_concept(user_input)

        entity_context = self._fetch_entity(user_input)
        if entity_context:
            return entity_context

        candidate = extract_direct_what_is_entity(user_input)
        if candidate is None:
            return ""

        return self._fetch_wikipedia(candidate, user_input)

    def _fetch_time_sensitive(self, user_input: str) -> str:
        wiki = self._fetch_wikipedia(user_input, user_input)
        if wiki:
            return wiki
        return self._fetch_web_search(user_input, user_input)

    def _fetch_entity(self, user_input: str) -> str:
        entities = ner.lookup_entities(user_input)
        if not entities:
            return ""
        entity_text = entities[0].text
        if ner.is_temporal(user_input):
            return self._fetch_web_search(entity_text, user_input)
        wiki = self._fetch_wikipedia(entity_text, user_input)
        if wiki:
            return wiki
        return self._fetch_web_search(entity_text, user_input)

    def _fetch_wikipedia(self, query: str, user_input: str) -> str:
        wiki = self._wikipedia.execute({"query": query})
        if not _is_successful_wikipedia_result(wiki):
            return ""
        trace.retrieval("wikipedia", query)
        return context.compress(wiki, query=user_input, max_sentences=_MAX_CONTEXT_SENTENCES)

    def _fetch_web_search(self, query: str, user_input: str) -> str:
        raw = self._run_search(query, max_results=3)
        return context.compress(raw, query=user_input, max_sentences=_MAX_CONTEXT_SENTENCES)

    def _run_search(self, query: str, max_results: int) -> str:
        raw = self._web_search.execute({"query": query, "max_results": max_results})
        trace.retrieval("web_search", query)
        return raw

    def _fetch_concept(self, user_input: str) -> str:
        raw = "\n\n".join(
            self._run_search(q, max_results=5) for q in _concept_search_queries(user_input)
        )
        return context.compress(raw, query=user_input, max_sentences=10)

    def _fetch_recommendation(self, user_input: str) -> str:
        raw = "\n\n".join(
            [
                self._run_search(user_input, max_results=3),
                self._run_search(f"beginner recommendation {user_input}", max_results=3),
            ]
        )
        return context.compress(raw, query=user_input, max_sentences=8)

    def _fetch_reference(self, user_input: str) -> str:
        queries = _reference_search_queries(user_input)
        parts: list[str] = []

        # Numbers in reference queries often map to Wikipedia articles that name the
        # cultural work (e.g. "42" → "42 (number)" which names Hitchhiker's Guide).
        numeric_clues = [
            t for t in _WORD_TOKENS_RE.findall(user_input) if t.isdigit() and len(t) >= 2
        ]
        for num in numeric_clues[:1]:
            wiki_raw = self._wikipedia.execute({"query": num})
            if _is_successful_wikipedia_result(wiki_raw):
                trace.retrieval("wikipedia", num)
                parts.append(wiki_raw)

        parts.extend(self._run_search(q, max_results=5) for q in queries)
        combined = "\n\n".join(filter(None, parts))
        return context.compress(combined, query=user_input, max_sentences=8)


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


# Module-level singleton using concrete tool implementations
from src.tools.web_fetch import WebFetch  # noqa: E402
from src.tools.web_search import WebSearch  # noqa: E402
from src.tools.wikipedia import Wikipedia  # noqa: E402

DEFAULT_RETRIEVER: Retriever = DefaultRetriever(
    web_fetch=WebFetch(),
    web_search=WebSearch(),
    wikipedia=Wikipedia(),
)
