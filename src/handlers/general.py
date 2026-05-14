from __future__ import annotations

from pydantic import BaseModel

from src import trace
from src.llm_client import LLMClient, LLMRequest
from src.model_registry import MODEL_REGISTRY, ModelProfile
from src.schemas import FinalAnswer


class GeneralHandler:
    id = "general"
    intent = id

    def __init__(self, profile: ModelProfile | None = None) -> None:
        self._profile = profile or MODEL_REGISTRY["general"]

    def execute(self, input: str, llm: LLMClient) -> BaseModel:
        return self.handle(input, llm)

    def handle(self, user_input: str, llm: LLMClient) -> BaseModel:
        trace.handler("general", user_input)
        trace.span_enter("general")
        result = llm.structured(
            LLMRequest(
                model=self._profile.model,
                system=self._profile.system,
                user=user_input,
                max_tokens=self._profile.max_tokens,
                temperature=self._profile.temperature,
            ),
            FinalAnswer,
        )
        trace.span_exit("general")
        return result


_handler = GeneralHandler()
handle = _handler.handle
