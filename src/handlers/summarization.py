from __future__ import annotations

import re

from pydantic import BaseModel

from src import trace
from src.llm_client import LLMClient, LLMRequest
from src.model_registry import MODEL_REGISTRY
from src.schemas import FinalAnswer, SummaryResult

_TRIGGER_PREFIX = re.compile(
    r"^(summarize[:\s]+|summary[:\s]+|tl;dr[:\s]+|resuma[:\s]+|resumo[:\s]+)",
    re.IGNORECASE,
)
_MIN_CONTENT_WORDS = 10


class SummarizationHandler:
    intent = "summarization"

    def handle(self, user_input: str, llm: LLMClient) -> BaseModel:
        trace.handler("summarization", user_input)
        trace.span_enter("summarization")
        text = _TRIGGER_PREFIX.sub("", user_input).strip()
        if len(text.split()) < _MIN_CONTENT_WORDS:
            trace.span_exit("summarization")
            return FinalAnswer(answer="No text provided to summarize.")
        profile = MODEL_REGISTRY["summarization"]
        result = llm.structured(
            LLMRequest(
                model=profile.model,
                system=profile.system,
                user=f"Summarize this text:\n\n{text}",
                max_tokens=profile.max_tokens,
                temperature=profile.temperature,
            ),
            SummaryResult,
        )
        trace.span_exit("summarization")
        return result


_handler = SummarizationHandler()
handle = _handler.handle
