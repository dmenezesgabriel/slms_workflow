from __future__ import annotations

from pydantic import BaseModel

from src.llm_client import LLMClient
from src.plugins.contracts import PluginInput
from src.plugins.registry import PluginRegistry
from src.schemas import FinalAnswer


class PluginNode:
    """A WorkflowNode backed by a named plugin from a PluginRegistry.

    PluginNode implements the existing WorkflowNode protocol so the DAG
    executor, workflow runner, and orchestrator never import concrete
    technique or tool modules.
    """

    def __init__(self, plugin_name: str, registry: PluginRegistry) -> None:
        self.id = f"plugin_{plugin_name}"
        self._plugin_name = plugin_name
        self._registry = registry

    def execute(self, input: str, llm: LLMClient) -> BaseModel:
        plugin = self._registry.resolve(self._plugin_name)
        output = plugin.execute(PluginInput(data={"text": input}))
        return FinalAnswer(answer=str(output.data.get("result", "")))
