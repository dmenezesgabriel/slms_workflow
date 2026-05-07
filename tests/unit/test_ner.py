"""Unit tests for NER entity extraction and temporal-signal detection."""

from __future__ import annotations

import pytest

from app.ner import is_temporal, lookup_entities


class TestIsTemporalDetection:
    @pytest.mark.parametrize(
        "text",
        [
            "What are the latest news about OpenAI?",
            "recent news on Python 3.13",
            "current news about artificial intelligence",
            "últimas notícias sobre inteligência artificial",
            "notícias recentes sobre Python",
            "what is happening today in AI?",
            "atualização mais recente do Python",
        ],
    )
    def test_temporal_signals_detected(self, text: str) -> None:
        assert is_temporal(text), f"Expected is_temporal=True for {text!r}"

    @pytest.mark.parametrize(
        "text",
        [
            "what is the capital of France",
            "explain quantum computing",
            "how does photosynthesis work",
            "what is machine learning",
            "hello there",
            "o que é Python?",
            "quem é Linus Torvalds?",
        ],
    )
    def test_non_temporal_not_detected(self, text: str) -> None:
        assert not is_temporal(text), f"Expected is_temporal=False for {text!r}"

    def test_case_insensitive(self) -> None:
        assert is_temporal("LATEST news about AI")
        assert is_temporal("Latest")
        assert is_temporal("TODAY")

    @pytest.mark.parametrize("keyword", ["latest", "current", "recent", "today", "news", "now"])
    def test_english_keywords(self, keyword: str) -> None:
        assert is_temporal(f"tell me the {keyword} updates")

    @pytest.mark.parametrize("keyword", ["últimas", "atual", "recente", "hoje", "notícias"])
    def test_portuguese_keywords(self, keyword: str) -> None:
        assert is_temporal(f"quais são as {keyword} novidades")


class TestLookupEntities:
    """These tests require the xx_ent_wiki_sm spaCy model to be installed."""

    @pytest.mark.parametrize(
        "text,expected_fragment",
        [
            ("Tell me about OpenAI", "OpenAI"),
            ("Who is Sam Altman?", "Sam Altman"),
            ("Where is Rio de Janeiro located?", "Rio de Janeiro"),
            ("Tell me about Linus Torvalds", "Linus Torvalds"),
            ("Look up Microsoft on Wikipedia", "Microsoft"),
        ],
    )
    def test_known_entities_extracted(self, text: str, expected_fragment: str) -> None:
        try:
            entities = lookup_entities(text)
        except RuntimeError as exc:
            pytest.skip(f"spaCy model not available: {exc}")

        entity_texts = [e.text.lower() for e in entities]
        assert any(expected_fragment.lower() in t for t in entity_texts), (
            f"Expected entity fragment {expected_fragment!r} in {entity_texts}"
        )

    def test_empty_text_returns_empty_list(self) -> None:
        try:
            entities = lookup_entities("")
        except RuntimeError as exc:
            pytest.skip(f"spaCy model not available: {exc}")
        assert entities == []
