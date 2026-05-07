"""Unit tests for the summarization handler, focusing on the content guard."""

from __future__ import annotations

import pytest

from app.handlers.summarization import _MIN_CONTENT_WORDS, _TRIGGER_PREFIX, handle
from app.schemas import FinalAnswer, SummaryResult


class _NeverCallLLM:
    """Fails immediately if the LLM is called — used to assert the guard fires."""

    def structured(self, *args: object, **kwargs: object) -> object:
        raise AssertionError("LLM must NOT be called for degenerate input")


class _AlwaysOkLLM:
    """Returns a minimal SummaryResult — used to assert the LLM is reached."""

    def structured(self, *args: object, **kwargs: object) -> SummaryResult:
        return SummaryResult(title="Test", summary="A summary.", key_points=["point"])


class TestContentGuard:
    @pytest.mark.parametrize(
        "prompt",
        [
            "summarize this text for me",
            "summarize",
            "tl;dr",
            "give me a summary",
            "summary",
            "resuma",
        ],
    )
    def test_degenerate_input_bypasses_llm(self, prompt: str) -> None:
        result = handle(prompt, _NeverCallLLM())  # type: ignore[arg-type]
        assert isinstance(result, FinalAnswer), (
            f"Expected FinalAnswer for degenerate input {prompt!r}, got {type(result).__name__}"
        )
        assert result.answer == "No text provided to summarize."

    @pytest.mark.parametrize(
        "prompt",
        [
            "summarize this: " + "important content word " * 10,
            "tl;dr: " + "some extended content to summarize " * 5,
        ],
    )
    def test_sufficient_content_reaches_llm(self, prompt: str) -> None:
        result = handle(prompt, _AlwaysOkLLM())  # type: ignore[arg-type]
        assert isinstance(result, SummaryResult), (
            f"Expected SummaryResult for legitimate input, got {type(result).__name__}"
        )

    def test_min_content_words_threshold(self) -> None:
        assert _MIN_CONTENT_WORDS == 10, (
            "Guard threshold changed — update dataset and smoke tests if intentional"
        )

    def test_exactly_at_threshold_is_blocked(self) -> None:
        # 9 content words after stripping "summarize" → should be blocked
        nine_words = "summarize " + " ".join(["word"] * 9)
        result = handle(nine_words, _NeverCallLLM())  # type: ignore[arg-type]
        assert isinstance(result, FinalAnswer)

    def test_one_above_threshold_passes(self) -> None:
        # 10 content words → should pass
        ten_words = "summarize " + " ".join(["word"] * 10)
        result = handle(ten_words, _AlwaysOkLLM())  # type: ignore[arg-type]
        assert isinstance(result, SummaryResult)


class TestTriggerPrefixStripping:
    @pytest.mark.parametrize(
        "prompt,expected_stripped",
        [
            ("summarize: the article", "the article"),
            ("summary: here is text", "here is text"),
            ("tl;dr: content here", "content here"),
            ("resuma: texto aqui", "texto aqui"),
            ("resumo: este texto", "este texto"),
        ],
    )
    def test_prefix_stripped_correctly(self, prompt: str, expected_stripped: str) -> None:
        stripped = _TRIGGER_PREFIX.sub("", prompt).strip()
        assert stripped == expected_stripped, (
            f"After stripping {prompt!r}: expected {expected_stripped!r}, got {stripped!r}"
        )
