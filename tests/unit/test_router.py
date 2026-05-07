"""Unit tests for the TF-IDF intent router."""

from __future__ import annotations

import pytest

from app.router import classify_ml, _FAST_ROUTE_THRESHOLD


class TestClassifyML:
    @pytest.mark.parametrize(
        "prompt,expected",
        [
            ("summarize this", "summarization"),
            ("tl;dr", "summarization"),
            ("give me a summary", "summarization"),
            ("resuma este texto", "summarization"),
            ("me dá um resumo", "summarization"),
            ("what is the capital of France", "question_answering"),
            ("how does photosynthesis work", "question_answering"),
            ("o que é machine learning", "question_answering"),
            ("qual é a capital do Brasil", "question_answering"),
            ("calculate 15 + 7", "function_calling"),
            ("search for Python tutorials", "function_calling"),
            ("look up Python on Wikipedia", "function_calling"),
            ("calcule 15 mais 7", "function_calling"),
            ("classify this review as positive", "classification"),
            ("determine the sentiment of this text", "classification"),
            ("hello there", "general"),
            ("hi", "general"),
            ("olá", "general"),
            ("oi", "general"),
        ],
    )
    def test_intent_classification(self, prompt: str, expected: str) -> None:
        result = classify_ml(prompt)
        assert result is not None, f"ML router returned None (below threshold) for {prompt!r}"
        assert result.intent == expected, (
            f"Expected {expected!r}, got {result.intent!r} (confidence={result.confidence:.2f})"
        )

    @pytest.mark.parametrize(
        "prompt",
        [
            "What are the latest news about OpenAI?",
            "recent news on Python 3.13",
            "current news about artificial intelligence",
            "últimas notícias sobre inteligência artificial",
            "notícias recentes sobre Python",
        ],
    )
    def test_temporal_news_routes_to_function_calling(self, prompt: str) -> None:
        result = classify_ml(prompt)
        assert result is not None, f"Below threshold for {prompt!r}"
        assert result.intent == "function_calling", (
            f"Temporal query {prompt!r} routed to {result.intent!r}, expected 'function_calling'"
        )

    def test_empty_input_returns_unclassified(self) -> None:
        result = classify_ml("")
        assert result is not None
        assert result.intent == "unclassified"
        assert result.confidence == 1.0

    def test_whitespace_input_returns_unclassified(self) -> None:
        result = classify_ml("   ")
        assert result is not None
        assert result.intent == "unclassified"

    @pytest.mark.parametrize(
        "prompt",
        ["summarize this article", "what is machine learning", "calculate 3 plus 5"],
    )
    def test_confidence_above_threshold(self, prompt: str) -> None:
        result = classify_ml(prompt)
        assert result is not None
        assert result.confidence >= _FAST_ROUTE_THRESHOLD, (
            f"Confidence {result.confidence:.2f} below threshold {_FAST_ROUTE_THRESHOLD} for {prompt!r}"
        )

    def test_image_reference_routes_to_image_understanding(self) -> None:
        result = classify_ml("what is in this image @photo.png?")
        assert result is not None
        assert result.intent == "image_understanding"
        assert result.confidence == 1.0

    @pytest.mark.parametrize("lang,prompt,expected", [
        ("en", "summarize this text", "summarization"),
        ("pt", "resuma este texto", "summarization"),
        ("en", "what is Python", "question_answering"),
        ("pt", "o que é Python", "question_answering"),
    ])
    def test_bilingual_parity(self, lang: str, prompt: str, expected: str) -> None:
        result = classify_ml(prompt)
        assert result is not None
        assert result.intent == expected, f"[{lang}] {prompt!r}: expected {expected!r}, got {result.intent!r}"
