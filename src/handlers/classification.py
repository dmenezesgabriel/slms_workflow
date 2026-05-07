from __future__ import annotations

from pydantic import BaseModel

from src.llm_client import LLMClient, LLMRequest
from src.model_registry import MODEL_REGISTRY
from src.schemas import ClassificationResult


def handle(user_input: str, llm: LLMClient) -> BaseModel:
    profile = MODEL_REGISTRY["classification"]
    return llm.structured(
        LLMRequest(
            model=profile.model,
            system=profile.system,
            user=user_input,
            max_tokens=profile.max_tokens,
            temperature=profile.temperature,
        ),
        ClassificationResult,
    )
