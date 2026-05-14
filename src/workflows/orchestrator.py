"""Unified assistant coordinator — executes DAG workflows for every input."""

from __future__ import annotations

from typing import Callable

from pydantic import BaseModel

from src import trace
from src.graph.base import NodeRegistry, WorkflowNode
from src.graph.dag import GraphNode, WorkflowGraph, run_graph
from src.llm_client import LLMClient
from src.router import route_task
from src.schemas import IntentName
from src.tools import ToolRegistry
from src.workflows.composer import DAGComposer
from src.workflows.planner import Planner


class Orchestrator:
    def __init__(
        self,
        node_registry: NodeRegistry,
        tool_registry: ToolRegistry,
        planner: Planner | None = None,
    ) -> None:
        self.node_registry = node_registry
        self.tool_registry = tool_registry
        self._planner = planner or Planner(
            node_registry=node_registry,
            tool_registry=tool_registry,
        )

    def _node(self, intent: str) -> WorkflowNode:
        node = self.node_registry.get(intent)
        if node is None:
            node = self.node_registry.get("general")
        if node is None:
            raise KeyError(f"Node registry misconfigured: no {intent!r} and no 'general' fallback")
        return node

    def run(
        self,
        user_input: str,
        llm: LLMClient,
        conversation_context: str | None = None,
    ) -> BaseModel:
        trace.span_enter("orchestrate")
        graph = self._planner.plan(user_input, llm)
        trace.plan("dag", graph.name, graph.description)

        dag_input = user_input
        if conversation_context and self._is_simple(graph):
            intent = graph.nodes[0].node.id
            dag_input = _contextualize(user_input, conversation_context, intent)

        result, _trace = run_graph(graph, dag_input, llm)
        trace.span_exit("orchestrate")
        if result is None:
            from src.schemas import FinalAnswer

            return FinalAnswer(answer="No DAG node was executed for this request.")
        return result

    def plan(self, user_input: str, llm: LLMClient) -> WorkflowGraph:
        return self._planner.plan(user_input, llm)

    def run_direct(self, user_input: str, llm: LLMClient) -> BaseModel:
        return self.run_direct_with_intent(user_input, llm, route_task(user_input, llm).intent)

    def run_direct_with_intent(
        self, user_input: str, llm: LLMClient, intent: IntentName | None = None
    ) -> BaseModel:
        if intent is None:
            return self.run_direct(user_input, llm)
        graph = WorkflowGraph(
            name=intent,
            description=f"Direct dispatch to {intent}.",
            nodes=(GraphNode("final", self._node(intent), "{query}"),),
            final_node="final",
        )
        result, _trace = run_graph(graph, user_input, llm)
        if result is None:
            from src.schemas import FinalAnswer

            return FinalAnswer(answer="No DAG node was executed for this request.")
        return result

    @staticmethod
    def _is_simple(graph: WorkflowGraph) -> bool:
        return len(graph.nodes) == 1 and graph.nodes[0].node.id != "agent"

    def compose_dag(self, user_input: str) -> WorkflowGraph | None:
        return DAGComposer(
            node_registry=self.node_registry,
            tool_registry=self.tool_registry,
        ).compose(user_input)


Dispatch = Callable[[str, LLMClient], BaseModel]


def _contextualize(
    user_input: str,
    conversation_context: str | None,
    intent: str | None,
) -> str:
    if not conversation_context:
        return user_input
    if intent not in {"question_answering", "general", "classification", "summarization"}:
        return user_input
    return (
        "Recent conversation context:\n"
        f"{conversation_context}\n\n"
        f"Current user request: {user_input}"
    )
