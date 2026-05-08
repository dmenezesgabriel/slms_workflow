from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.handlers import summarization
from src.schemas import FinalAnswer, SummaryResult

NO_TEXT_ANSWER = "No text provided to summarize."
TOKEN = "word"
BELOW_MIN_CONTENT_WORD_COUNT = summarization._MIN_CONTENT_WORDS - 1
MIN_CONTENT_WORD_COUNT = summarization._MIN_CONTENT_WORDS
SUMMARY_RESULT = SummaryResult(title="Test", summary="A summary.", key_points=["point"])
LLM_REQUEST = object()


def content_with_word_count(word_count: int) -> str:
    return " ".join([TOKEN] * word_count)


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
    def test_returns_final_answer_when_prompt_has_insufficient_content(self, prompt: str) -> None:
        llm = MagicMock()

        result = summarization.handle(prompt, llm)

        assert result == FinalAnswer(answer=NO_TEXT_ANSWER)
        assert llm.structured.call_count == 0

    def test_returns_final_answer_when_content_word_count_is_below_minimum(self) -> None:
        prompt = f"summarize {content_with_word_count(BELOW_MIN_CONTENT_WORD_COUNT)}"
        llm = MagicMock()

        result = summarization.handle(prompt, llm)

        assert result == FinalAnswer(answer=NO_TEXT_ANSWER)
        assert llm.structured.call_count == 0

    def test_calls_llm_when_content_word_count_meets_minimum(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        prompt = f"summarize {content_with_word_count(MIN_CONTENT_WORD_COUNT)}"
        llm = MagicMock()
        llm.structured.return_value = SUMMARY_RESULT
        llm_request_class = MagicMock(return_value=LLM_REQUEST)
        monkeypatch.setattr(summarization, "LLMRequest", llm_request_class)

        result = summarization.handle(prompt, llm)

        assert result == SUMMARY_RESULT
        assert llm_request_class.call_count == 1
        assert llm_request_class.call_args.kwargs["user"] == (
            f"Summarize this text:\n\n{content_with_word_count(MIN_CONTENT_WORD_COUNT)}"
        )
        assert llm.structured.call_count == 1
        llm.structured.assert_called_once_with(LLM_REQUEST, SummaryResult)


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
    def test_removes_supported_trigger_prefix(self, prompt: str, expected_stripped: str) -> None:
        result = summarization._TRIGGER_PREFIX.sub("", prompt).strip()

        assert result == expected_stripped
