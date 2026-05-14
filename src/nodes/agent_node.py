from __future__ import annotations

from pydantic import BaseModel

from src.graph.base import WorkflowNode
from src.llm_client import LLMClient
from src.tools import ToolRegistry


class AgentNode:
    id = "agent"

    def __init__(
        self,
        tool_registry: ToolRegistry,
        action_nodes: dict[str, WorkflowNode] | None = None,
    ) -> None:
        self._tool_registry = tool_registry
        self._action_nodes = action_nodes

    def execute(self, input: str, llm: LLMClient) -> BaseModel:
        from src.agent import run_agent

        return run_agent(
            input,
            llm,
            tool_registry=self._tool_registry,
            action_nodes=self._action_nodes,
        )
