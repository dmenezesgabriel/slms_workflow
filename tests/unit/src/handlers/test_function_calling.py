from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.handlers import function_calling
from src.schemas import FinalAnswer, ToolDecision

MATH_TEXT = "what is 3 plus 5"
MATH_EXPRESSION = "3 + 5"
SEARCH_TEXT = "search for Python tutorials"
SEARCH_QUERY = "Python tutorials"
WIKIPEDIA_TEXT = "look up Python on Wikipedia"
WIKIPEDIA_QUERY = "Python"
FETCH_TEXT = "fetch https://example.com"
FETCH_URL = "https://example.com"
AMBIGUOUS_TEXT = "hello there"
DISPATCHED_ANSWER = FinalAnswer(answer="dispatched")
NO_TOOL_DECISION = ToolDecision(needs_tool=False, tool_name="none", arguments={}, reason="No tool.")
SEARCH_DECISION = ToolDecision(
    needs_tool=True,
    tool_name="web_search",
    arguments={"query": SEARCH_QUERY},
    reason="Deterministic search pattern.",
)
CALCULATOR_DECISION = ToolDecision(
    needs_tool=True,
    tool_name="calculator",
    arguments={"expression": MATH_EXPRESSION},
    reason="Deterministic math extraction.",
)
WIKIPEDIA_DECISION = ToolDecision(
    needs_tool=True,
    tool_name="wikipedia",
    arguments={"query": WIKIPEDIA_QUERY},
    reason="Deterministic Wikipedia pattern.",
)


class TestExtractMath:
    @pytest.mark.parametrize(
        "text,expected_expression",
        [
            ("15 + 7", "15 + 7"),
            ("144 / 12", "144 / 12"),
            ("3 * 5", "3 * 5"),
            ("10 - 3", "10 - 3"),
            ("what is 3 times 5", "3 * 5"),
            ("144 divided by 12", "144 / 12"),
            ("3 plus 5", "3 + 5"),
            ("10 minus 3", "10 - 3"),
            ("2 multiplied by 7", "2 * 7"),
            ("3 mais 5", "3 + 5"),
            ("10 menos 3", "10 - 3"),
            ("3 vezes 5", "3 * 5"),
            ("144 dividido por 12", "144 / 12"),
        ],
    )
    def test_returns_expression_when_text_contains_supported_math(
        self, text: str, expected_expression: str
    ) -> None:
        result = function_calling._extract_math(text)

        assert result == expected_expression

    @pytest.mark.parametrize(
        "text",
        [
            "what is Python?",
            "search for machine learning",
            "hello there",
            "summarize this",
        ],
    )
    def test_returns_none_when_text_has_no_math(self, text: str) -> None:
        result = function_calling._extract_math(text)

        assert result is None


class TestDeterministicTool:
    @pytest.mark.parametrize(
        "text,expected_tool,expected_arguments",
        [
            (SEARCH_TEXT, "web_search", {"query": SEARCH_QUERY}),
            (WIKIPEDIA_TEXT, "wikipedia", {"query": WIKIPEDIA_QUERY}),
            (FETCH_TEXT, "web_fetch", {"url": FETCH_URL}),
        ],
    )
    def test_returns_tool_decision_when_text_matches_explicit_tool_pattern(
        self, text: str, expected_tool: str, expected_arguments: dict[str, str]
    ) -> None:
        result = function_calling._deterministic_tool(text)

        assert result is not None
        assert result.needs_tool is True
        assert result.tool_name == expected_tool
        assert result.arguments == expected_arguments

    def test_returns_none_when_text_does_not_match_explicit_tool_pattern(self) -> None:
        result = function_calling._deterministic_tool(AMBIGUOUS_TEXT)

        assert result is None


