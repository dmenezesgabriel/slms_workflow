from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.schemas import ToolDecision
from src.tools import decision_for_action, execute_action, is_tool_action


class TestToolActions:
    def test_builds_tool_decision_from_agent_action(self) -> None:
        result = decision_for_action("web_search", "python testing")

        assert result == ToolDecision(
            needs_tool=True,
            tool_name="web_search",
            arguments={"query": "python testing"},
            reason="Agent tool action.",
        )

    def test_returns_none_for_processing_action(self) -> None:
        result = decision_for_action("summarize", "content")

        assert result is None

    def test_executes_tool_action_through_shared_dispatcher(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        tool_result = object()
        execute = MagicMock(return_value=tool_result)
        monkeypatch.setattr("src.tools.execute", execute)

        result = execute_action("calculator", "3 + 4")

        assert result is tool_result
        execute.assert_called_once_with(
            ToolDecision(
                needs_tool=True,
                tool_name="calculator",
                arguments={"expression": "3 + 4"},
                reason="Agent tool action.",
            )
        )

    def test_identifies_tool_actions_without_exposing_registry_shape(self) -> None:
        assert is_tool_action("calculator") is True
        assert is_tool_action("answer") is False
