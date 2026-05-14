from __future__ import annotations

import re

from pydantic import BaseModel

from src import trace
from src.llm_client import LLMClient, LLMRequest
from src.model_registry import MODEL_REGISTRY, ModelProfile
from src.schemas import FinalAnswer, SummaryResult

_TRIGGER_PREFIX = re.compile(
    r"^(summarize[:\s]+|summary[:\s]+|tl;dr[:\s]+|resuma[:\s]+|resumo[:\s]+)",
    re.IGNORECASE,
)
_MIN_CONTENT_WORDS = 10


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
        if len(text.split()) < _MIN_CONTENT_WORDS:
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
