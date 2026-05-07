from __future__ import annotations

import re

from pydantic import BaseModel

from app.llm_client import LLMClient, LLMRequest
from app.model_registry import MODEL_REGISTRY
from app.schemas import SummaryResult

_TRIGGER_PREFIX = re.compile(
    r"^(summarize[:\s]+|summary[:\s]+|tl;dr[:\s]+|resuma[:\s]+|resumo[:\s]+)",
    re.IGNORECASE,
)


def handle(user_input: str, llm: LLMClient) -> BaseModel:
    text = _TRIGGER_PREFIX.sub("", user_input).strip()
    profile = MODEL_REGISTRY["summarization"]
    return llm.structured(
        LLMRequest(
            model=profile.model,
            system=profile.system,
            user=f"Summarize this text:\n\n{text}",
            max_tokens=profile.max_tokens,
            temperature=profile.temperature,
        ),
        SummaryResult,
    )
