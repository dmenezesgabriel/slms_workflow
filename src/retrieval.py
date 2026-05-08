from __future__ import annotations

import re
from typing import Protocol

from src import context, ner, trace
from src.tools import web_fetch, web_search, wikipedia

_URL_PATTERN = re.compile(r"https?://\S+")

# Matches direct "what is X" entity lookup patterns. The negative lookahead keeps
# factual relation questions such as "what is the capital of France" from being
# routed through the proper-noun fallback as if "France" were the subject.
_WHAT_IS_RE = re.compile(
    r"\b(what\s+is(?!\s+(?:the\s+)?capital\s+of)|what\s+are|what's|"
    r"o\s+que\s+[eé]|o\s+que\s+s[aã]o)\b",
    re.IGNORECASE,
)
_PROPER_NOUN_RE = re.compile(
    r"\b([A-Za-z]*[A-Z][A-Za-z]*[A-Z][A-Za-z]*|[a-z]+[A-Z][a-zA-Z]+|[A-Z][a-z]{2,})\b"
)
_RETRIEVAL_SIGNALS = re.compile(
    r"\b(latest|current|recent|today|news|price|weather|stock|score|"
    r"winner|elected|released|launched|announced|update|version|"
    r"últimas?|atual|recente|hoje|notícias?|preço|clima|tempo|"
    r"vencedor|eleito|lançado|anunciado|atualização|versão)\b",
    re.IGNORECASE,
)
_MAX_CONTEXT_SENTENCES = 6


class Retriever(Protocol):
    """Minimal retrieval interface required by the QA handler."""

    def fetch_context(self, user_input: str) -> str:
        """Return compressed grounding context, or an empty string."""


def needs_retrieval(text: str) -> bool:
    """True when the query has temporal signals or contains a URL."""
    return (
        bool(_URL_PATTERN.search(text))
        or _RETRIEVAL_SIGNALS.search(text) is not None
        or ner.is_temporal(text)
    )


def extract_direct_what_is_entity(prompt: str) -> str | None:
    """Extract fallback entity only from direct 'what is X' prompts."""
    wi_match = _WHAT_IS_RE.search(prompt)
    if wi_match is None:
        return None
    match = _PROPER_NOUN_RE.search(prompt, wi_match.end())
    return match.group(1) if match else None


class DefaultRetriever:
    """Default adapter that isolates QA from concrete web/wiki dependencies."""

    def fetch_context(self, user_input: str) -> str:
        url_match = _URL_PATTERN.search(user_input)
        if url_match:
            trace.retrieval("web_fetch", url_match.group())
            raw = web_fetch.run({"url": url_match.group()})
            return context.compress(raw, query=user_input, max_sentences=_MAX_CONTEXT_SENTENCES)

        if _RETRIEVAL_SIGNALS.search(user_input):
            return self._fetch_time_sensitive_context(user_input)

        entity_context = self._fetch_entity_context(user_input)
        if entity_context:
            return entity_context

        candidate = extract_direct_what_is_entity(user_input)
        if candidate is None:
            return ""

        return _fetch_wikipedia_context(candidate, user_input)

    def _fetch_time_sensitive_context(self, user_input: str) -> str:
        wiki_context = _fetch_wikipedia_context(user_input, user_input)
        if wiki_context:
            return wiki_context
        return _fetch_web_search_context(user_input, user_input)

    def _fetch_entity_context(self, user_input: str) -> str:
        entities = ner.lookup_entities(user_input)
        if not entities:
            return ""

        entity_text = entities[0].text
        if ner.is_temporal(user_input):
            return _fetch_web_search_context(entity_text, user_input)

        wiki_context = _fetch_wikipedia_context(entity_text, user_input)
        if wiki_context:
            return wiki_context
        return _fetch_web_search_context(entity_text, user_input)


def _fetch_wikipedia_context(query: str, user_input: str) -> str:
    wiki = wikipedia.run({"query": query})
    if not _is_successful_wikipedia_result(wiki):
        return ""
    trace.retrieval("wikipedia", query)
    return context.compress(wiki, query=user_input, max_sentences=_MAX_CONTEXT_SENTENCES)


def _fetch_web_search_context(query: str, user_input: str) -> str:
    raw = web_search.run({"query": query, "max_results": 3})
    trace.retrieval("web_search", query)
    return context.compress(raw, query=user_input, max_sentences=_MAX_CONTEXT_SENTENCES)


def _is_successful_wikipedia_result(text: str) -> bool:
    return "No Wikipedia article" not in text and "failed" not in text.lower()


DEFAULT_RETRIEVER: Retriever = DefaultRetriever()
