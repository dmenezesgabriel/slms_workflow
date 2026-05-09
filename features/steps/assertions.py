"""Assertion ports for BDD tests.

Provides port interfaces for evaluating execution results:
- Answer usability scoring
- Trace path verification
- Content verification
- Acceptance criteria evaluation

This module follows the Ports & Adapters pattern by defining
evaluation interfaces that step definitions depend on.
"""

from __future__ import annotations

from typing import Any


class AssertionPort:
    """Port interface for result evaluation."""

    @staticmethod
    def is_answer_usable(answer: str) -> tuple[bool, str]:
        from src.scoring import score_result

        score = score_result(answer)
        return score.is_usable, score.reason

    @staticmethod
    def get_trace_path(result: Any) -> str:
        if not hasattr(result, "trace_lines"):
            return ""
        return " ".join(result.trace_lines).lower()

    @staticmethod
    def contains_term(answer: str, terms: list[str]) -> bool:
        lower_answer = answer.lower()
        return any(term in lower_answer for term in terms)

    @staticmethod
    def parse_terms(terms_string: str) -> list[str]:
        return [term.strip().lower() for term in terms_string.split(",") if term.strip()]


def assert_answer_usable(context: Any) -> None:
    result = context.last_result
    usable, reason = AssertionPort.is_answer_usable(result.answer)
    assert usable is True, reason


def assert_trace_includes(context: Any, expected_path: str) -> None:
    result = context.last_result
    trace_path = AssertionPort.get_trace_path(result)
    assert expected_path.lower() in trace_path, trace_path


def assert_answer_contains_term(context: Any, terms_string: str) -> None:
    result = context.last_result
    terms = AssertionPort.parse_terms(terms_string)
    contains = AssertionPort.contains_term(result.answer, terms)
    assert contains is True, result.answer


def assert_acceptance_case_passes(context: Any) -> None:
    evaluation = context.last_evaluation
    assert evaluation.passed is True, {
        "failures": evaluation.failures,
        "answer": evaluation.answer,
        "trace": evaluation.trace_lines,
        "ground_truth": evaluation.case.ground_truth,
    }


def assert_response_time_under(context: Any, seconds: float) -> None:
    result = context.last_result
    assert (
        result.elapsed_ms <= seconds * 1000
    ), f"Response took {result.elapsed_ms/1000:.1f}s, expected under {seconds}s"


def assert_latency_under(context: Any, seconds: float) -> None:
    result = context.last_result
    assert (
        result.elapsed_ms <= seconds * 1000
    ), f"Latency {result.elapsed_ms/1000:.1f}s exceeded {seconds}s"


def assert_trace_includes_any(context: Any, paths: list[str]) -> None:
    result = context.last_result
    trace_path = AssertionPort.get_trace_path(result)
    assert any(
        path.lower() in trace_path for path in paths
    ), f"Trace {trace_path} doesn't contain any of {paths}"
