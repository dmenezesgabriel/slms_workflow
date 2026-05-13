from __future__ import annotations

import re

from src import text_utils as context
from src import trace
from src.patterns import RECOMMENDATION_RE as _RECOMMENDATION_RE
from src.patterns import RETRIEVAL_SIGNALS_RE as _RETRIEVAL_SIGNALS
from src.patterns import URL_RE as _URL_PATTERN
from src.techniques import ner
from src.techniques.retrieval import (
    Retriever,
    _concept_search_queries,
    _is_successful_wikipedia_result,
    _reference_search_queries,
    extract_direct_what_is_entity,
)
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
_MAX_CONTEXT_SENTENCES = 6


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


def create_default_retriever() -> Retriever:
    from src.tools.web_fetch import WebFetch
    from src.tools.web_search import WebSearch
    from src.tools.wikipedia import Wikipedia

    return DefaultRetriever(
        web_fetch=WebFetch(),
        web_search=WebSearch(),
        wikipedia=Wikipedia(),
    )
