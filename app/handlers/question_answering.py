from __future__ import annotations

from pydantic import BaseModel

from app.llm_client import LLMClient, LLMRequest
from app.model_registry import MODEL_REGISTRY
from app.schemas import FinalAnswer


def handle(user_input: str, llm: LLMClient) -> BaseModel:
    profile = MODEL_REGISTRY["question_answering"]
    return llm.structured(
        LLMRequest(
            model=profile.model,
            system=profile.system,
            user=user_input,
            max_tokens=profile.max_tokens,
            temperature=profile.temperature,
        ),
        FinalAnswer,
    )
