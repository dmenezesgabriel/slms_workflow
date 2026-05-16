from __future__ import annotations

from src import text_utils as context
from src import trace
from src.techniques import ner
from src.techniques.retrieval import (
    Retriever,
    _concept_search_queries,
    _is_successful_wikipedia_result,
    _reference_search_queries,
    plan_retrieval,
)
from src.tools.base import Tool

_MAX_CONTEXT_SENTENCES = 6


class DefaultRetriever:
    def __init__(self, web_fetch: Tool, web_search: Tool, wikipedia: Tool) -> None:
        self._web_fetch = web_fetch
        self._web_search = web_search
        self._wikipedia = wikipedia

    def fetch_context(self, user_input: str) -> str:
        plan = plan_retrieval(user_input)

        if plan.strategy == "url_fetch" and plan.query is not None:
            trace.retrieval("web_fetch", plan.query)
            raw = self._web_fetch.execute({"url": plan.query})
            return context.compress(raw, query=user_input, max_sentences=_MAX_CONTEXT_SENTENCES)

        if plan.strategy == "time_sensitive":
            return self._fetch_time_sensitive(user_input)
        if plan.strategy == "reference_lookup":
            return self._fetch_reference(user_input)
        if plan.strategy == "recommendation_lookup":
            return self._fetch_recommendation(user_input)
        if plan.strategy == "concept_lookup":
            return self._fetch_concept(user_input)
        if plan.strategy == "entity_lookup":
            return self._fetch_entity(user_input)
        if plan.strategy == "direct_what_is" and plan.query is not None:
            return self._fetch_wikipedia(plan.query, user_input)
        return ""

    def _fetch_time_sensitive(self, user_input: str) -> str:
        wiki = self._fetch_wikipedia(user_input, user_input)
        if wiki:
            return wiki
        return self._fetch_web_search(user_input, user_input)

    def _fetch_entity(self, user_input: str) -> str:
        entity = ner.best_lookup_entity(user_input)
        if entity is None:
            return ""
        entity_text = entity.text
        if ner.is_temporal(user_input):
            return self._fetch_web_search(entity_text, user_input)
        if (
            plan_retrieval(user_input).strategy == "entity_lookup"
            and "programming language" in user_input.lower()
        ):
            if "created" in user_input.lower() or "first released" in user_input.lower():
                return self._fetch_web_search(
                    f"{entity_text} programming language creator first released",
                    user_input,
                )
            wiki = self._fetch_wikipedia(f"{entity_text} programming language", user_input)
            if wiki:
                return wiki
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
        parts = [self._run_search(q, max_results=5) for q in queries]
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
