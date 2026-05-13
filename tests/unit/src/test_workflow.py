from __future__ import annotations

from unittest.mock import MagicMock

from src.dag import DagNode, DagWorkflow, run_dag_workflow
from src.llm_client import LLMClient
from src.schemas import FinalAnswer
from src.workflow import WORKFLOW_REGISTRY, run_workflow


def test_predefined_workflows_are_dag_workflows() -> None:
    assert WORKFLOW_REGISTRY
    assert all(isinstance(workflow, DagWorkflow) for workflow in WORKFLOW_REGISTRY.values())
    assert all(workflow.final_node is not None for workflow in WORKFLOW_REGISTRY.values())


def test_run_workflow_delegates_to_dag_runtime() -> None:
    class _FixedNode:
        id = "fixed"

        def execute(self, input: str, llm: LLMClient) -> FinalAnswer:
            return FinalAnswer(answer="ok")

    workflow = DagWorkflow(
        name="compat",
        description="compatibility wrapper",
        nodes=(DagNode("final", _FixedNode(), "hello {query}"),),
        final_node="final",
    )

    result = run_workflow(workflow, "world", MagicMock())

    assert result is not None
    assert isinstance(result, FinalAnswer)
    assert "ok" in str(result)


def test_node_registry_enables_plug_and_play_technique() -> None:
    calls: list[str] = []

    class CustomAnswerNode:
        id = "answer"

        def execute(self, input: str, llm: LLMClient) -> FinalAnswer:
            calls.append(input)
            return FinalAnswer(answer=f"custom: {input}")

    graph = DagWorkflow(
        name="plug_test",
        description="test",
        nodes=(DagNode("final", CustomAnswerNode(), "process {query}"),),
        final_node="final",
    )

    result, trace = run_dag_workflow(graph, "hello", MagicMock())

    assert result == FinalAnswer(answer="custom: process hello")
    assert calls == ["process hello"]
    assert trace.nodes["final"].output == "custom: process hello"


def test_workflow_registry_has_expected_structure() -> None:
    assert "research_and_summarize" in WORKFLOW_REGISTRY
    assert "fetch_and_summarize" in WORKFLOW_REGISTRY
    assert "research_and_classify" in WORKFLOW_REGISTRY
    assert "wiki_and_answer" in WORKFLOW_REGISTRY

    for name, wf in WORKFLOW_REGISTRY.items():
        assert len(wf.nodes) >= 1
        assert wf.final_node is not None
        assert wf.final_node in {n.id for n in wf.nodes}
