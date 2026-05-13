from __future__ import annotations

from pydantic import BaseModel

from src.handlers.function_calling import FunctionCallingHandler
from src.llm_client import LLMClient
from src.tools import ToolRegistry


class FunctionCallingNode:
    id = "function_calling"

    def __init__(self, tool_registry: ToolRegistry) -> None:
        self._handler = FunctionCallingHandler(tool_registry=tool_registry)

    def execute(self, input: str, llm: LLMClient) -> BaseModel:
        return self._handler.handle(input, llm)
