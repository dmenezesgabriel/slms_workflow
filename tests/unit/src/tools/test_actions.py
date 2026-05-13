from __future__ import annotations

from unittest.mock import MagicMock

from src.schemas import ToolDecision
from src.tools import ToolRegistry


def _make_tool(name: str) -> MagicMock:
    tool = MagicMock()
    tool.name = name
    return tool


class TestToolActions:
    def test_builds_tool_decision_from_agent_action(self) -> None:
        registry = ToolRegistry([_make_tool("web_search")])
        result = registry.decision_for_action("web_search", "python testing")

        assert result == ToolDecision(
            needs_tool=True,
            tool_name="web_search",
            arguments={"query": "python testing"},
            reason="Agent tool action.",
        )

    def test_returns_none_for_processing_action(self) -> None:
        registry = ToolRegistry([])
        result = registry.decision_for_action("summarize", "content")

        assert result is None

    def test_executes_tool_action_through_shared_dispatcher(self) -> None:
        mock_tool = _make_tool("calculator")
        mock_tool.execute.return_value = "7"
        registry = ToolRegistry([mock_tool])

        result = registry.execute_action("calculator", "3 + 4")

        assert result is not None
        assert result.success is True
        assert result.result == "7"

    def test_identifies_tool_actions_without_exposing_registry_shape(self) -> None:
        registry = ToolRegistry([_make_tool("calculator")])
        assert registry.is_action("calculator") is True
        assert registry.is_action("answer") is False
