from __future__ import annotations

from pydantic import BaseModel

from src import trace
from src.llm_client import LLMClient, LLMRequest
from src.model_registry import MODEL_REGISTRY
from src.schemas import FinalAnswer


class GeneralHandler:
    intent = "general"

    def handle(self, user_input: str, llm: LLMClient) -> BaseModel:
        trace.handler("general", user_input)
        trace.span_enter("general")
        profile = MODEL_REGISTRY["general"]
        result = llm.structured(
            LLMRequest(
                model=profile.model,
                system=profile.system,
                user=user_input,
                max_tokens=profile.max_tokens,
                temperature=profile.temperature,
            ),
            FinalAnswer,
        )
        trace.span_exit("general")
        return result


_handler = GeneralHandler()
handle = _handler.handle
