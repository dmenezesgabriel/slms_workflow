from __future__ import annotations

import re

from pydantic import BaseModel

from src import context, trace
from src.llm_client import LLMClient, LLMRequest
from src.model_registry import MODEL_REGISTRY
from src.schemas import FinalAnswer
from src.tools import web_fetch, web_search, wikipedia

_URL_PATTERN = re.compile(r"https?://\S+")

# Matches "what is / what are / o que é" patterns used for entity lookups.
_WHAT_IS_RE = re.compile(
    r"\b(what\s+is|what\s+are|what's|o\s+que\s+[eé]|o\s+que\s+s[aã]o)\b",
    re.IGNORECASE,
)
# Likely proper-noun tokens: PascalCase compounds (FastAPI, LangChain), camelCase (spaCy),
# or simple Title-case (Docker).  The first alternative catches any word with 2+ uppercase
# letters; the second catches camelCase; the third catches plain Title-case.
_PROPER_NOUN_RE = re.compile(
    r"\b([A-Za-z]*[A-Z][A-Za-z]*[A-Z][A-Za-z]*|[a-z]+[A-Z][a-zA-Z]+|[A-Z][a-z]{2,})\b"
)

# Signals that the answer requires external or time-sensitive knowledge (en + pt).
# Kept narrow — broad question-word patterns match too many general-knowledge queries.
_RETRIEVAL_SIGNALS = re.compile(
    r"\b(latest|current|recent|today|news|price|weather|stock|score|"
    r"winner|elected|released|launched|announced|update|version|"
    r"últimas?|atual|recente|hoje|notícias?|preço|clima|tempo|"
    r"vencedor|eleito|lançado|anunciado|atualização|versão)\b",
    re.IGNORECASE,
)
_MAX_CONTEXT_SENTENCES = 6


def _needs_retrieval(text: str) -> bool:
    """True when the query has temporal signals or contains a URL."""
    from src.ner import is_temporal

    return (
        bool(_URL_PATTERN.search(text))
        or _RETRIEVAL_SIGNALS.search(text) is not None
        or is_temporal(text)
    )


def _fetch_context(user_input: str) -> str:
    from src import ner

    url_match = _URL_PATTERN.search(user_input)
    if url_match:
        trace.retrieval("web_fetch", url_match.group())
        raw = web_fetch.run({"url": url_match.group()})
        return context.compress(raw, query=user_input, max_sentences=_MAX_CONTEXT_SENTENCES)

    # Time-sensitive queries → web (Wikipedia first, DuckDuckGo fallback)
    if _RETRIEVAL_SIGNALS.search(user_input):
        wiki = wikipedia.run({"query": user_input})
        if "No Wikipedia article" not in wiki and "failed" not in wiki.lower():
            trace.retrieval("wikipedia", user_input)
            return context.compress(wiki, query=user_input, max_sentences=_MAX_CONTEXT_SENTENCES)
        trace.retrieval("web_search", user_input)
        raw = web_search.run({"query": user_input, "max_results": 3})
        return context.compress(raw, query=user_input, max_sentences=_MAX_CONTEXT_SENTENCES)

    # Entity-centric queries ("Tell me about OpenAI", "Quem é Linus Torvalds?")
    # → fetch Wikipedia for factual grounding even without temporal signals.
    entities = ner.lookup_entities(user_input)
    if entities:
        entity = entities[0]
        tool = "web_search" if ner.is_temporal(user_input) else "wikipedia"
        if tool == "wikipedia":
            wiki = wikipedia.run({"query": entity.text})
            ok = "No Wikipedia article" not in wiki and "failed" not in wiki.lower()
            if ok:
                trace.retrieval("wikipedia", entity.text)
                n = _MAX_CONTEXT_SENTENCES
                return context.compress(wiki, query=user_input, max_sentences=n)
        raw = web_search.run({"query": entity.text, "max_results": 3})
        trace.retrieval("web_search", entity.text)
        return context.compress(raw, query=user_input, max_sentences=_MAX_CONTEXT_SENTENCES)

    # Fallback: niche entities not recognized by the NER model (e.g. library/tool names).
    # Only triggers for "what is X" patterns where X looks like a proper noun.
    # Search AFTER the "what is" match to skip question-word tokens like "What".
    wi_match = _WHAT_IS_RE.search(user_input)
    if wi_match:
        m = _PROPER_NOUN_RE.search(user_input, wi_match.end())
        if m:
            candidate = m.group(1)
            wiki = wikipedia.run({"query": candidate})
            if "No Wikipedia article" not in wiki and "failed" not in wiki.lower():
                trace.retrieval("wikipedia", candidate)
                return context.compress(
                    wiki, query=user_input, max_sentences=_MAX_CONTEXT_SENTENCES
                )

    return ""


def handle(user_input: str, llm: LLMClient) -> BaseModel:
    retrieved = _fetch_context(user_input)

    user_message = f"Context:\n{retrieved}\n\nQuestion: {user_input}" if retrieved else user_input

    profile = MODEL_REGISTRY["question_answering"]
    return llm.structured(
        LLMRequest(
            model=profile.model,
            system=profile.system,
            user=user_message,
            max_tokens=profile.max_tokens,
            temperature=profile.temperature,
        ),
        FinalAnswer,
    )
