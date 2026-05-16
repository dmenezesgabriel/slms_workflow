from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.retrievers.default import DefaultRetriever
from src.techniques.retrieval import extract_direct_what_is_entity
from src.tools.base import Tool


class TestTechniquePurity:
    def test_techniques_retrieval_does_not_import_tools(self) -> None:
        import src.techniques.retrieval as r

        source = r.__file__ if hasattr(r, "__file__") else ""
        with open(source) as f:
            content = f.read()
        assert "src.tools" not in content

    def test_techniques_retrieval_has_no_default_retriever(self) -> None:
        from src.techniques import retrieval as r

        assert not hasattr(r, "DefaultRetriever")

    def test_techniques_retrieval_has_no_create_default_retriever(self) -> None:
        from src.techniques import retrieval as r

        assert not hasattr(r, "create_default_retriever")

    def test_retrievers_default_exports_default_retriever(self) -> None:
        from src.retrievers.default import DefaultRetriever

        assert DefaultRetriever is not None

    def test_retrievers_default_exports_create_default_retriever(self) -> None:
        from src.retrievers.default import create_default_retriever

        assert create_default_retriever is not None


class TestProperNounFallback:
    @pytest.mark.parametrize(
        "prompt,expected",
        [
            ("What is spaCy?", "spaCy"),
            ("What is FastAPI?", "FastAPI"),
            ("what is spacy?", "spacy"),
            ("what is the capital of France", None),
        ],
    )
    def test_extracts_only_direct_what_is_entities(self, prompt: str, expected: str | None) -> None:
        assert extract_direct_what_is_entity(prompt) == expected


def _make_tool() -> Tool:
    tool = MagicMock()
    tool.name = "tool"
    tool.description = "tool"
    tool.parameters = {}
    tool.prompt_line.return_value = "tool"
    tool.execute.return_value = ""
    return tool


def _make_retriever(
    web_fetch: Tool | None = None,
    web_search: Tool | None = None,
    wikipedia: Tool | None = None,
) -> DefaultRetriever:
    return DefaultRetriever(
        web_fetch=web_fetch or _make_tool(),
        web_search=web_search or _make_tool(),
        wikipedia=wikipedia or _make_tool(),
    )


class TestDefaultRetriever:
    def test_fetches_url_through_fetch_adapter(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_fetch = MagicMock()
        mock_fetch.execute.return_value = "page about testing"
        compress = MagicMock(return_value="compressed page")
        monkeypatch.setattr("src.retrievers.default.context.compress", compress)

        result = _make_retriever(web_fetch=mock_fetch).fetch_context("read https://example.com")

        assert result == "compressed page"
        mock_fetch.execute.assert_called_once_with({"url": "https://example.com"})
        compress.assert_called_once()

    def test_protected_baseline_fetches_direct_what_is_entity_from_wikipedia(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_wikipedia = MagicMock()
        mock_wikipedia.execute.return_value = "spaCy is an NLP library."
        compress = MagicMock(return_value="compressed wiki context")
        monkeypatch.setattr("src.retrievers.default.context.compress", compress)
        monkeypatch.setattr(
            "src.retrievers.default.ner.best_lookup_entity", MagicMock(return_value=None)
        )

        result = _make_retriever(wikipedia=mock_wikipedia).fetch_context("What is spaCy?")

        assert result == "compressed wiki context"
        mock_wikipedia.execute.assert_called_once_with({"query": "spaCy"})
        compress.assert_called_once_with(
            "spaCy is an NLP library.",
            query="What is spaCy?",
            max_sentences=6,
        )

    def test_target_improvement_lowercase_direct_what_is_prompt_uses_wikipedia(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_wikipedia = MagicMock()
        mock_wikipedia.execute.return_value = "spaCy is an NLP library."
        compress = MagicMock(return_value="compressed wiki context")
        monkeypatch.setattr("src.retrievers.default.context.compress", compress)
        monkeypatch.setattr(
            "src.retrievers.default.ner.best_lookup_entity", MagicMock(return_value=None)
        )

        result = _make_retriever(wikipedia=mock_wikipedia).fetch_context("what is spacy?")

        assert result == "compressed wiki context"
        mock_wikipedia.execute.assert_called_once_with({"query": "spacy"})

    def test_returns_empty_context_when_no_retrieval_path_matches(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "src.retrievers.default.ner.best_lookup_entity", MagicMock(return_value=None)
        )

        result = _make_retriever().fetch_context("hello there")

        assert result == ""

    def test_reference_question_uses_acquired_search_evidence(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_search = MagicMock()
        mock_search.execute.return_value = "Title: Result\nSnippet: useful clue text"
        compress = MagicMock(return_value="compressed search context")
        monkeypatch.setattr("src.retrievers.default.context.compress", compress)

        prompt = "which song says hello from the other side?"
        result = _make_retriever(web_search=mock_search).fetch_context(prompt)

        assert result == "compressed search context"
        assert mock_search.execute.call_count == 2
        mock_search.execute.assert_any_call({"query": prompt, "max_results": 5})
        mock_search.execute.assert_any_call(
            {"query": "hello from other side quote source", "max_results": 5}
        )
        compress.assert_called_once_with(
            "Title: Result\nSnippet: useful clue text\n\nTitle: Result\nSnippet: useful clue text",
            query=prompt,
            max_sentences=8,
        )

    def test_programming_language_creator_prompt_uses_focused_web_search(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_search = MagicMock()
        mock_search.execute.return_value = "Title: About Python\nSnippet: Guido van Rossum created Python and it was first released in 1991."
        compress = MagicMock(return_value="compressed search context")
        monkeypatch.setattr("src.retrievers.default.context.compress", compress)
        monkeypatch.setattr(
            "src.retrievers.default.ner.best_lookup_entity",
            MagicMock(return_value=MagicMock(text="Python", label="MISC")),
        )
        monkeypatch.setattr("src.retrievers.default.ner.is_temporal", MagicMock(return_value=False))

        prompt = "Who created the Python programming language and when was it first released?"
        result = _make_retriever(web_search=mock_search).fetch_context(prompt)

        assert result == "compressed search context"
        mock_search.execute.assert_called_once_with(
            {
                "query": "Python programming language creator first released",
                "max_results": 3,
            }
        )
        compress.assert_called_once_with(
            "Title: About Python\nSnippet: Guido van Rossum created Python and it was first released in 1991.",
            query=prompt,
            max_sentences=6,
        )
