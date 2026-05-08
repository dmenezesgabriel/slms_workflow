from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src import ner
from src.ner import Entity

TEMPORAL_PROMPTS = [
    "What are the latest news about OpenAI?",
    "recent news on Python 3.13",
    "current news about artificial intelligence",
    "últimas notícias sobre inteligência artificial",
    "notícias recentes sobre Python",
    "what is happening today in AI?",
    "atualização mais recente do Python",
]
NON_TEMPORAL_PROMPTS = [
    "what is the capital of France",
    "explain quantum computing",
    "how does photosynthesis work",
    "what is machine learning",
    "hello there",
    "o que é Python?",
    "quem é Linus Torvalds?",
]
CASE_INSENSITIVE_TEMPORAL_PROMPT = "LATEST news about AI"
TRACE_TEXT_LIMIT = 60


class TestIsTemporal:
    @pytest.mark.parametrize("text", TEMPORAL_PROMPTS)
    def test_returns_true_when_text_has_temporal_signal(self, text: str) -> None:
        result = ner.is_temporal(text)

        assert result is True

    @pytest.mark.parametrize("text", NON_TEMPORAL_PROMPTS)
    def test_returns_false_when_text_has_no_temporal_signal(self, text: str) -> None:
        result = ner.is_temporal(text)

        assert result is False

    def test_matches_temporal_signal_without_case_sensitivity(self) -> None:
        result = ner.is_temporal(CASE_INSENSITIVE_TEMPORAL_PROMPT)

        assert result is True


class TestExtract:
    def test_delegates_to_configured_extractor(self, monkeypatch: pytest.MonkeyPatch) -> None:
        text = "Tell me about OpenAI"
        expected_entities = [Entity(text="OpenAI", label="ORG")]
        extractor = MagicMock()
        extractor.extract.return_value = expected_entities
        trace_ner = MagicMock()
        monkeypatch.setattr(ner, "_extractor", extractor)
        monkeypatch.setattr("src.ner.trace.ner", trace_ner)

        result = ner.extract(text)

        assert result == expected_entities
        assert extractor.extract.call_count == 1
        extractor.extract.assert_called_once_with(text)

    def test_records_trace_when_entities_are_extracted(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        text = "Tell me about OpenAI"
        entity = Entity(text="OpenAI", label="ORG")
        extractor = MagicMock()
        extractor.extract.return_value = [entity]
        trace_ner = MagicMock()
        monkeypatch.setattr(ner, "_extractor", extractor)
        monkeypatch.setattr("src.ner.trace.ner", trace_ner)

        ner.extract(text)

        assert trace_ner.call_count == 1
        trace_ner.assert_called_once_with(text[:TRACE_TEXT_LIMIT], [(entity.text, entity.label)])

    def test_does_not_record_trace_when_no_entities_are_extracted(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        text = "hello there"
        extractor = MagicMock()
        extractor.extract.return_value = []
        trace_ner = MagicMock()
        monkeypatch.setattr(ner, "_extractor", extractor)
        monkeypatch.setattr("src.ner.trace.ner", trace_ner)

        result = ner.extract(text)

        assert result == []
        assert trace_ner.call_count == 0


class TestLookupEntities:
    def test_returns_only_entities_with_lookup_labels(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        text = "Tell me about OpenAI and Monday"
        lookup_entity = Entity(text="OpenAI", label="ORG")
        ignored_entity = Entity(text="Monday", label="DATE")
        extract = MagicMock(return_value=[lookup_entity, ignored_entity])
        monkeypatch.setattr(ner, "extract", extract)

        result = ner.lookup_entities(text)

        assert result == [lookup_entity]
        assert extract.call_count == 1
        extract.assert_called_once_with(text)

    def test_returns_empty_list_when_extracted_entities_are_not_lookup_labels(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        text = "Tell me about Monday"
        extract = MagicMock(return_value=[Entity(text="Monday", label="DATE")])
        monkeypatch.setattr(ner, "extract", extract)

        result = ner.lookup_entities(text)

        assert result == []
        assert extract.call_count == 1
        extract.assert_called_once_with(text)
