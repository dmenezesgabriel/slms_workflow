from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel

from src.llm_client import LLMClient


class Handler(Protocol):
    intent: str

    def handle(self, user_input: str, llm: LLMClient) -> BaseModel: ...
