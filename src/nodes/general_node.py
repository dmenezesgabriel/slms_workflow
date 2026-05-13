from __future__ import annotations

from pydantic import BaseModel

from src.handlers.general import GeneralHandler
from src.llm_client import LLMClient


class GeneralNode:
    id = "general"

    def __init__(self) -> None:
        self._handler = GeneralHandler()

    def execute(self, input: str, llm: LLMClient) -> BaseModel:
        return self._handler.handle(input, llm)
