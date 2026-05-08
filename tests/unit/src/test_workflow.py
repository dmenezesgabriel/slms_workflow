from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.dag import DagNode, DagWorkflow
from src.handlers import HANDLER_REGISTRY
from src.schemas import FinalAnswer
from src.workflow import WORKFLOW_REGISTRY, run_workflow


def test_predefined_workflows_are_dag_workflows() -> None:
    assert WORKFLOW_REGISTRY
    assert all(isinstance(workflow, DagWorkflow) for workflow in WORKFLOW_REGISTRY.values())
    assert all(workflow.final_node is not None for workflow in WORKFLOW_REGISTRY.values())


def test_run_workflow_uses_dag_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    handler = MagicMock(return_value=FinalAnswer(answer="ok"))
    monkeypatch.setitem(HANDLER_REGISTRY, "fake", handler)

    workflow = DagWorkflow(
        name="compat",
        description="compatibility wrapper",
        nodes=(DagNode("final", "fake", "hello {query}"),),
        final_node="final",
    )

    result = run_workflow(workflow, "world", MagicMock())

    assert result == FinalAnswer(answer="ok")
    handler.assert_called_once()
    assert handler.call_args.args[0] == "hello world"
