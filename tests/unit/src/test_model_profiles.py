from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.bootstrap import build_node_registry
from src.lexical_scoring import LexicalMatch
from src.model_registry import MODEL_REGISTRY, ModelProfile, apply_model_overrides
from src.router import PrototypeClassification, Router
from src.schemas import FinalAnswer, IntentClassification, SummaryResult
from src.tools import ToolRegistry


def test_apply_model_overrides_returns_new_registry_without_mutating_global() -> None:
    original = MODEL_REGISTRY["general"]

    overridden = apply_model_overrides(default_model="custom-model")

    assert overridden["general"].model == "custom-model"
    assert MODEL_REGISTRY["general"] == original


def test_router_uses_injected_profile_for_llm_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    llm = MagicMock()
    llm.structured.return_value = IntentClassification(
        intent="general",
        confidence=0.9,
        reason="ok",
    )
    monkeypatch.setattr(
        "src.router._ml_router.classify_with_details",
        MagicMock(
            return_value=PrototypeClassification(
                intent="general",
                prototype="",
                match=LexicalMatch(
                    value="",
                    score=0.0,
                    token_overlap=0.0,
                    fuzzy=0.0,
                    char_ngram=0.0,
                ),
            )
        ),
    )

    profile = ModelProfile(model="router-model", system="router-system", max_tokens=77)
    Router(profile=profile).route("ambiguous prompt", llm)

    request = llm.structured.call_args.args[0]
    assert request.model == "router-model"
    assert request.system == "router-system"
    assert request.max_tokens == 77


def test_build_node_registry_injects_profiles_into_nodes() -> None:
    llm = MagicMock()
    llm.structured.return_value = SummaryResult(title="t", summary="s", key_points=[])
    retriever = MagicMock()
    retriever.fetch_context.return_value = ""
    profiles = apply_model_overrides(role_models={"summarization": "summary-model"})

    registry = build_node_registry(
        tool_registry=ToolRegistry([]),
        retriever=retriever,
        model_profiles=profiles,
    )

    node = registry.get("summarization")
    assert node is not None
    node.execute("summarize " + "word " * 12, llm)

    request = llm.structured.call_args.args[0]
    assert request.model == "summary-model"


def test_build_node_registry_persists_qa_retrieval_results_explicitly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    llm = MagicMock()
    llm.structured.return_value = FinalAnswer(answer="a")
    retriever = MagicMock()
    retriever.fetch_context.return_value = "retrieved context"
    rag_store = MagicMock()

    monkeypatch.setattr("src.bootstrap.HybridRAG", MagicMock(return_value=rag_store))

    registry = build_node_registry(
        tool_registry=ToolRegistry([]),
        retriever=retriever,
    )

    qa_node = registry.get("question_answering")
    assert qa_node is not None
    result = qa_node.execute("what is Python", llm)

    assert result == FinalAnswer(answer="a")
    rag_store.add_text.assert_called_once_with(
        contents=["retrieved context"],
        sources=["retrieval_cache"],
    )
