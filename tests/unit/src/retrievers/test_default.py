from __future__ import annotations

import pytest

from src.techniques.retrieval import plan_retrieval


@pytest.mark.parametrize(
    ("prompt", "expected_strategy", "expected_query"),
    [
        ("read https://example.com", "url_fetch", "https://example.com"),
        ("latest news about OpenAI", "time_sensitive", "latest news about OpenAI"),
        (
            "which song says hello from the other side?",
            "reference_lookup",
            "which song says hello from the other side?",
        ),
        ("explain the SOLID principles", "concept_lookup", "explain the SOLID principles"),
        ("What is spaCy?", "direct_what_is", "spaCy"),
        ("what is spacy?", "direct_what_is", "spacy"),
    ],
)
def test_plan_retrieval_selects_expected_strategy(
    monkeypatch: pytest.MonkeyPatch, prompt: str, expected_strategy: str, expected_query: str
) -> None:
    monkeypatch.setattr("src.techniques.retrieval.ner.best_lookup_entity", lambda _text: None)
    monkeypatch.setattr("src.techniques.retrieval.ner.is_temporal", lambda _text: False)

    plan = plan_retrieval(prompt)

    assert plan.strategy == expected_strategy
    assert plan.query == expected_query
    assert plan.score > 0.0


def test_plan_retrieval_prefers_entity_lookup_for_named_entity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entity = type("Entity", (), {"text": "OpenAI", "label": "ORG"})()
    monkeypatch.setattr("src.techniques.retrieval.ner.best_lookup_entity", lambda _text: entity)
    monkeypatch.setattr("src.techniques.retrieval.ner.is_temporal", lambda _text: False)

    plan = plan_retrieval("tell me about OpenAI")

    assert plan.strategy == "entity_lookup"
    assert plan.query == "OpenAI"


def test_plan_retrieval_returns_none_for_non_retrieval_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.techniques.retrieval.ner.best_lookup_entity", lambda _text: None)
    monkeypatch.setattr("src.techniques.retrieval.ner.is_temporal", lambda _text: False)

    plan = plan_retrieval("hello there")

    assert plan.strategy == "none"
    assert plan.query is None
    assert plan.score == 0.0
