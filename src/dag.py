from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel

from src import retrieval, trace
from src.context import compress, extract_text
from src.handlers import HANDLER_REGISTRY
from src.llm_client import LLMClient
from src.schemas import FinalAnswer

ConditionName = Literal[
    "always",
    "if_retrieval_needed",
    "if_not_retrieval_needed",
    "if_query_has_url",
    "if_query_has_no_url",
]


@dataclass(frozen=True)
class DagNode:
    """One deterministic unit in an agentic workflow graph.

    intent maps to the existing handler registry. input_format can reference:
      - {query}: original user prompt
      - {input}: current compressed output from the most recently executed node
      - {node_id}: text output of any dependency or previously executed node
    """

    id: str
    intent: str
    input_format: str = "{input}"
    depends_on: tuple[str, ...] = ()
    condition: ConditionName = "always"


@dataclass(frozen=True)
class DagWorkflow:
    name: str
    description: str
    nodes: tuple[DagNode, ...]
    final_node: str | None = None


_MAX_NODE_INPUT_CHARS = 900


class _FormatValues(dict[str, str]):
    def __missing__(self, key: str) -> str:
        return ""


def run_dag_workflow(graph: DagWorkflow, user_input: str, llm: LLMClient) -> BaseModel:
    """Execute a deterministic DAG workflow and return the selected final result."""

    order = _topological_order(graph)
    outputs: dict[str, str] = {}
    results: dict[str, BaseModel] = {}
    current = user_input

    for node_id in order:
        node = _node_by_id(graph, node_id)
        if not _condition_matches(node.condition, user_input):
            trace.dag_skip(graph.name, node.id, node.condition)
            continue

        node_input = _render_input(node.input_format, user_input, current, outputs)
        if len(node_input) > _MAX_NODE_INPUT_CHARS:
            node_input = node_input[:_MAX_NODE_INPUT_CHARS]

        trace.dag_node(graph.name, node.id, node.intent, node_input)
        handler = HANDLER_REGISTRY.get(node.intent, HANDLER_REGISTRY["general"])
        result = handler(node_input, llm)
        text = extract_text(result)

        results[node.id] = result
        outputs[node.id] = text
        current = compress(text, query=user_input, max_sentences=5)

    final_id = graph.final_node or (order[-1] if order else None)
    if final_id and final_id in results:
        return results[final_id]

    if results:
        last_id = next(reversed(results))
        return results[last_id]

    return FinalAnswer(answer="No DAG node was executed for this request.")


def _render_input(
    input_format: str,
    user_input: str,
    current: str,
    outputs: dict[str, str],
) -> str:
    values = _FormatValues({"query": user_input, "input": current})
    values.update(outputs)
    return input_format.format_map(values)


def _condition_matches(condition: ConditionName, user_input: str) -> bool:
    has_url = retrieval._URL_PATTERN.search(user_input) is not None
    if condition == "always":
        return True
    if condition == "if_retrieval_needed":
        return retrieval.needs_retrieval(user_input)
    if condition == "if_not_retrieval_needed":
        return not retrieval.needs_retrieval(user_input)
    if condition == "if_query_has_url":
        return has_url
    if condition == "if_query_has_no_url":
        return not has_url
    return False


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
