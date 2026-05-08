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


class TestDefaultRetriever:
    def test_fetches_url_through_fetch_adapter(self, monkeypatch: pytest.MonkeyPatch) -> None:
        web_fetch = MagicMock(return_value="page about testing")
        compress = MagicMock(return_value="compressed page")
        monkeypatch.setattr("src.retrieval.web_fetch.run", web_fetch)
        monkeypatch.setattr("src.retrieval.context.compress", compress)

        result = retrieval.DefaultRetriever().fetch_context("read https://example.com")

        assert result == "compressed page"
        web_fetch.assert_called_once_with({"url": "https://example.com"})
        compress.assert_called_once()

    def test_returns_empty_context_when_no_retrieval_path_matches(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("src.retrieval.ner.lookup_entities", MagicMock(return_value=[]))

        result = retrieval.DefaultRetriever().fetch_context("hello there")

        assert result == ""
