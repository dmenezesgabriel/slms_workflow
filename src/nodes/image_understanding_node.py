from __future__ import annotations

from pydantic import BaseModel

from src.handlers.image_understanding import ImageUnderstandingHandler
from src.llm_client import LLMClient


class ImageUnderstandingNode:
    id = "image_understanding"

    def __init__(self) -> None:
        self._handler = ImageUnderstandingHandler()

    def execute(self, input: str, llm: LLMClient) -> BaseModel:
        return self._handler.handle(input, llm)
