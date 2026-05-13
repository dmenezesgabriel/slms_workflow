from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Callable, Mapping

from pydantic import BaseModel

from src import trace
from src.context import CompressFn, ExecutionContext, ExtractFn
from src.llm_client import LLMClient
from src.nodes.base import WorkflowNode
from src.patterns import URL_RE as _URL_PATTERN
from src.text_utils import compress, extract_text
from src.trace_types import ExecutionTrace, NodeTrace

ConditionFn = Callable[[str], bool]

_DEFAULT_CONDITIONS: Mapping[str, ConditionFn] = MappingProxyType(
    {
        "always": lambda _: True,
        "if_query_has_url": lambda text: bool(_URL_PATTERN.search(text)),
        "if_query_has_no_url": lambda text: not bool(_URL_PATTERN.search(text)),
    }
)


@dataclass(frozen=True)
class DagNode:
    """One deterministic unit in an agentic workflow graph.

    node is the WorkflowNode to execute; input_format can reference:
      - {query}: original user prompt
      - {input}: current compressed output from the most recently executed node
      - {node_id}: text output of any dependency or previously executed node
    """

    id: str
    node: WorkflowNode
    input_format: str = "{input}"
    depends_on: tuple[str, ...] = ()
    condition: str = "always"


@dataclass(frozen=True)
class DagWorkflow:
    name: str
    description: str
    nodes: tuple[DagNode, ...]
    final_node: str | None = None
    conditions: Mapping[str, ConditionFn] = field(default_factory=lambda: _DEFAULT_CONDITIONS)


_MAX_NODE_INPUT_CHARS = 900


def run_dag_workflow(
    graph: DagWorkflow,
    user_input: str,
    llm: LLMClient,
    compress_fn: CompressFn | None = None,
    extract_fn: ExtractFn | None = None,
) -> tuple[BaseModel | None, ExecutionTrace]:
    """Execute a deterministic DAG workflow and return (result, trace).

    Each node's WorkflowNode.execute is called with its rendered input.
    compress_fn defaults to text_utils.compress.
    extract_fn defaults to text_utils.extract_text.
    """
    _compress = compress_fn or (lambda text, query: compress(text, query=query, max_sentences=5))
    _extract = extract_fn or extract_text

    _validate_dag(graph)

    ctx = ExecutionContext(
        query=user_input,
        _compress=_compress,
        _extract=_extract,
    )

    order = _topological_order(graph)
    exec_trace = ExecutionTrace(workflow_name=graph.name)

    for node_id in order:
        node = _node_by_id(graph, node_id)
        if not _condition_matches(node.condition, user_input, graph.conditions):
            trace.dag_skip_node(node_id, node.condition)
            continue

        node_input = ctx.render(node.input_format)
        if len(node_input) > _MAX_NODE_INPUT_CHARS:
            node_input = node_input[:_MAX_NODE_INPUT_CHARS]

        t0 = time.monotonic()
        error: str | None = None
        try:
            trace.dag_exec_node(node_id, node.node.id)
            result = node.node.execute(node_input, llm)
        except Exception as exc:
            result = None
            error = str(exc)
        elapsed = (time.monotonic() - t0) * 1000

        if result is not None:
            ctx.record(node.id, result)

        exec_trace.nodes[node.id] = NodeTrace(
            node_id=node.id,
            intent=node.node.id,
            input_=node_input,
            output=_extract(result) if result is not None else "",
            elapsed_ms=round(elapsed, 1),
            error=error,
        )

    final_id = graph.final_node or (order[-1] if order else None)
    if final_id and final_id in ctx.results:
        return ctx.results[final_id], exec_trace

    last = ctx.last_result()
    if last is not None:
        return last, exec_trace

    return None, exec_trace


def _validate_dag(graph: DagWorkflow) -> None:
    for node in graph.nodes:
        if node.condition not in graph.conditions:
            raise ValueError(
                f"Unknown DAG condition {node.condition!r} in {graph.name!r} node {node.id!r}. "
                f"Available: {sorted(graph.conditions)}"
            )


def _condition_matches(
    condition: str, user_input: str, conditions: Mapping[str, ConditionFn]
) -> bool:
    fn = conditions.get(condition)
    if fn is None:
        raise ValueError(
            f"Unknown DAG condition: {condition!r}. " f"Available conditions: {sorted(conditions)}"
        )
    return fn(user_input)


def _node_by_id(graph: DagWorkflow, node_id: str) -> DagNode:
    for node in graph.nodes:
        if node.id == node_id:
            return node
    raise ValueError(f"Unknown DAG node {node_id!r} in {graph.name!r}")


def _topological_order(graph: DagWorkflow) -> list[str]:
    nodes = {node.id: node for node in graph.nodes}
    if len(nodes) != len(graph.nodes):
        raise ValueError(f"DAG {graph.name!r} contains duplicate node ids")

    indegree = {node_id: 0 for node_id in nodes}
    outgoing: dict[str, list[str]] = {node_id: [] for node_id in nodes}

    for node in graph.nodes:
        for dep in node.depends_on:
            if dep not in nodes:
                raise ValueError(
                    f"DAG {graph.name!r} node {node.id!r} depends on unknown node {dep!r}"
                )
            indegree[node.id] += 1
            outgoing[dep].append(node.id)

    ready = deque(node_id for node_id, degree in indegree.items() if degree == 0)
    order: list[str] = []

    while ready:
        node_id = ready.popleft()
        order.append(node_id)
        for child in outgoing[node_id]:
            indegree[child] -= 1
            if indegree[child] == 0:
                ready.append(child)

    if len(order) != len(nodes):
        raise ValueError(f"DAG {graph.name!r} contains a cycle")

    return order
