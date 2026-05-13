from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.dag import DagNode, DagWorkflow, run_dag_workflow
from src.llm_client import LLMClient
from src.schemas import FinalAnswer


def _make_node(node_id: str, intent: str = "general") -> object:
    class _Node:
        id = intent

        def execute(self, input: str, llm: LLMClient) -> FinalAnswer:
            return FinalAnswer(answer=f"{self.id}:{input}")

    return _Node()


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

    result, trace = run_dag_workflow(graph, "question", MagicMock())

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
