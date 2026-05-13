from __future__ import annotations

from pydantic import BaseModel

from src.handlers.summarization import SummarizationHandler
from src.llm_client import LLMClient


class SummarizationNode:
    id = "summarization"

    def __init__(self) -> None:
        self._handler = SummarizationHandler()

    def execute(self, input: str, llm: LLMClient) -> BaseModel:
        return self._handler.handle(input, llm)
