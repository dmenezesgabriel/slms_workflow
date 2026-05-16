from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src import tool_selection
from src.schemas import ToolDecision
from src.techniques import ner
from src.techniques.ner import Entity


class TestProtectedBaselineToolSelection:
    @pytest.mark.parametrize(
        ("prompt", "expected_tool", "expected_arguments"),
        [
            (
                "search the web for python decorators",
                "web_search",
                {"query": "python decorators"},
            ),
            (
                "look up the wikipedia article about Ada Lovelace",
                "wikipedia",
                {"query": "Ada Lovelace"},
            ),
            (
                "fetch https://example.com/docs",
                "web_fetch",
                {"url": "https://example.com/docs"},
            ),
        ],
    )
    def test_deterministic_tool_matches_current_explicit_patterns(
        self, prompt: str, expected_tool: str, expected_arguments: dict[str, str]
    ) -> None:
        result = tool_selection.deterministic_tool(prompt)

        assert result is not None
        assert result.tool_name == expected_tool
        assert result.arguments == expected_arguments

    def test_ner_tool_prefers_wikipedia_for_entity_lookup(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        entity = Entity(text="Ada Lovelace", label="PER")
        monkeypatch.setattr(ner, "lookup_entities", MagicMock(return_value=[entity]))
        monkeypatch.setattr(ner, "best_lookup_entity", MagicMock(return_value=entity))
        monkeypatch.setattr(ner, "is_temporal", MagicMock(return_value=False))

        result = tool_selection.ner_tool("tell me about Ada Lovelace")

        assert result == ToolDecision(
            needs_tool=True,
            tool_name="wikipedia",
            arguments={"query": "Ada Lovelace"},
            reason="NER PER: 'Ada Lovelace'.",
        )

    def test_ner_tool_uses_web_search_for_temporal_requests(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        entity = Entity(text="OpenAI", label="ORG")
        monkeypatch.setattr(ner, "lookup_entities", MagicMock(return_value=[entity]))
        monkeypatch.setattr(ner, "best_lookup_entity", MagicMock(return_value=entity))
        monkeypatch.setattr(ner, "is_temporal", MagicMock(return_value=True))

        result = tool_selection.ner_tool("tell me about the latest OpenAI update")

        assert result == ToolDecision(
            needs_tool=True,
            tool_name="web_search",
            arguments={"query": "OpenAI"},
            reason="NER ORG: 'OpenAI'.",
        )


class TestImprovedToolSelection:
    @pytest.mark.parametrize(
        ("prompt", "expected_tool", "expected_query"),
        [
            ("me fale sobre openai", "wikipedia", "openai"),
            ("o que e spacy", "wikipedia", "spacy"),
            ("pesquise por python decorators", "web_search", "python decorators"),
        ],
    )
    def test_deterministic_tool_handles_portuguese_and_lowercase_lookup_cases(
        self, prompt: str, expected_tool: str, expected_query: str
    ) -> None:
        result = tool_selection.deterministic_tool(prompt)

        assert result is not None
        assert result.tool_name == expected_tool
        assert expected_query in str(result.arguments.get("query", "")).lower()

    def test_ner_tool_uses_ranked_entity_instead_of_first_entity(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        entities = [Entity(text="Ada", label="PER"), Entity(text="Ada Lovelace", label="PER")]
        monkeypatch.setattr(ner, "lookup_entities", MagicMock(return_value=entities))
        monkeypatch.setattr(
            ner,
            "best_lookup_entity",
            MagicMock(return_value=entities[1]),
        )
        monkeypatch.setattr(ner, "is_temporal", MagicMock(return_value=False))

        result = tool_selection.ner_tool("tell me about Ada Lovelace")

        assert result is not None
        assert result.tool_name == "wikipedia"
        assert result.arguments == {"query": "Ada Lovelace"}

    def test_current_ambiguous_prompt_still_returns_no_tool_decision(self) -> None:
        tool_registry = MagicMock()
        tool_registry.__contains__.return_value = True

        result = tool_selection.deterministic_decision("hello there", tool_registry)

        assert result is None
