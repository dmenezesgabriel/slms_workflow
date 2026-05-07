"""Unit tests for the deterministic tool-selection paths in the function_calling handler."""

from __future__ import annotations

import pytest

from app.handlers.function_calling import _extract_math, deterministic_decision


class TestMathExtraction:
    @pytest.mark.parametrize(
        "text,expected_expr",
        [
            # Symbol forms
            ("15 + 7", "15 + 7"),
            ("144 / 12", "144 / 12"),
            ("3 * 5", "3 * 5"),
            ("10 - 3", "10 - 3"),
            # Natural-language English
            ("what is 3 times 5", "3 * 5"),
            ("144 divided by 12", "144 / 12"),
            ("3 plus 5", "3 + 5"),
            ("10 minus 3", "10 - 3"),
            ("2 multiplied by 7", "2 * 7"),
            # Natural-language Portuguese
            ("3 mais 5", "3 + 5"),
            ("10 menos 3", "10 - 3"),
            ("3 vezes 5", "3 * 5"),
            ("144 dividido por 12", "144 / 12"),
        ],
    )
    def test_extract_math(self, text: str, expected_expr: str) -> None:
        result = _extract_math(text)
        assert result is not None, f"_extract_math returned None for {text!r}"
        assert result.strip() == expected_expr, (
            f"Expected {expected_expr!r}, got {result.strip()!r}"
        )

    @pytest.mark.parametrize(
        "text",
        [
            "what is Python?",
            "search for machine learning",
            "hello there",
            "summarize this",
        ],
    )
    def test_returns_none_for_non_math(self, text: str) -> None:
        assert _extract_math(text) is None, f"_extract_math should return None for {text!r}"


class TestDeterministicToolSelection:
    @pytest.mark.parametrize(
        "text,expected_tool,arg_key,arg_substr",
        [
            # web_search
            ("search for Python tutorials", "web_search", "query", "Python tutorials"),
            ("search for llama.cpp", "web_search", "query", "llama.cpp"),
            ("search the web for climate change", "web_search", "query", "climate change"),
            ("search about Rust programming", "web_search", "query", "Rust"),
            # wikipedia
            ("look up Python on Wikipedia", "wikipedia", "query", "Python"),
            ("find the Wikipedia article about machine learning", "wikipedia", "query", "machine learning"),
            ("Wikipedia article about Brazil", "wikipedia", "query", "Brazil"),
            # web_fetch
            ("fetch https://example.com", "web_fetch", "url", "https://example.com"),
            ("fetch https://docs.python.org/3/", "web_fetch", "url", "https://docs.python.org"),
            # calculator
            ("what is 15 + 7", "calculator", "expression", "15"),
            ("144 divided by 12", "calculator", "expression", "144"),
        ],
    )
    def test_tool_selected_correctly(
        self, text: str, expected_tool: str, arg_key: str, arg_substr: str
    ) -> None:
        decision = deterministic_decision(text)
        assert decision is not None, f"deterministic_decision returned None for {text!r}"
        assert decision.needs_tool is True
        assert decision.tool_name == expected_tool, (
            f"Expected tool {expected_tool!r}, got {decision.tool_name!r}"
        )
        arg_val = str(decision.arguments.get(arg_key, ""))
        assert arg_substr.lower() in arg_val.lower(), (
            f"Expected {arg_substr!r} in {arg_key}={arg_val!r}"
        )

    @pytest.mark.parametrize(
        "text",
        [
            "hello there",
            "how are you",
            "explain machine learning",
        ],
    )
    def test_returns_none_for_ambiguous_input(self, text: str) -> None:
        decision = deterministic_decision(text)
        assert decision is None, (
            f"deterministic_decision should return None for {text!r}, got {decision}"
        )

    def test_math_takes_priority_over_search(self) -> None:
        # If the text contains both math and search-like words, math wins
        decision = deterministic_decision("calculate 3 + 5 and search for results")
        assert decision is not None
        assert decision.tool_name == "calculator"

    def test_decision_always_has_reason(self) -> None:
        decision = deterministic_decision("search for Python")
        assert decision is not None
        assert decision.reason, "ToolDecision must always include a reason string"
