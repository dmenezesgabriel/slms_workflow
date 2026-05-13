from __future__ import annotations

from pydantic import BaseModel

from src import trace
from src.llm_client import LLMClient, LLMRequest
from src.model_registry import MODEL_REGISTRY
from src.schemas import ClassificationResult


class ClassificationHandler:
    intent = "classification"

    def handle(self, user_input: str, llm: LLMClient) -> BaseModel:
        trace.handler("classification", user_input)
        trace.span_enter("classification")
        profile = MODEL_REGISTRY["classification"]
        result = llm.structured(
            LLMRequest(
                model=profile.model,
                system=profile.system,
                user=user_input,
                max_tokens=profile.max_tokens,
                temperature=profile.temperature,
            ),
            ClassificationResult,
        )
        trace.span_exit("classification")
        return result


_handler = ClassificationHandler()
handle = _handler.handle
