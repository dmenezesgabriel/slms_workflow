from __future__ import annotations

from pydantic import BaseModel

from src.handlers.function_calling import FunctionCallingHandler
from src.llm_client import LLMClient


class FunctionCallingNode:
    id = "function_calling"

    def __init__(self) -> None:
        self._handler = FunctionCallingHandler()

    def execute(self, input: str, llm: LLMClient) -> BaseModel:
        return self._handler.handle(input, llm)
