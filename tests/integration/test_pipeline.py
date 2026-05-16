"""
Integration tests for the full pipeline — require a llama.cpp LLM server.

Run with:
    pytest tests/integration/ -m integration -v
"""

from __future__ import annotations

import pytest

from src.main import run
from src.text_utils import extract_text


@pytest.mark.integration
class TestFullPipeline:
    def test_math_calculation_end_to_end(self, llm_client: object) -> None:
        result = run("what is 15 + 7?", llm_client)  # type: ignore[arg-type]
        answer = extract_text(result)
        assert "22" in answer, f"Expected '22' in answer, got: {answer!r}"

    def test_greeting_returns_response(self, llm_client: object) -> None:
        result = run("hello there", llm_client)  # type: ignore[arg-type]
        answer = extract_text(result)
        assert len(answer.strip()) > 0, "Expected non-empty response to greeting"

    def test_simple_factual_question(self, llm_client: object) -> None:
        result = run("what is the capital of France?", llm_client)  # type: ignore[arg-type]
        answer = extract_text(result).lower()
        assert "paris" in answer, f"Expected 'Paris' in factual answer, got: {answer!r}"

    def test_summarization_with_content(self, llm_client: object) -> None:
        prompt = (
            "summarize this: Python is a high-level programming language known for its "
            "simplicity and readability. It was created by Guido van Rossum and released in 1991. "
            "Python supports multiple programming paradigms including procedural, object-oriented, "
            "and functional programming. It is widely used in data science, web development, "
            "automation, and artificial intelligence."
        )
        result = run(prompt, llm_client)  # type: ignore[arg-type]
        answer = extract_text(result)
        assert len(answer.strip()) > 20, f"Expected substantive summary, got: {answer!r}"

    def test_degenerate_summarization_handled(self, llm_client: object) -> None:
        result = run("summarize this text for me", llm_client)  # type: ignore[arg-type]
        answer = extract_text(result)
        assert "No text provided" in answer, f"Expected guard message, got: {answer!r}"


@pytest.mark.integration
class TestProtectedAndTargetImprovementPrompts:
    def test_portuguese_summarization_prompt_returns_non_empty_response(
        self, llm_client: object
    ) -> None:
        prompt = (
            "resuma este texto: Python é uma linguagem de programação criada por Guido van Rossum. "
            "Ela é usada em web, automação e ciência de dados."
        )
        result = run(prompt, llm_client)  # type: ignore[arg-type]
        answer = extract_text(result)
        assert len(answer.strip()) > 0

    def test_target_improvement_paraphrase_prompt_returns_non_empty_response(
        self, llm_client: object
    ) -> None:
        result = run("could you make this shorter?", llm_client)  # type: ignore[arg-type]
        answer = extract_text(result)
        assert len(answer.strip()) > 0

    def test_portuguese_paraphrase_prompt_returns_non_empty_response(
        self, llm_client: object
    ) -> None:
        result = run("pode resumir isso? Python é muito usado em automação.", llm_client)  # type: ignore[arg-type]
        answer = extract_text(result)
        assert len(answer.strip()) > 0


@pytest.mark.integration
class TestRouterWithLLMFallback:
    def test_low_confidence_falls_back_to_llm(self, llm_client: object) -> None:
        # This should fall below the TF-IDF threshold and use the LLM router
        result = run(
            "I was wondering if you might be able to assist me",
            llm_client,  # type: ignore[arg-type]
        )
        answer = extract_text(result)
        assert len(answer.strip()) > 0
