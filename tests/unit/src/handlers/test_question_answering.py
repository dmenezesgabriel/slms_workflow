from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.handlers import question_answering
from src.schemas import FinalAnswer


WHAT_IS_PROMPT = "What is spaCy?"
PROPER_NOUN = "spaCy"
PROPER_NOUN_GROUP = 1
TEMPORAL_PROMPT = "what is happening now in AI?"
STATIC_PROMPT = "what is Python"
URL_PROMPT = "fetch https://example.com"
RETRIEVAL_SIGNAL_PROMPT = "current Python version"
ANSWER = FinalAnswer(answer="answer")
CONTEXT = "retrieved context"
NO_CONTEXT = ""
LLM_REQUEST = object()


class TestWhatIsPattern:
    @pytest.mark.parametrize(
        "phrase",
        ["What is", "What are", "What's", "o que é", "o que são"],
    )
    def test_matches_supported_question_phrase(self, phrase: str) -> None:
        text = f"{phrase} something"

        result = question_answering._WHAT_IS_RE.search(text)

        assert result is not None

    def test_does_not_match_non_question_phrase(self) -> None:
        text = "explain what matters most"

        result = question_answering._WHAT_IS_RE.search(text)

        assert result is None

    def test_matches_without_case_sensitivity(self) -> None:
        text = "WHAT IS Python"

        result = question_answering._WHAT_IS_RE.search(text)

        assert result is not None


class TestProperNounPattern:
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
    def test_matches_entity_after_question_phrase(
        self, prompt: str, expected_entity: str
    ) -> None:
        question_match = question_answering._WHAT_IS_RE.search(prompt)

        assert question_match is not None

        result = question_answering._PROPER_NOUN_RE.search(prompt, question_match.end())

        assert result is not None
        assert result.group(PROPER_NOUN_GROUP) == expected_entity

    def test_does_not_return_question_word_as_entity(self) -> None:
        question_match = question_answering._WHAT_IS_RE.search(WHAT_IS_PROMPT)

        assert question_match is not None

        result = question_answering._PROPER_NOUN_RE.search(WHAT_IS_PROMPT, question_match.end())

        assert result is not None
        assert result.group(PROPER_NOUN_GROUP) == PROPER_NOUN

    @pytest.mark.parametrize(
        "text,expected_match",
        [
            ("spaCy", True),
            ("FastAPI", True),
            ("LangChain", True),
            ("Docker", True),
            ("OpenAI", True),
            ("python", False),
        ],
    )
    def test_matches_only_supported_proper_noun_shapes(
        self, text: str, expected_match: bool
    ) -> None:
        result = question_answering._PROPER_NOUN_RE.search(text)

        assert bool(result) is expected_match


class TestNeedsRetrieval:
    def test_returns_true_when_prompt_contains_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        is_temporal = MagicMock(return_value=False)
        monkeypatch.setattr("src.ner.is_temporal", is_temporal)

        result = question_answering._needs_retrieval(URL_PROMPT)

        assert result is True
        assert is_temporal.call_count == 0

    def test_returns_true_when_prompt_contains_retrieval_signal(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        is_temporal = MagicMock(return_value=False)
        monkeypatch.setattr("src.ner.is_temporal", is_temporal)

        result = question_answering._needs_retrieval(RETRIEVAL_SIGNAL_PROMPT)

        assert result is True
        assert is_temporal.call_count == 0

    def test_returns_true_when_temporal_detector_matches(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        is_temporal = MagicMock(return_value=True)
        monkeypatch.setattr("src.ner.is_temporal", is_temporal)

        result = question_answering._needs_retrieval(TEMPORAL_PROMPT)

        assert result is True
        assert is_temporal.call_count == 1
        is_temporal.assert_called_once_with(TEMPORAL_PROMPT)

    def test_returns_false_when_no_retrieval_path_matches(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        is_temporal = MagicMock(return_value=False)
        monkeypatch.setattr("src.ner.is_temporal", is_temporal)

        result = question_answering._needs_retrieval(STATIC_PROMPT)

        assert result is False
        assert is_temporal.call_count == 1
        is_temporal.assert_called_once_with(STATIC_PROMPT)


class TestHandle:
    def test_sends_retrieved_context_to_llm_when_context_exists(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        llm = MagicMock()
        llm.structured.return_value = ANSWER
        fetch_context = MagicMock(return_value=CONTEXT)
        llm_request_class = MagicMock(return_value=LLM_REQUEST)
        monkeypatch.setattr(question_answering, "_fetch_context", fetch_context)
        monkeypatch.setattr(question_answering, "LLMRequest", llm_request_class)

        result = question_answering.handle(STATIC_PROMPT, llm)

        assert result == ANSWER
        assert fetch_context.call_count == 1
        fetch_context.assert_called_once_with(STATIC_PROMPT)
        assert llm_request_class.call_count == 1
        assert llm.structured.call_count == 1
        llm.structured.assert_called_once_with(LLM_REQUEST, FinalAnswer)
        assert f"Context:\n{CONTEXT}" in llm_request_class.call_args.kwargs["user"]
        assert f"Question: {STATIC_PROMPT}" in llm_request_class.call_args.kwargs["user"]

    def test_sends_prompt_to_llm_when_context_does_not_exist(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        llm = MagicMock()
        llm.structured.return_value = ANSWER
        fetch_context = MagicMock(return_value=NO_CONTEXT)
        llm_request_class = MagicMock(return_value=LLM_REQUEST)
        monkeypatch.setattr(question_answering, "_fetch_context", fetch_context)
        monkeypatch.setattr(question_answering, "LLMRequest", llm_request_class)

        result = question_answering.handle(STATIC_PROMPT, llm)

        assert result == ANSWER
        assert fetch_context.call_count == 1
        fetch_context.assert_called_once_with(STATIC_PROMPT)
        assert llm_request_class.call_count == 1
        assert llm_request_class.call_args.kwargs["user"] == STATIC_PROMPT
        assert llm.structured.call_count == 1
        llm.structured.assert_called_once_with(LLM_REQUEST, FinalAnswer)
