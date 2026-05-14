from __future__ import annotations

from typing import Protocol, Sequence

from pydantic import BaseModel

from src.llm_client import LLMClient


class WorkflowNode(Protocol):
    id: str

    def execute(self, input: str, llm: LLMClient) -> BaseModel: ...


class NodeRegistry:
    def __init__(self, nodes: Sequence[WorkflowNode]) -> None:
        self._nodes: dict[str, WorkflowNode] = {n.id: n for n in nodes}
        self._fallback = self._nodes.get("general")

    def get(self, node_id: str) -> WorkflowNode | None:
        return self._nodes.get(node_id)

    def all(self) -> list[WorkflowNode]:
        """Return all registered workflow nodes (for registry composition)."""
        return list(self._nodes.values())
