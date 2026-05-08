from __future__ import annotations

from src.main import _conversation_context


def test_conversation_context_ignores_standalone_that_question() -> None:
    turns = [("Tell me about OpenAI", "OpenAI is an AI company.")]

    context = _conversation_context(
        "what is that movie that says the meaning of life is 42?",
        turns,
    )

    assert context is None


def test_conversation_context_keeps_short_pronoun_follow_up() -> None:
    turns = [("Tell me about OpenAI", "OpenAI is an AI company.")]

    context = _conversation_context("what about its history?", turns)

    assert context is not None
    assert "OpenAI" in context
