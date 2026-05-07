"""Unit tests for the question-answering handler — regex patterns and retrieval logic."""

from __future__ import annotations

import pytest

from app.handlers.question_answering import (
    _PROPER_NOUN_RE,
    _RETRIEVAL_SIGNALS,
    _WHAT_IS_RE,
    _needs_retrieval,
)


class TestWhatIsPattern:
    @pytest.mark.parametrize(
        "phrase",
        ["What is", "What are", "What's", "o que é", "o que são"],
    )
    def test_matches_question_words(self, phrase: str) -> None:
        assert _WHAT_IS_RE.search(f"{phrase} something"), (
            f"_WHAT_IS_RE did not match phrase: {phrase!r}"
        )

    def test_does_not_match_mid_sentence(self) -> None:
        # Should only match at word boundaries, not inside words
        result = _WHAT_IS_RE.search("explain what matters most")
        assert result is None

    def test_case_insensitive(self) -> None:
        assert _WHAT_IS_RE.search("WHAT IS Python")
        assert _WHAT_IS_RE.search("what IS Python")


class TestProperNounExtraction:
    """Verifies that proper nouns are extracted from AFTER the 'what is' match."""

    @pytest.mark.parametrize(
        "prompt,expected_entity",
        [
            ("What is spaCy?", "spaCy"),
            ("What is FastAPI?", "FastAPI"),
            ("What is LangChain?", "LangChain"),
            ("What is Docker?", "Docker"),
            ("o que é LangChain?", "LangChain"),
            ("What is GitHub?", "GitHub"),
            ("What is OpenAI?", "OpenAI"),
        ],
    )
    def test_entity_extracted_after_what_is(self, prompt: str, expected_entity: str) -> None:
        wi = _WHAT_IS_RE.search(prompt)
        assert wi is not None, f"_WHAT_IS_RE did not match {prompt!r}"
        m = _PROPER_NOUN_RE.search(prompt, wi.end())
        assert m is not None, f"No proper noun found after 'what is' in {prompt!r}"
        assert m.group(1) == expected_entity, (
            f"Expected {expected_entity!r}, got {m.group(1)!r}"
        )

    @pytest.mark.parametrize(
        "prompt",
        [
            "how does Python work?",
            "explain machine learning to me",
        ],
    )
    def test_no_extraction_without_what_is(self, prompt: str) -> None:
        wi = _WHAT_IS_RE.search(prompt)
        assert wi is None, f"_WHAT_IS_RE unexpectedly matched {prompt!r}"

    def test_question_word_not_extracted_as_entity(self) -> None:
        wi = _WHAT_IS_RE.search("What is spaCy?")
        assert wi is not None
        m = _PROPER_NOUN_RE.search("What is spaCy?", wi.end())
        assert m is not None
        assert m.group(1) != "What", "Question word 'What' should not be extracted as entity"

    @pytest.mark.parametrize(
        "text,has_match",
        [
            ("spaCy", True),          # camelCase
            ("FastAPI", True),         # PascalCase compound
            ("LangChain", True),       # PascalCase compound
            ("Docker", True),          # Title-case
            ("OpenAI", True),          # Multi-uppercase
            ("python", False),         # all lowercase
        ],
    )
    def test_proper_noun_pattern_coverage(self, text: str, has_match: bool) -> None:
        m = _PROPER_NOUN_RE.search(text)
        assert bool(m) == has_match, (
            f"_PROPER_NOUN_RE match={bool(m)} for {text!r}, expected {has_match}"
        )


class TestNeedsRetrieval:
    @pytest.mark.parametrize(
        "prompt",
        [
            "What are the latest news about OpenAI?",
            "current Python version",
            "today's weather forecast",
            "fetch https://example.com",
            "what is the current stock price",
        ],
    )
    def test_retrieval_triggered_for_temporal_or_url(self, prompt: str) -> None:
        assert _needs_retrieval(prompt), f"Expected retrieval for {prompt!r}"

    @pytest.mark.parametrize(
        "prompt",
        [
            "what is Python",
            "explain machine learning",
            "hello there",
            "what is the capital of France",
        ],
    )
    def test_retrieval_not_triggered_for_static_queries(self, prompt: str) -> None:
        assert not _needs_retrieval(prompt), f"Unexpected retrieval for {prompt!r}"

    def test_url_triggers_retrieval(self) -> None:
        assert _needs_retrieval("go to https://example.com and tell me what you find")

    def test_retrieval_signals_pattern_is_narrow(self) -> None:
        # Verify the pattern doesn't over-fire on common words
        assert not _RETRIEVAL_SIGNALS.search("what is this about")
        assert not _RETRIEVAL_SIGNALS.search("tell me about Python")
