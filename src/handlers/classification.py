from __future__ import annotations

from pydantic import BaseModel

from src import trace
from src.llm_client import LLMClient, LLMRequest
from src.model_registry import MODEL_REGISTRY, ModelProfile
from src.schemas import ClassificationResult


class ClassificationHandler:
    id = "classification"
    intent = id

    def __init__(self, profile: ModelProfile | None = None) -> None:
        self._profile = profile or MODEL_REGISTRY["classification"]

    def execute(self, input: str, llm: LLMClient) -> BaseModel:
        return self.handle(input, llm)

    def handle(self, user_input: str, llm: LLMClient) -> BaseModel:
        trace.handler("classification", user_input)
        trace.span_enter("classification")
        result = llm.structured(
            LLMRequest(
                model=self._profile.model,
                system=self._profile.system,
                user=user_input,
                max_tokens=self._profile.max_tokens,
                temperature=self._profile.temperature,
            ),
            ClassificationResult,
        )
        trace.span_exit("classification")
        return result


_handler = ClassificationHandler()
handle = _handler.handle
