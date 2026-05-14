from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.dag import DagNode, DagWorkflow, WorkflowGraph, run_dag_workflow
from src.llm_client import LLMClient
from src.schemas import FinalAnswer
from src.workflow import get_workflow_registry, run_workflow, set_node_registry


@pytest.fixture(scope="module")
def _registry() -> None:
    """Build and set the node registry once for all workflow tests."""
    from src.bootstrap import build_node_registry, build_tool_registry

    set_node_registry(build_node_registry(tool_registry=build_tool_registry()))
    return None


def test_predefined_workflows_are_dag_workflows(_registry: None) -> None:
    wf_registry = get_workflow_registry()
    assert wf_registry
    assert all(isinstance(workflow, WorkflowGraph) for workflow in wf_registry.values())
    assert all(isinstance(workflow, DagWorkflow) for workflow in wf_registry.values())
    assert all(workflow.final_node is not None for workflow in wf_registry.values())


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


def test_workflow_registry_has_expected_structure(_registry: None) -> None:
    wf_registry = get_workflow_registry()
    assert "research_and_summarize" in wf_registry
    assert "fetch_and_summarize" in wf_registry
    assert "research_and_classify" in wf_registry
    assert "wiki_and_answer" in wf_registry

    for name, wf in wf_registry.items():
        assert len(wf.nodes) >= 1
        assert wf.final_node is not None
        assert wf.final_node in {n.id for n in wf.nodes}
