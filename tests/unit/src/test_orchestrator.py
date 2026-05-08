from __future__ import annotations

from unittest.mock import MagicMock

from src.orchestrator import compose_dag_workflow, compose_workflow, plan_assistant


def test_composes_math_follow_up_workflow() -> None:
    graph = compose_workflow("calculate 7 times 8 and tell me if the result is even or odd")

    assert graph is not None
    assert graph.name == "on_demand_calculator_to_question_answering"
    assert [node.intent for node in graph.nodes] == ["function_calling", "question_answering"]
    assert graph.nodes[0].input_format == "calculate 7 * 8"


def test_composes_research_summary_workflow_and_cleans_follow_up() -> None:
    graph = compose_workflow("search for llama.cpp and summarize the findings")

    assert graph is not None
    assert graph.name == "on_demand_web_search_to_summarization"
    assert graph.nodes[0].input_format == "search for llama.cpp"
    assert graph.nodes[1].intent == "summarization"


def test_composes_on_demand_dag_for_default_planner() -> None:
    graph = compose_dag_workflow("search for llama.cpp and summarize the findings")

    assert graph is not None
    assert graph.name == "on_demand_web_search_to_summarization"
    assert [node.id for node in graph.nodes] == ["tool", "final"]
    assert graph.nodes[1].depends_on == ("tool",)
    assert graph.nodes[1].input_format == "summarize: {tool}"


def test_plan_uses_dag_for_compound_deterministic_tasks() -> None:
    plan = plan_assistant("search for llama.cpp and summarize the findings", MagicMock())

    assert plan.strategy == "dag"
    assert plan.graph is not None
    assert plan.name == "on_demand_web_search_to_summarization"


def test_plain_math_stays_direct() -> None:
    workflow = compose_workflow("what is 15 + 7?")

    assert workflow is None


def test_entity_relation_question_stays_direct(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    expected = MagicMock(intent="question_answering", reason="mock route")
    route_task = MagicMock(return_value=expected)
    monkeypatch.setattr("src.orchestrator.route_task", route_task)

    plan = plan_assistant("what is the capital of France?", MagicMock())

    assert plan.strategy == "direct"
    assert plan.intent == "question_answering"
    assert route_task.call_count == 1
