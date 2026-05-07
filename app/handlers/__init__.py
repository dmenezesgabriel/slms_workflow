from __future__ import annotations

from typing import Callable

from pydantic import BaseModel

from app.handlers import (
    classification,
    function_calling,
    general,
    image_understanding,
    question_answering,
    summarization,
)
from app.llm_client import LLMClient

Handler = Callable[[str, LLMClient], BaseModel]

HANDLER_REGISTRY: dict[str, Handler] = {
    "summarization": summarization.handle,
    "question_answering": question_answering.handle,
    "function_calling": function_calling.handle,
    "classification": classification.handle,
    "image_understanding": image_understanding.handle,
    "general": general.handle,
    "unclassified": general.handle,
}