class TestDeterministicDecision:
    def test_returns_calculator_decision_when_math_is_extracted(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        extract_math = MagicMock(return_value=MATH_EXPRESSION)
        deterministic_tool = MagicMock()
        ner_tool = MagicMock()
        monkeypatch.setattr(function_calling, "_extract_math", extract_math)
        monkeypatch.setattr(function_calling, "_deterministic_tool", deterministic_tool)
        monkeypatch.setattr(function_calling, "_ner_tool", ner_tool)
        monkeypatch.setattr(function_calling, "TOOL_REGISTRY", {"calculator": object()})

        result = function_calling.deterministic_decision(MATH_TEXT)

        assert result is not None
        assert result.tool_name == "calculator"
        assert result.arguments == {"expression": MATH_EXPRESSION}
        assert extract_math.call_count == 1
        extract_math.assert_called_once_with(MATH_TEXT)
        assert deterministic_tool.call_count == 0
        assert ner_tool.call_count == 0

    def test_returns_regex_decision_when_math_is_not_extracted(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        extract_math = MagicMock(return_value=None)
        deterministic_tool = MagicMock(return_value=SEARCH_DECISION)
        ner_tool = MagicMock()
        monkeypatch.setattr(function_calling, "_extract_math", extract_math)
        monkeypatch.setattr(function_calling, "_deterministic_tool", deterministic_tool)
        monkeypatch.setattr(function_calling, "_ner_tool", ner_tool)

        result = function_calling.deterministic_decision(SEARCH_TEXT)

        assert result == SEARCH_DECISION
        assert extract_math.call_count == 1
        extract_math.assert_called_once_with(SEARCH_TEXT)
        assert deterministic_tool.call_count == 1
        deterministic_tool.assert_called_once_with(SEARCH_TEXT)
        assert ner_tool.call_count == 0

    def test_returns_ner_decision_when_regex_decision_is_not_available(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        extract_math = MagicMock(return_value=None)
        deterministic_tool = MagicMock(return_value=None)
        ner_tool = MagicMock(return_value=WIKIPEDIA_DECISION)
        monkeypatch.setattr(function_calling, "_extract_math", extract_math)
        monkeypatch.setattr(function_calling, "_deterministic_tool", deterministic_tool)
        monkeypatch.setattr(function_calling, "_ner_tool", ner_tool)

        result = function_calling.deterministic_decision(WIKIPEDIA_TEXT)

        assert result == WIKIPEDIA_DECISION
        assert extract_math.call_count == 1
        extract_math.assert_called_once_with(WIKIPEDIA_TEXT)
        assert deterministic_tool.call_count == 1
        deterministic_tool.assert_called_once_with(WIKIPEDIA_TEXT)
        assert ner_tool.call_count == 1
        ner_tool.assert_called_once_with(WIKIPEDIA_TEXT)

    def test_returns_none_when_no_deterministic_path_matches(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        extract_math = MagicMock(return_value=None)
        deterministic_tool = MagicMock(return_value=None)
        ner_tool = MagicMock(return_value=None)
        monkeypatch.setattr(function_calling, "_extract_math", extract_math)
        monkeypatch.setattr(function_calling, "_deterministic_tool", deterministic_tool)
        monkeypatch.setattr(function_calling, "_ner_tool", ner_tool)

        result = function_calling.deterministic_decision(AMBIGUOUS_TEXT)

        assert result is None
        assert extract_math.call_count == 1
        extract_math.assert_called_once_with(AMBIGUOUS_TEXT)
        assert deterministic_tool.call_count == 1
        deterministic_tool.assert_called_once_with(AMBIGUOUS_TEXT)
        assert ner_tool.call_count == 1
        ner_tool.assert_called_once_with(AMBIGUOUS_TEXT)


class TestHandle:
    def test_dispatches_calculator_decision_when_math_is_extracted(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        llm = MagicMock()
        extract_math = MagicMock(return_value=MATH_EXPRESSION)
        dispatch = MagicMock(return_value=DISPATCHED_ANSWER)
        tool_decision_class = MagicMock(return_value=CALCULATOR_DECISION)
        fast_path = MagicMock()
        monkeypatch.setattr(function_calling, "_extract_math", extract_math)
        monkeypatch.setattr(function_calling, "_dispatch", dispatch)
        monkeypatch.setattr(function_calling, "ToolDecision", tool_decision_class)
        monkeypatch.setattr("src.handlers.function_calling.trace.fast_path", fast_path)
        monkeypatch.setattr(function_calling, "TOOL_REGISTRY", {"calculator": object()})

        result = function_calling.handle(MATH_TEXT, llm)

        assert result == DISPATCHED_ANSWER
        assert extract_math.call_count == 1
        extract_math.assert_called_once_with(MATH_TEXT)
        assert tool_decision_class.call_count == 1
        tool_decision_class.assert_called_once_with(
            needs_tool=True,
            tool_name="calculator",
            arguments={"expression": MATH_EXPRESSION},
            reason="Deterministic math extraction.",
        )
        assert dispatch.call_count == 1
        dispatch.assert_called_once_with(CALCULATOR_DECISION)
        assert fast_path.call_count == 1
        fast_path.assert_called_once_with("math_regex", MATH_EXPRESSION)
        llm.structured.assert_not_called()

    def test_returns_decision_reason_when_llm_selects_no_tool(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        llm = MagicMock()
        llm.structured.return_value = NO_TOOL_DECISION
        extract_math = MagicMock(return_value=None)
        deterministic_tool = MagicMock(return_value=None)
        ner_tool = MagicMock(return_value=None)
        llm_request = MagicMock()
        llm_request_class = MagicMock(return_value=llm_request)
        monkeypatch.setattr(function_calling, "_extract_math", extract_math)
        monkeypatch.setattr(function_calling, "_deterministic_tool", deterministic_tool)
        monkeypatch.setattr(function_calling, "_ner_tool", ner_tool)
        monkeypatch.setattr(function_calling, "LLMRequest", llm_request_class)

        result = function_calling.handle(AMBIGUOUS_TEXT, llm)

        assert result == FinalAnswer(answer=NO_TOOL_DECISION.reason)
        assert llm_request_class.call_count == 1
        assert llm.structured.call_count == 1
        llm.structured.assert_called_once_with(llm_request, ToolDecision)
        extract_math.assert_called_once_with(AMBIGUOUS_TEXT)
        deterministic_tool.assert_called_once_with(AMBIGUOUS_TEXT)
        ner_tool.assert_called_once_with(AMBIGUOUS_TEXT)
