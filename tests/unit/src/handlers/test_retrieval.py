from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src import retrieval


class TestProperNounFallback:
    @pytest.mark.parametrize(
        "prompt,expected",
        [
            ("What is spaCy?", "spaCy"),
            ("What is FastAPI?", "FastAPI"),
            ("what is the capital of France", None),
        ],
    )
    def test_extracts_only_direct_what_is_entities(self, prompt: str, expected: str | None) -> None:
        assert retrieval.extract_direct_what_is_entity(prompt) == expected


def _make_retriever(
    web_fetch: object = None,
    web_search: object = None,
    wikipedia: object = None,
) -> retrieval.DefaultRetriever:
    return retrieval.DefaultRetriever(
        web_fetch=web_fetch or MagicMock(),
        web_search=web_search or MagicMock(),
        wikipedia=wikipedia or MagicMock(),
    )


class TestDefaultRetriever:
    def test_fetches_url_through_fetch_adapter(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_fetch = MagicMock()
        mock_fetch.execute.return_value = "page about testing"
        compress = MagicMock(return_value="compressed page")
        monkeypatch.setattr("src.retrieval.context.compress", compress)

        result = _make_retriever(web_fetch=mock_fetch).fetch_context("read https://example.com")

        assert result == "compressed page"
        mock_fetch.execute.assert_called_once_with({"url": "https://example.com"})
        compress.assert_called_once()

    def test_returns_empty_context_when_no_retrieval_path_matches(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("src.retrieval.ner.lookup_entities", MagicMock(return_value=[]))

        result = _make_retriever().fetch_context("hello there")

        assert result == ""

    def test_reference_question_uses_acquired_search_evidence(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_search = MagicMock()
        mock_search.execute.return_value = "Title: Result\nSnippet: useful clue text"
        compress = MagicMock(return_value="compressed search context")
        monkeypatch.setattr("src.retrieval.context.compress", compress)

        prompt = "which song says hello from the other side?"
        result = _make_retriever(web_search=mock_search).fetch_context(prompt)

        assert result.startswith("Likely answer inferred from web evidence: Result")
        assert mock_search.execute.call_count == 2
        mock_search.execute.assert_any_call({"query": prompt, "max_results": 5})
        mock_search.execute.assert_any_call(
            {"query": "hello from other side quote source", "max_results": 5}
        )
        compress.assert_called_once_with(
            "Title: Result\nSnippet: useful clue text\n\nTitle: Result\nSnippet: useful clue text",
            query=prompt,
            max_sentences=retrieval._MAX_CONTEXT_SENTENCES,
        )
