"""Composes a DagWorkflow for every user input — no strategy enum, always a DAG."""

from __future__ import annotations

from src import trace
from src.composer import DAGComposer, _looks_like_ambiguous_multi_tool_task
from src.dag import DagNode, DagWorkflow
from src.llm_client import LLMClient
from src.nodes.base import NodeRegistry, WorkflowNode
from src.patterns import RECOMMENDATION_RE
from src.router import route_task
from src.tools import ToolRegistry


class Planner:
    def __init__(
        self,
        node_registry: NodeRegistry,
        tool_registry: ToolRegistry,
        composer: DAGComposer | None = None,
    ) -> None:
        self._node_registry = node_registry
        self._composer = composer or DAGComposer(
            node_registry=node_registry,
            tool_registry=tool_registry,
        )

    def _node(self, intent: str) -> WorkflowNode:
        node = self._node_registry.get(intent)
        if node is None:
            node = self._node_registry.get("general")
        if node is None:
            raise KeyError(f"Node registry misconfigured: no {intent!r} and no 'general' fallback")
        return node

    def plan(self, user_input: str, llm: LLMClient) -> DagWorkflow:
        trace.span_enter("planning")
        stripped = user_input.strip()
        if not stripped:
            trace.plan_step("empty", "Empty prompt")
            trace.span_exit("planning")
            return self._single("general", "Empty prompt.")

        graph = self._composer.compose(stripped)
        if graph is not None:
            trace.plan_step("composed_dag", graph.name)
            trace.span_exit("planning")
            return graph

        if _looks_like_ambiguous_multi_tool_task(stripped):
            trace.plan_step("agent", "Ambiguous multi-step tool task")
            trace.span_exit("planning")
            return self._agent("Ambiguous multi-step tool task.")

        if RECOMMENDATION_RE.search(stripped):
            trace.plan_step("single", "question_answering")
            trace.span_exit("planning")
            return self._single(
                "question_answering", "Deterministic recommendation/question pattern."
            )

        intent = route_task(stripped, llm)
        trace.plan_step("single", intent.intent)
        trace.span_exit("planning")
        return self._single(intent.intent, intent.reason)

    def _single(self, intent: str, description: str) -> DagWorkflow:
        return DagWorkflow(
            name=intent,
            description=description,
            nodes=(DagNode("final", self._node(intent), "{query}"),),
            final_node="final",
        )

    def _agent(self, description: str) -> DagWorkflow:
        return DagWorkflow(
            name="agent",
            description=description,
            nodes=(DagNode("agent", self._node("agent"), "{query}"),),
            final_node="agent",
        )
