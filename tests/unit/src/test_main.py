from __future__ import annotations

import sys

from pydantic import BaseModel

import src.main as main_module


class _Result(BaseModel):
    answer: str


class _StubOrchestrator:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object, str | None]] = []

    def run(self, user_input: str, llm: object, conversation_context: str | None = None) -> _Result:
        self.calls.append((user_input, llm, conversation_context))
        return _Result(answer="ok")


class _StubUI:
    def help(self, commands: object) -> None:
        return None

    def workflows(self, workflows: object) -> None:
        return None

    def error(self, message: str) -> None:
        raise AssertionError(message)

    def info(self, message: str) -> None:
        return None

    def header(self, value: str) -> None:
        return None

    def user_message(self, value: str) -> None:
        return None

    def run_with_status(self, status: str, execute: object) -> object:
        return execute()


def test_conversation_context_ignores_standalone_that_question() -> None:
    turns = [("Tell me about OpenAI", "OpenAI is an AI company.")]

    context = main_module._conversation_context(
        "what is that movie that says the meaning of life is 42?",
        turns,
    )

    assert context is None


def test_conversation_context_keeps_short_pronoun_follow_up() -> None:
    turns = [("Tell me about OpenAI", "OpenAI is an AI company.")]

    context = main_module._conversation_context("what about its history?", turns)

    assert context is not None
    assert "OpenAI" in context


def test_run_builds_default_llm_client_from_bootstrap(monkeypatch) -> None:
    orchestrator = _StubOrchestrator()
    default_llm = object()

    monkeypatch.setattr(main_module, "_get_orchestrator", lambda: orchestrator)
    monkeypatch.setattr(main_module, "build_llm_client", lambda: default_llm)

    result = main_module.run("hello")

    assert result.answer == "ok"
    assert orchestrator.calls == [("hello", default_llm, None)]


def test_main_uses_bootstrap_llm_factory_for_cli_prompt(monkeypatch, capsys) -> None:
    dispatch_calls: list[tuple[str, object]] = []
    default_llm = object()

    monkeypatch.setattr(main_module, "AssistantUI", lambda: _StubUI())
    monkeypatch.setattr(main_module, "_ensure_requested_models", lambda args: None)
    monkeypatch.setattr(main_module, "apply_model_overrides", lambda **kwargs: {"router": object()})
    monkeypatch.setattr(main_module, "build_tool_registry", lambda: object())
    monkeypatch.setattr(main_module, "build_node_registry", lambda **kwargs: object())
    monkeypatch.setattr(main_module, "set_node_registry", lambda registry: None)
    monkeypatch.setattr(main_module, "Router", lambda profile: object())
    monkeypatch.setattr(main_module, "Orchestrator", lambda **kwargs: object())
    monkeypatch.setattr(main_module, "build_llm_client", lambda: default_llm)
    monkeypatch.setattr(main_module, "_print_result", lambda result, as_json, ui=None: "printed")

    def dispatch(prompt: str, llm: object) -> _Result:
        dispatch_calls.append((prompt, llm))
        return _Result(answer="ok")

    monkeypatch.setattr(main_module, "_select_dispatch", lambda args, orchestrator: dispatch)
    monkeypatch.setattr(sys, "argv", ["src.main", "--prompt", "hello"])

    main_module.main()

    assert dispatch_calls == [("hello", default_llm)]
    assert capsys.readouterr().out == ""
