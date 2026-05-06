from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

MessageContent = str | list[dict[str, Any]]


@dataclass(frozen=True)
class LLMRequest:
    model: str
    system: str
    user: MessageContent
    temperature: float = 0.0
    max_tokens: int = 256
    tools: list[dict[str, Any]] | None = None


@dataclass(frozen=True)
class LLMResponse:
    text: str
    raw: Any | None = None


class LLMClient(Protocol):
    def complete(self, request: LLMRequest) -> LLMResponse:
        ...

    def structured(self, request: LLMRequest, schema: type[T]) -> T:
        ...