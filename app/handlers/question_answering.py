from __future__ import annotations

import re

from pydantic import BaseModel

from app import context, trace
from app.llm_client import LLMClient, LLMRequest
from app.model_registry import MODEL_REGISTRY
from app.schemas import FinalAnswer
from app.tools import web_fetch, web_search, wikipedia

_URL_PATTERN = re.compile(r"https?://\S+")

# Signals that the answer requires external or time-sensitive knowledge.
# Kept narrow and specific — broad question-word patterns ("what is", "who is")
# match too many general-knowledge queries that the model handles fine on its own.
_RETRIEVAL_SIGNALS = re.compile(
    r"\b(latest|current|recent|today|news|price|weather|stock|score|"
    r"winner|elected|released|launched|announced|update|version)\b",
    re.IGNORECASE,
)
_MAX_CONTEXT_SENTENCES = 6


def _fetch_context(user_input: str) -> str:
    url_match = _URL_PATTERN.search(user_input)
    if url_match:
        trace.retrieval("web_fetch", url_match.group())
        raw = web_fetch.run({"url": url_match.group()})
        return context.compress(raw, query=user_input, max_sentences=_MAX_CONTEXT_SENTENCES)

    if _RETRIEVAL_SIGNALS.search(user_input):
        wiki = wikipedia.run({"query": user_input})
        if "No Wikipedia article" not in wiki and "failed" not in wiki.lower():
            trace.retrieval("wikipedia", user_input)
            return context.compress(wiki, query=user_input, max_sentences=_MAX_CONTEXT_SENTENCES)

        trace.retrieval("web_search", user_input)
        raw = web_search.run({"query": user_input, "max_results": 3})
        return context.compress(raw, query=user_input, max_sentences=_MAX_CONTEXT_SENTENCES)

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
