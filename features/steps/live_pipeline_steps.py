from __future__ import annotations

import io
import os
import socket
import time
from contextlib import redirect_stderr
from typing import Any, Callable

from behave import given, then, when

os.environ["SLM_TRACE"] = "1"


def _llm_server_available(host: str = "127.0.0.1", port: int = 8080) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1.0):
            return True
    except OSError:
        return False


def _capture_run(fn: Callable[[], str]) -> tuple[str, list[str], float]:
    buffer = io.StringIO()
    started_at = time.perf_counter()
    with redirect_stderr(buffer):
        answer = fn()
    elapsed_ms = (time.perf_counter() - started_at) * 1000
    trace_lines = [line for line in buffer.getvalue().splitlines() if line.strip()]
    return answer, trace_lines, elapsed_ms


@given("the local LLM server is available")
def step_llm_server_available(context: Any) -> None:
    if not _llm_server_available():
        context.scenario.skip("LLM server not available at 127.0.0.1:8080")
        return

    from src.providers.openai_local import OpenAILocalClient

    context.llm_client = OpenAILocalClient()


@when('I run the assistant with "{prompt}"')
@when('I run the direct pipeline with "{prompt}"')
def step_run_unified_assistant(context: Any, prompt: str) -> None:
    from src.context import extract_text
    from src.main import run

    answer, trace_lines, elapsed_ms = _capture_run(
        lambda: extract_text(run(prompt, context.llm_client))
    )

    context.last_answer = answer
    context.last_trace_lines = trace_lines
    context.last_elapsed_ms = elapsed_ms


@when('I run workflow "{workflow}" with "{prompt}"')
def step_run_workflow(context: Any, workflow: str, prompt: str) -> None:
    from src.context import extract_text
    from src.workflow import WORKFLOW_REGISTRY, run_workflow

    selected_workflow = WORKFLOW_REGISTRY[workflow]
    answer, trace_lines, elapsed_ms = _capture_run(
        lambda: extract_text(run_workflow(selected_workflow, prompt, context.llm_client))
    )

    context.last_answer = answer
    context.last_trace_lines = trace_lines
    context.last_elapsed_ms = elapsed_ms


@when('I run the agent with "{prompt}"')
def step_run_agent(context: Any, prompt: str) -> None:
    from src.agent import run_agent
    from src.context import extract_text

    answer, trace_lines, elapsed_ms = _capture_run(
        lambda: extract_text(run_agent(prompt, context.llm_client))
    )

    context.last_answer = answer
    context.last_trace_lines = trace_lines
    context.last_elapsed_ms = elapsed_ms


@then("the answer should be usable")
def step_answer_should_be_usable(context: Any) -> None:
    from src.scoring import score_result

    score = score_result(context.last_answer)

    assert score.is_usable is True, score.reason


@then('the trace should include "{expected_path}"')
def step_trace_should_include(context: Any, expected_path: str) -> None:
    joined_trace = " ".join(context.last_trace_lines).lower()

    assert expected_path.lower() in joined_trace, joined_trace


@then('the answer should contain at least one of "{terms}"')
def step_answer_should_contain_term(context: Any, terms: str) -> None:
    expected_terms = [term.strip().lower() for term in terms.split(",") if term.strip()]
    answer = context.last_answer.lower()

    assert any(term in answer for term in expected_terms), context.last_answer
