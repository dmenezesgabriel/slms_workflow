from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src import router
from src.schemas import IntentClassification

FAST_ROUTE_CONFIDENCE = router._FAST_ROUTE_THRESHOLD
BELOW_FAST_ROUTE_CONFIDENCE = router._FAST_ROUTE_THRESHOLD / 2
ABOVE_LLM_FALLBACK_CONFIDENCE = (router._LLM_FALLBACK_THRESHOLD + 1.0) / 2
BELOW_LLM_FALLBACK_CONFIDENCE = router._LLM_FALLBACK_THRESHOLD / 2
PERFECT_CONFIDENCE = 1.0
FAST_ROUTE_PROMPT = "summarize this text"
LLM_ROUTE_PROMPT = "ambiguous prompt"
IMAGE_PROMPT = "what is in this image @photo.png?"
EMPTY_PROMPT = ""
WHITESPACE_PROMPT = "   "
LLM_REQUEST = object()


class TestClassifyMlShortCircuit:
    def test_returns_unclassified_when_input_is_empty(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        classify = MagicMock()
        monkeypatch.setattr(router._ml_router, "classify", classify)

        result = router.classify_ml(EMPTY_PROMPT)

        assert result is not None
        assert result.intent == "unclassified"
        assert result.confidence == PERFECT_CONFIDENCE
        assert classify.call_count == 0

    def test_returns_unclassified_when_input_is_whitespace(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        classify = MagicMock()
        monkeypatch.setattr(router._ml_router, "classify", classify)

        result = router.classify_ml(WHITESPACE_PROMPT)

        assert result is not None
        assert result.intent == "unclassified"
        assert result.confidence == PERFECT_CONFIDENCE
        assert classify.call_count == 0

    def test_returns_image_understanding_when_input_references_image(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        classify = MagicMock()
        monkeypatch.setattr(router._ml_router, "classify", classify)

        result = router.classify_ml(IMAGE_PROMPT)

        assert result is not None
        assert result.intent == "image_understanding"
        assert result.confidence == PERFECT_CONFIDENCE
        assert classify.call_count == 0


class TestClassifyMlFastRoute:
    def test_returns_intent_when_confidence_meets_threshold(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        classify = MagicMock(return_value=("summarization", FAST_ROUTE_CONFIDENCE))
        monkeypatch.setattr(router._ml_router, "classify", classify)

        result = router.classify_ml(FAST_ROUTE_PROMPT)

        assert result is not None
        assert result.intent == "summarization"
        assert result.confidence == FAST_ROUTE_CONFIDENCE
        assert classify.call_count == 1
        classify.assert_called_once_with(FAST_ROUTE_PROMPT)

    def test_returns_none_when_confidence_is_below_threshold(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        classify = MagicMock(return_value=("summarization", BELOW_FAST_ROUTE_CONFIDENCE))
        monkeypatch.setattr(router._ml_router, "classify", classify)

        result = router.classify_ml(FAST_ROUTE_PROMPT)

        assert result is None
        assert classify.call_count == 1
        classify.assert_called_once_with(FAST_ROUTE_PROMPT)


class TestRouteTaskShortCircuit:
    def test_returns_unclassified_when_input_is_empty(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        llm = MagicMock()
        classify = MagicMock()
        monkeypatch.setattr(router._ml_router, "classify", classify)

        result = router.route_task(EMPTY_PROMPT, llm)

        assert result.intent == "unclassified"
        assert result.confidence == PERFECT_CONFIDENCE
        assert classify.call_count == 0
        assert llm.structured.call_count == 0

    def test_returns_image_understanding_when_input_references_image(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        llm = MagicMock()
        classify = MagicMock()
        monkeypatch.setattr(router._ml_router, "classify", classify)

        result = router.route_task(IMAGE_PROMPT, llm)

        assert result.intent == "image_understanding"
        assert result.confidence == PERFECT_CONFIDENCE
        assert classify.call_count == 0
        assert llm.structured.call_count == 0


class TestRouteTaskFastPath:
    def test_returns_ml_result_when_confidence_meets_threshold(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        llm = MagicMock()
        classify = MagicMock(return_value=("summarization", FAST_ROUTE_CONFIDENCE))
        trace_route = MagicMock()
        monkeypatch.setattr(router._ml_router, "classify", classify)
        monkeypatch.setattr("src.router.trace.route", trace_route)

        result = router.route_task(FAST_ROUTE_PROMPT, llm)

        assert result.intent == "summarization"
        assert result.confidence == FAST_ROUTE_CONFIDENCE
        assert classify.call_count == 1
        classify.assert_called_once_with(FAST_ROUTE_PROMPT)
        assert llm.structured.call_count == 0
        assert trace_route.call_count == 1
        trace_route.assert_called_once_with(result.intent, result.confidence, "ml")


class TestRouteTaskLlmFallback:
    def test_instantiates_request_and_returns_llm_result_when_confidence_is_accepted(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        expected = IntentClassification(
            intent="question_answering",
            confidence=ABOVE_LLM_FALLBACK_CONFIDENCE,
            reason="LLM selected intent.",
        )
        llm = MagicMock()
        llm.structured.return_value = expected
        classify = MagicMock(return_value=("general", BELOW_FAST_ROUTE_CONFIDENCE))
        trace_route = MagicMock()
        llm_request_class = MagicMock(return_value=LLM_REQUEST)
        monkeypatch.setattr(router._ml_router, "classify", classify)
        monkeypatch.setattr("src.router.trace.route", trace_route)
        monkeypatch.setattr(router, "LLMRequest", llm_request_class)

        result = router.route_task(LLM_ROUTE_PROMPT, llm)

        assert result == expected
        assert classify.call_count == 1
        classify.assert_called_once_with(LLM_ROUTE_PROMPT)
        assert llm_request_class.call_count == 1
        assert LLM_ROUTE_PROMPT in llm_request_class.call_args.kwargs["user"]
        assert llm.structured.call_count == 1
        llm.structured.assert_called_once_with(LLM_REQUEST, IntentClassification)
        assert trace_route.call_count == 1
        trace_route.assert_called_once_with(result.intent, result.confidence, "llm")

    def test_returns_general_when_llm_confidence_is_below_threshold(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        llm_result = IntentClassification(
            intent="question_answering",
            confidence=BELOW_LLM_FALLBACK_CONFIDENCE,
            reason="Low confidence.",
        )
        llm = MagicMock()
        llm.structured.return_value = llm_result
        classify = MagicMock(return_value=("general", BELOW_FAST_ROUTE_CONFIDENCE))
        trace_route = MagicMock()
        llm_request_class = MagicMock(return_value=LLM_REQUEST)
        monkeypatch.setattr(router._ml_router, "classify", classify)
        monkeypatch.setattr("src.router.trace.route", trace_route)
        monkeypatch.setattr(router, "LLMRequest", llm_request_class)

        result = router.route_task(LLM_ROUTE_PROMPT, llm)

        assert result.intent == "general"
        assert result.confidence == BELOW_LLM_FALLBACK_CONFIDENCE
        assert classify.call_count == 1
        classify.assert_called_once_with(LLM_ROUTE_PROMPT)
        assert llm_request_class.call_count == 1
        assert llm.structured.call_count == 1
        llm.structured.assert_called_once_with(LLM_REQUEST, IntentClassification)
        assert trace_route.call_count == 1
        trace_route.assert_called_once_with(result.intent, result.confidence, "llm-lowconf")
