from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.nodes.base import NodeRegistry, WorkflowNode
from src.tools import ToolRegistry


def _make_node(node_id: str) -> WorkflowNode:
    class _Node:
        id = node_id

        def execute(self, input: str, llm: MagicMock) -> MagicMock:  # type: ignore[override]
            return MagicMock()

    return _Node()


def _make_tool(name: str) -> MagicMock:
    tool = MagicMock()
    tool.name = name
    tool.prompt_line.return_value = f"{name}: does something"
    tool.execute.return_value = ""
    return tool


def _build_node_registry(*node_ids: str) -> NodeRegistry:
    return NodeRegistry([_make_node(nid) for nid in node_ids])


def _build_tool_registry(*tool_names: str) -> ToolRegistry:
    return ToolRegistry([_make_tool(name) for name in tool_names])


def _make_orchestrator(
    node_ids: tuple[str, ...] = (
        "function_calling",
        "question_answering",
        "summarization",
        "general",
    ),
    tool_names: tuple[str, ...] = ("calculator", "web_search"),
) -> object:
    from src.orchestrator import Orchestrator

    return Orchestrator(
        node_registry=_build_node_registry(*node_ids),
        tool_registry=_build_tool_registry(*tool_names),
    )


def test_composes_math_follow_up_workflow() -> None:
    orchestrator = _make_orchestrator()
    graph = orchestrator.compose_dag("calculate 7 times 8 and tell me if the result is even or odd")

    assert graph is not None
    assert graph.name == "on_demand_calculator_to_question_answering"
    assert [node.node.id for node in graph.nodes] == ["function_calling", "question_answering"]
    assert graph.nodes[0].input_format == "calculate 7 * 8"


def test_composes_research_summary_workflow_and_cleans_follow_up() -> None:
    orchestrator = _make_orchestrator()
    graph = orchestrator.compose_dag("search for llama.cpp and summarize the findings")

    assert graph is not None
    assert graph.name == "on_demand_web_search_to_summarization"
    assert graph.nodes[0].input_format == "search for llama.cpp"
    assert graph.nodes[1].node.id == "summarization"


def test_composes_on_demand_dag_for_default_planner() -> None:
    orchestrator = _make_orchestrator()
    graph = orchestrator.compose_dag("search for llama.cpp and summarize the findings")

    assert graph is not None
    assert graph.name == "on_demand_web_search_to_summarization"
    assert [node.id for node in graph.nodes] == ["tool", "final"]
    assert graph.nodes[1].depends_on == ("tool",)
    assert graph.nodes[1].input_format == "summarize: {tool}"


def test_plan_returns_multi_node_dag_for_compound_tasks() -> None:
    orchestrator = _make_orchestrator()
    plan = orchestrator.plan("search for llama.cpp and summarize the findings", MagicMock())

    assert len(plan.nodes) > 1
    assert plan.name == "on_demand_web_search_to_summarization"


def test_plain_math_stays_direct() -> None:
    orchestrator = _make_orchestrator()
    workflow = orchestrator.compose_dag("what is 15 + 7?")

    assert workflow is None


def test_entity_relation_returns_single_node_dag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = MagicMock(intent="question_answering", reason="mock route")
    route_task = MagicMock(return_value=expected)
    monkeypatch.setattr("src.planner.route_task", route_task)

    orchestrator = _make_orchestrator()
    plan = orchestrator.plan("what is the capital of France?", MagicMock())

    assert len(plan.nodes) == 1
    assert plan.nodes[0].node.id == "question_answering"
    assert route_task.call_count == 1
