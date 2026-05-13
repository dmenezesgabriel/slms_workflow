"""Execution ports for BDD tests.

Provides port interfaces for running the application:
- Unified assistant execution
- Agent loop execution
- Workflow execution

This module follows the Ports & Adapters pattern by defining
application interfaces that step definitions depend on.
"""

from __future__ import annotations

import io
import os
import time
from contextlib import redirect_stderr
from dataclasses import dataclass
from typing import Any, Callable

os.environ["SLM_TRACE"] = "1"


@dataclass(frozen=True)
class ExecutionResult:
    """Immutable result of a pipeline execution."""

    answer: str
    trace_lines: list[str]
    elapsed_ms: float


class ExecutionPort:
    """Port interface for application execution."""

    @staticmethod
    def run_unified_assistant(prompt: str, llm_client: Any) -> ExecutionResult:
        from src.context import extract_text
        from src.main import run

        return _capture_execution(lambda: extract_text(run(prompt, llm_client)))

    @staticmethod
    def run_agent(prompt: str, llm_client: Any) -> ExecutionResult:
        from src.agent import run_agent
        from src.context import extract_text

        return _capture_execution(lambda: extract_text(run_agent(prompt, llm_client)))

    @staticmethod
    def run_workflow(workflow_name: str, prompt: str, llm_client: Any) -> ExecutionResult:
        from src.context import extract_text
        from src.workflow import WORKFLOW_REGISTRY, run_workflow

        workflow = WORKFLOW_REGISTRY[workflow_name]
        return _capture_execution(lambda: extract_text(run_workflow(workflow, prompt, llm_client)))

    @staticmethod
    def run_acceptance_case(case_id: str, llm_client: Any) -> tuple[ExecutionResult, Any]:
        from evals.acceptance import CASE_BY_ID, _evaluate
        from src.context import extract_text
        from src.main import run

        case = CASE_BY_ID[case_id]
        result = _capture_execution(lambda: extract_text(run(case.prompt, llm_client)))
        evaluation_result = _evaluate(case, result.answer, result.trace_lines, result.elapsed_ms)
        return result, evaluation_result


def _capture_execution(fn: Callable[[], str]) -> ExecutionResult:
    from src import trace as trace_module

    trace_module.init()
    buffer = io.StringIO()
    started_at = time.perf_counter()
    with redirect_stderr(buffer):
        answer = fn()
    elapsed_ms = (time.perf_counter() - started_at) * 1000
    trace_lines = [line for line in buffer.getvalue().splitlines() if line.strip()]
    return ExecutionResult(answer=answer, trace_lines=trace_lines, elapsed_ms=elapsed_ms)


def execute_unified_assistant(context: Any, prompt: str) -> None:
    result = ExecutionPort.run_unified_assistant(prompt, context.llm_client)
    context.last_result = result


def execute_agent(context: Any, prompt: str) -> None:
    result = ExecutionPort.run_agent(prompt, context.llm_client)
    context.last_result = result


def execute_workflow(context: Any, workflow_name: str, prompt: str) -> None:
    result = ExecutionPort.run_workflow(workflow_name, prompt, context.llm_client)
    context.last_result = result


def execute_acceptance_case(context: Any, case_id: str) -> None:
    result, evaluation = ExecutionPort.run_acceptance_case(case_id, context.llm_client)
    context.last_result = result
    context.last_evaluation = evaluation
