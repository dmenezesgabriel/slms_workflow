from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.dag import DagNode, DagWorkflow, run_dag_workflow
from src.handlers import HANDLER_REGISTRY
from src.schemas import FinalAnswer


def test_runs_nodes_in_dependency_order(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def first_handler(user_input: str, llm: object) -> FinalAnswer:
        calls.append(f"first:{user_input}")
        return FinalAnswer(answer="retrieved context")

    def second_handler(user_input: str, llm: object) -> FinalAnswer:
        calls.append(f"second:{user_input}")
        return FinalAnswer(answer="final answer")

    _intent_map = {"first": first_handler, "second": second_handler}
    original_dispatch = HANDLER_REGISTRY.dispatch

    def patched_dispatch(intent: str, user_input: str, llm: object) -> FinalAnswer:
        if intent in _intent_map:
            return _intent_map[intent](user_input, llm)
        return original_dispatch(intent, user_input, llm)

    monkeypatch.setattr(HANDLER_REGISTRY, "dispatch", patched_dispatch)

    graph = DagWorkflow(
        name="test_graph",
        description="test",
        nodes=(
            DagNode("a", "first", "lookup {query}"),
            DagNode("b", "second", "Context: {a}\nQuestion: {query}", depends_on=("a",)),
        ),
        final_node="b",
    )

    result = run_dag_workflow(graph, "question", MagicMock())

    assert result == FinalAnswer(answer="final answer")
    assert calls == [
        "first:lookup question",
        "second:Context: retrieved context\nQuestion: question",
    ]


def test_skips_branch_when_condition_does_not_match(monkeypatch: pytest.MonkeyPatch) -> None:
    branch_calls: list[str] = []

    def branch_handler(user_input: str, llm: object) -> FinalAnswer:
        branch_calls.append(user_input)
        return FinalAnswer(answer="ran")

    original_dispatch = HANDLER_REGISTRY.dispatch

    def patched_dispatch(intent: str, user_input: str, llm: object) -> FinalAnswer:
        if intent == "branch":
            return branch_handler(user_input, llm)
        return original_dispatch(intent, user_input, llm)

    monkeypatch.setattr(HANDLER_REGISTRY, "dispatch", patched_dispatch)

    graph = DagWorkflow(
        name="branch_graph",
        description="test",
        nodes=(DagNode("url_only", "branch", condition="if_query_has_url"),),
        final_node="url_only",
    )

    result = run_dag_workflow(graph, "no url here", MagicMock())

    assert result == FinalAnswer(answer="No DAG node was executed for this request.")
    assert branch_calls == []


def test_rejects_cycles() -> None:
    graph = DagWorkflow(
        name="cycle",
        description="test",
        nodes=(
            DagNode("a", "general", depends_on=("b",)),
            DagNode("b", "general", depends_on=("a",)),
        ),
    )

    with pytest.raises(ValueError, match="cycle"):
        run_dag_workflow(graph, "prompt", MagicMock())
