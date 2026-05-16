from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel

from src.dag import run_graph
from src.graph.base import NodeRegistry
from src.llm_client import LLMClient
from src.nodes.base import WorkflowNode
from src.orchestrator import Orchestrator
from src.schemas import FinalAnswer
from src.text_utils import extract_text
from src.tools import ToolRegistry
from src.tools.base import Tool


def _make_node(node_id: str) -> WorkflowNode:
    class _Node:
        id = node_id

        def execute(self, input: str, llm: LLMClient) -> BaseModel:
            return FinalAnswer(answer=f"{node_id}:{input}")

    return _Node()


def _make_tool(name: str) -> Tool:
    class _Tool:
        def __init__(self) -> None:
            self.name = name
            self.description = "does something"
            self.parameters: dict[str, str] = {}

        def prompt_line(self) -> str:
            return f"{name}: does something"

        def execute(self, args: dict[str, object]) -> str:
            return ""

    return _Tool()


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
) -> Orchestrator:
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


def test_orchestrated_composed_search_to_qa_produces_substantive_answer() -> None:
    """Previously broken prompt: 'search for llama.cpp and tell me what it is'.

    Proves the full compose → DAG execute path passes tool output
    through to the final answer with substantive content.
    """
    TOOL_RESULT = (
        "llama.cpp is a C/C++ implementation of LLM inference. "
        "It supports 4-bit quantization and runs on CPU. "
        "Great for running local AI models on consumer hardware."
    )

    class _MockToolNode:
        id = "function_calling"

        def execute(self, input: str, llm: LLMClient) -> FinalAnswer:
            return FinalAnswer(answer=f"web_search result: {TOOL_RESULT}")

    class _MockQANode:
        id = "question_answering"

        def execute(self, input: str, llm: LLMClient) -> FinalAnswer:
            return FinalAnswer(answer=f"Based on context: {input}")

    node_registry = NodeRegistry([_MockToolNode(), _MockQANode()])
    tool_registry = _build_tool_registry("web_search")
    orchestrator = Orchestrator(
        node_registry=node_registry,
        tool_registry=tool_registry,
    )

    graph = orchestrator.compose_dag("search for llama.cpp and tell me what it is")
    assert graph is not None
    assert graph.name == "on_demand_web_search_to_question_answering"

    result, trace = run_graph(
        graph,
        "search for llama.cpp and tell me what it is",
        MagicMock(),
    )

    assert result is not None
    answer = extract_text(result)
    assert "C/C++" in answer, f"Expected tool content in answer, got: {answer!r}"
    assert "llama.cpp" in answer, f"Expected llama.cpp in final answer, got: {answer!r}"
    assert trace.nodes["tool"].output == "web_search result: " + TOOL_RESULT
    assert "Context:" in trace.nodes["final"].input_
    assert "Question:" in trace.nodes["final"].input_


def test_node_registry_resolve_returns_specific_node_before_fallback() -> None:
    registry = _build_node_registry("question_answering", "general")

    assert registry.resolve("question_answering").id == "question_answering"


def test_node_registry_resolve_falls_back_to_general() -> None:
    registry = _build_node_registry("general")

    assert registry.resolve("question_answering").id == "general"


def test_node_registry_resolve_raises_without_general_fallback() -> None:
    registry = NodeRegistry([])

    with pytest.raises(
        KeyError,
        match="Node registry misconfigured: no 'question_answering' and no 'general' fallback",
    ):
        registry.resolve("question_answering")
