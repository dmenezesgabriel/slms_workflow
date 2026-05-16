from __future__ import annotations

import re
from typing import Final

from pydantic import BaseModel

from src import trace
from src.lexical_scoring import best_lexical_match
from src.llm_client import LLMClient, LLMRequest
from src.model_registry import MODEL_REGISTRY, ModelProfile
from src.schemas import FinalAnswer, SummaryResult
from src.text_normalization import tokenize

_TRIGGER_PREFIX = re.compile(
    r"^(?:(?:summarize|summary|tl;dr|resuma|resumo)(?:[:\s]+|$))",
    re.IGNORECASE,
)
_MIN_CONTENT_WORDS = 10
_MIN_INFORMATIVE_TOKENS = 3
_MIN_SHORT_CONTENT_CHARS = 12
_CONTENTLESS_MATCH_THRESHOLD = 0.72
_GENERIC_CONTENT_TOKENS: Final[frozenset[str]] = frozenset(
    {
        "a",
        "an",
        "as",
        "do",
        "este",
        "esta",
        "for",
        "is",
        "isso",
        "it",
        "me",
        "my",
        "o",
        "please",
        "por",
        "para",
        "resumo",
        "resuma",
        "summary",
        "summarize",
        "text",
        "texto",
        "that",
        "the",
        "this",
        "to",
        "um",
        "uma",
    }
)
_CONTENTLESS_PROTOTYPES: Final[tuple[str, ...]] = (
    "this text",
    "this article",
    "text for me",
    "resuma este texto",
    "resumo disso",
    "summarize this text for me",
)


def _has_meaningful_content(text: str) -> bool:
    tokens = tokenize(text)
    if not tokens:
        return False
    if len(tokens) >= _MIN_CONTENT_WORDS:
        return True
    informative_tokens = [token for token in tokens if token not in _GENERIC_CONTENT_TOKENS]
    unique_informative_tokens = set(informative_tokens)
    if len(" ".join(informative_tokens)) < _MIN_SHORT_CONTENT_CHARS:
        return False
    if len(unique_informative_tokens) < 2:
        return False
    if len(informative_tokens) < _MIN_INFORMATIVE_TOKENS and len(unique_informative_tokens) < 3:
        return False
    match = best_lexical_match(" ".join(tokens), list(_CONTENTLESS_PROTOTYPES))
    return match is None or match.score < _CONTENTLESS_MATCH_THRESHOLD


class SummarizationHandler:
    id = "summarization"
    intent = id

    def __init__(self, profile: ModelProfile | None = None) -> None:
        self._profile = profile or MODEL_REGISTRY["summarization"]

    def execute(self, input: str, llm: LLMClient) -> BaseModel:
        return self.handle(input, llm)

    def handle(self, user_input: str, llm: LLMClient) -> BaseModel:
        trace.handler("summarization", user_input)
        trace.span_enter("summarization")
        text = _TRIGGER_PREFIX.sub("", user_input).strip()
        if not _has_meaningful_content(text):
            trace.span_exit("summarization")
            return FinalAnswer(answer="No text provided to summarize.")
        result = llm.structured(
            LLMRequest(
                model=self._profile.model,
                system=self._profile.system,
                user=f"Summarize this text:\n\n{text}",
                max_tokens=self._profile.max_tokens,
                temperature=self._profile.temperature,
            ),
            SummaryResult,
        )
        trace.span_exit("summarization")
        return result


_handler = SummarizationHandler()
handle = _handler.handle
