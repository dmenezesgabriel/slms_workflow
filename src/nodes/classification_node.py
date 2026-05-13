from __future__ import annotations

from pydantic import BaseModel

from src.handlers.classification import ClassificationHandler
from src.llm_client import LLMClient


class ClassificationNode:
    id = "classification"

    def __init__(self) -> None:
        self._handler = ClassificationHandler()

    def execute(self, input: str, llm: LLMClient) -> BaseModel:
        return self._handler.handle(input, llm)
