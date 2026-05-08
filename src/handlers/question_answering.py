from __future__ import annotations

from pydantic import BaseModel

from src import retrieval
from src.llm_client import LLMClient, LLMRequest
from src.model_registry import MODEL_REGISTRY
from src.schemas import FinalAnswer

_URL_PATTERN = retrieval._URL_PATTERN
_WHAT_IS_RE = retrieval._WHAT_IS_RE
_PROPER_NOUN_RE = retrieval._PROPER_NOUN_RE
_RETRIEVAL_SIGNALS = retrieval._RETRIEVAL_SIGNALS


def _needs_retrieval(text: str) -> bool:
    """True when the query has temporal signals or contains a URL."""
    return retrieval.needs_retrieval(text)


def _fetch_context(user_input: str) -> str:
    return retrieval.DEFAULT_RETRIEVER.fetch_context(user_input)


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
