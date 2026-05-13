"""Unified assistant coordinator — executes DAG workflows for every input."""

from __future__ import annotations

from typing import Callable

from pydantic import BaseModel

from src import trace
from src.composer import DAGComposer
from src.dag import DagNode, DagWorkflow, run_dag_workflow
from src.handlers import NODE_REGISTRY
from src.llm_client import LLMClient
from src.nodes.base import WorkflowNode
from src.planner import Planner
from src.router import route_task
from src.schemas import IntentName


def _node(intent: str) -> WorkflowNode:
    node = NODE_REGISTRY.get(intent)
    if node is None:
        node = NODE_REGISTRY.get("general")
    if node is None:
        raise KeyError(f"Node registry misconfigured: no {intent!r} and no 'general' fallback")
    return node


class Orchestrator:
    def __init__(self) -> None:
        self._planner = Planner()

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

        result, _trace = run_dag_workflow(graph, dag_input, llm)
        trace.span_exit("orchestrate")
        return result

    def plan(self, user_input: str, llm: LLMClient) -> DagWorkflow:
        return self._planner.plan(user_input, llm)

    def run_direct(self, user_input: str, llm: LLMClient) -> BaseModel:
        return self.run_direct_with_intent(user_input, llm, route_task(user_input, llm).intent)

    def run_direct_with_intent(
        self, user_input: str, llm: LLMClient, intent: IntentName | None = None
    ) -> BaseModel:
        if intent is None:
            return self.run_direct(user_input, llm)
        graph = DagWorkflow(
            name=intent,
            description=f"Direct dispatch to {intent}.",
            nodes=(DagNode("final", _node(intent), "{query}"),),
            final_node="final",
        )
        result, _trace = run_dag_workflow(graph, user_input, llm)
        return result

    @staticmethod
    def _is_simple(graph: DagWorkflow) -> bool:
        return len(graph.nodes) == 1 and graph.nodes[0].node.id != "agent"

    def compose_dag(self, user_input: str) -> DagWorkflow | None:
        return DAGComposer().compose(user_input)


_orchestrator = Orchestrator()


def run_assistant(
    user_input: str,
    llm: LLMClient,
    conversation_context: str | None = None,
) -> BaseModel:
    return _orchestrator.run(user_input, llm, conversation_context)


def run_direct(user_input: str, llm: LLMClient) -> BaseModel:
    return _orchestrator.run_direct(user_input, llm)


def run_direct_with_intent(
    user_input: str, llm: LLMClient, intent: IntentName | None = None
) -> BaseModel:
    return _orchestrator.run_direct_with_intent(user_input, llm, intent)


def plan_assistant(user_input: str, llm: LLMClient) -> DagWorkflow:
    return _orchestrator.plan(user_input, llm)


def compose_dag_workflow(user_input: str) -> DagWorkflow | None:
    return _orchestrator.compose_dag(user_input)


def compose_workflow(user_input: str) -> DagWorkflow | None:
    return compose_dag_workflow(user_input)


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


Dispatch = Callable[[str, LLMClient], BaseModel]
