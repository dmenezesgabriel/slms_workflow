from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.dag import DagNode, DagWorkflow, GraphNode, WorkflowGraph, run_dag_workflow, run_graph
from src.llm_client import LLMClient
from src.schemas import FinalAnswer


def _make_node(node_id: str, intent: str = "general") -> object:
    class _Node:
        id = intent

        def execute(self, input: str, llm: LLMClient) -> FinalAnswer:
            return FinalAnswer(answer=f"{self.id}:{input}")

    return _Node()


def test_new_runtime_names_are_available_as_aliases() -> None:
    assert GraphNode is DagNode
    assert WorkflowGraph is DagWorkflow
    assert run_dag_workflow is not run_graph


def test_runs_nodes_in_dependency_order() -> None:
    calls: list[str] = []

    class _First:
        id = "first"

        def execute(self, input: str, llm: LLMClient) -> FinalAnswer:
            calls.append(f"first:{input}")
            return FinalAnswer(answer="retrieved context")

    class _Second:
        id = "second"

        def execute(self, input: str, llm: LLMClient) -> FinalAnswer:
            calls.append(f"second:{input}")
            return FinalAnswer(answer="final answer")

    graph = DagWorkflow(
        name="test_graph",
        description="test",
        nodes=(
            DagNode("a", _First(), "lookup {query}"),
            DagNode("b", _Second(), "Context: {a}\nQuestion: {query}", depends_on=("a",)),
        ),
        final_node="b",
    )

    result, trace = run_graph(graph, "question", MagicMock())

    assert result == FinalAnswer(answer="final answer")
    assert calls == [
        "first:lookup question",
        "second:Context: retrieved context\nQuestion: question",
    ]
    assert trace.nodes["a"].input_ == "lookup question"
    assert trace.nodes["a"].elapsed_ms >= 0
    assert trace.nodes["a"].error is None
    assert trace.nodes["b"].input_ == "Context: retrieved context\nQuestion: question"
    assert trace.nodes["b"].output == "final answer"


def test_skips_branch_when_condition_does_not_match() -> None:
    class _Branch:
        id = "branch"

        def execute(self, input: str, llm: LLMClient) -> FinalAnswer:
            raise AssertionError("should not be called")

    graph = DagWorkflow(
        name="branch_graph",
        description="test",
        nodes=(DagNode("url_only", _Branch(), condition="if_query_has_url"),),
        final_node="url_only",
    )

    result, trace = run_dag_workflow(graph, "no url here", MagicMock())

    assert result is None
    assert trace.nodes == {}
    assert len(trace.skipped_nodes) == 1
    assert trace.skipped_nodes[0]["node_id"] == "url_only"
    assert trace.skipped_nodes[0]["condition"] == "if_query_has_url"


def test_runs_nodes_with_injectable_executor() -> None:
    calls: list[str] = []

    class _First:
        id = "first"

        def execute(self, input: str, llm: LLMClient) -> FinalAnswer:
            calls.append(f"first:{input}")
            return FinalAnswer(answer="result_of_first")

    class _Second:
        id = "second"

        def execute(self, input: str, llm: LLMClient) -> FinalAnswer:
            calls.append(f"second:{input}")
            return FinalAnswer(answer="result_of_second")

    graph = DagWorkflow(
        name="test",
        description="test",
        nodes=(
            DagNode("a", _First(), "lookup {query}"),
            DagNode("b", _Second(), "Context: {a}\nQuestion: {query}", depends_on=("a",)),
        ),
        final_node="b",
    )

    result, trace = run_dag_workflow(graph, "question", MagicMock())

    assert result == FinalAnswer(answer="result_of_second")
    assert calls[0] == "first:lookup question"
    assert calls[1].startswith("second:Context:")
    assert trace.nodes["a"].output == "result_of_first"
    assert trace.nodes["b"].output == "result_of_second"


def test_rejects_unknown_condition() -> None:
    class _Node:
        id = "general"

        def execute(self, input: str, llm: LLMClient) -> FinalAnswer:
            return FinalAnswer(answer="")

    graph = DagWorkflow(
        name="bad_condition",
        description="test",
        nodes=(DagNode("a", _Node(), condition="if_something_fake"),),
    )
    with pytest.raises(ValueError, match="Unknown DAG condition"):
        run_dag_workflow(graph, "prompt", MagicMock())


def test_custom_condition_is_respected() -> None:
    custom_conditions = {
        "if_short_query": lambda text: len(text.split()) <= 3,
    }

    calls: list[str] = []

    class _Node:
        id = "general"

        def execute(self, input: str, llm: LLMClient) -> FinalAnswer:
            calls.append(self.id)
            return FinalAnswer(answer="ran")

    graph = DagWorkflow(
        name="custom_condition_test",
        description="test",
        nodes=(DagNode("a", _Node(), condition="if_short_query"),),
        conditions=custom_conditions,
    )

    result, trace = run_dag_workflow(graph, "hi there", MagicMock())
    assert calls == ["general"]
    assert trace.nodes["a"].output == "ran"

    calls.clear()
    result, trace = run_dag_workflow(graph, "this is a very long query", MagicMock())
    assert calls == []


def test_composed_dag_tool_output_flows_to_final_answer() -> None:
    TOOL_RESULT = (
        "llama.cpp is a C/C++ implementation of LLM inference. "
        "It supports 4-bit quantization and runs on CPU. "
        "Great for local AI experiments."
    )

    class _ToolNode:
        id = "function_calling"

        def execute(self, input: str, llm: LLMClient) -> FinalAnswer:
            return FinalAnswer(answer=f"web_search result: {TOOL_RESULT}")

    class _QANode:
        id = "question_answering"

        def execute(self, input: str, llm: LLMClient) -> FinalAnswer:
            return FinalAnswer(answer=f"Based on context: {input}")

    graph = WorkflowGraph(
        name="on_demand_web_search_to_question_answering",
        description="Composed from the user's prompt by the unified assistant.",
        nodes=(
            GraphNode("tool", _ToolNode(), "{query}"),
            GraphNode(
                "final",
                _QANode(),
                "Context:\n{tool}\n\nQuestion: {query}",
                depends_on=("tool",),
            ),
        ),
        final_node="final",
    )

    result, trace = run_graph(
        graph,
        "search for llama.cpp and tell me what it is",
        MagicMock(),
    )

    assert result is not None
    answer = result.model_dump().get("answer", "")
    assert "C/C++" in answer, f"Expected tool content in answer, got: {answer!r}"
    assert "llama.cpp" in answer, f"Expected llama.cpp in answer, got: {answer!r}"
    assert trace.nodes["tool"].output == "web_search result: " + TOOL_RESULT
    assert "Context:" in trace.nodes["final"].input_
    assert "Question:" in trace.nodes["final"].input_


def test_rejects_cycles() -> None:
    class _Node:
        id = "general"

        def execute(self, input: str, llm: LLMClient) -> FinalAnswer:
            return FinalAnswer(answer="")

    graph = DagWorkflow(
        name="cycle",
        description="test",
        nodes=(
            DagNode("a", _Node(), depends_on=("b",)),
            DagNode("b", _Node(), depends_on=("a",)),
        ),
    )

    with pytest.raises(ValueError, match="cycle"):
        run_dag_workflow(graph, "prompt", MagicMock())
