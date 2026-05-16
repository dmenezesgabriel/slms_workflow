"""Unified assistant coordinator — executes DAG workflows for every input."""

from __future__ import annotations

import logging
import time
from typing import Callable

from pydantic import BaseModel

from src import trace
from src.graph.base import NodeRegistry
from src.graph.dag import WorkflowGraph, run_graph
from src.graph.trace_types import ExecutionTrace
from src.llm_client import LLMClient
from src.router import Router, route_task
from src.schemas import IntentName
from src.tools import ToolRegistry
from src.trace_sink import (
    FileTraceSink,
    MultiSink,
    TraceSink,
    build_metrics_summary,
    build_trace_from_run,
    generate_run_id,
    write_metrics_artifact,
)
from src.workflows.composer import DAGComposer
from src.workflows.planner import Planner

logger = logging.getLogger(__name__)


class Orchestrator:
    def __init__(
        self,
        node_registry: NodeRegistry,
        tool_registry: ToolRegistry,
        planner: Planner | None = None,
        router: Router | None = None,
        trace_sink: TraceSink | None = None,
    ) -> None:
        self.node_registry = node_registry
        self.tool_registry = tool_registry
        self._router = router or Router()
        self._planner = planner or Planner(
            node_registry=node_registry,
            tool_registry=tool_registry,
            router=self._router,
        )
        self._trace_sink: MultiSink
        if isinstance(trace_sink, MultiSink):
            self._trace_sink = trace_sink
        elif trace_sink is not None:
            self._trace_sink = MultiSink([trace_sink])
        else:
            self._trace_sink = MultiSink([FileTraceSink()])

    def run(
        self,
        user_input: str,
        llm: LLMClient,
        conversation_context: str | None = None,
    ) -> BaseModel:
        run_id = generate_run_id()
        trace.set_run_id(run_id)
        start_time = time.monotonic()
        trace.span_enter("orchestrate")

        graph = self._planner.plan(user_input, llm)
        trace.plan("dag", graph.name, graph.description)

        dag_input = user_input
        if conversation_context and self._is_simple(graph):
            intent = graph.nodes[0].node.id
            dag_input = _contextualize(user_input, conversation_context, intent)

        result, exec_trace = run_graph(graph, dag_input, llm)

        end_time = time.monotonic()
        trace.span_exit("orchestrate")

        if result is None:
            from src.schemas import FinalAnswer

            result = FinalAnswer(answer="No DAG node was executed for this request.")

        full_trace = build_trace_from_run(
            run_id=run_id,
            workflow_name=exec_trace.workflow_name,
            workflow_description=graph.description,
            route_strategy=self._resolve_route_strategy(graph),
            route_confidence=1.0,
            exec_trace=exec_trace,
            start_time=start_time,
            end_time=end_time,
            final_status="completed",
        )
        self._emit_trace(full_trace)

        return result

    def _emit_trace(self, full_trace: ExecutionTrace) -> None:
        sink_failures: list[dict[str, str]] = []
        try:
            sink_failures = self._trace_sink.emit(full_trace)
        except Exception:
            logger.exception("Trace persistence failed, continuing")
        try:
            metrics = build_metrics_summary(full_trace)
            metrics.sink_failures = sink_failures
            write_metrics_artifact(metrics)
        except Exception:
            logger.exception("Metrics artifact writing failed, continuing")

    @staticmethod
    def _resolve_route_strategy(graph: WorkflowGraph) -> str:
        if graph.name.startswith("on_demand"):
            return "composed"
        if graph.name == "agent":
            return "agent"
        return "single"

    def plan(self, user_input: str, llm: LLMClient) -> WorkflowGraph:
        return self._planner.plan(user_input, llm)

    def run_direct(self, user_input: str, llm: LLMClient) -> BaseModel:
        return self.run_direct_with_intent(
            user_input,
            llm,
            route_task(user_input, llm, self._router).intent,
        )

    def run_direct_with_intent(
        self, user_input: str, llm: LLMClient, intent: IntentName | None = None
    ) -> BaseModel:
        if intent is None:
            return self.run_direct(user_input, llm)
        from src.graph.dag import GraphNode

        run_id = generate_run_id()
        trace.set_run_id(run_id)
        start_time = time.monotonic()
        graph = WorkflowGraph(
            name=intent,
            description=f"Direct dispatch to {intent}.",
            nodes=(GraphNode("final", self.node_registry.resolve(intent), "{query}"),),
            final_node="final",
        )
        result, exec_trace = run_graph(graph, user_input, llm)
        end_time = time.monotonic()

        if result is None:
            from src.schemas import FinalAnswer

            result = FinalAnswer(answer="No DAG node was executed for this request.")

        full_trace = build_trace_from_run(
            run_id=run_id,
            workflow_name=exec_trace.workflow_name,
            workflow_description=graph.description,
            route_strategy="direct",
            route_confidence=1.0,
            exec_trace=exec_trace,
            start_time=start_time,
            end_time=end_time,
            final_status="completed",
        )
        self._emit_trace(full_trace)

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
