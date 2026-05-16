from __future__ import annotations

import io

from rich.console import Console

from src.ui import StatusCollector, _sanitize_args


def test_sanitize_args_empty() -> None:
    assert _sanitize_args("web_search", {}) == ""


def test_sanitize_args_single_query() -> None:
    result = _sanitize_args("web_search", {"query": "llama.cpp"})
    assert result == "(llama.cpp)"


def test_sanitize_args_truncates_long_query() -> None:
    result = _sanitize_args("web_search", {"query": "x" * 100})
    assert len(result) < 70
    assert result.endswith("...)")


def test_sanitize_args_multiple_keys() -> None:
    result = _sanitize_args("fetch", {"url": "http://example.com", "method": "GET"})
    assert "url=" in result
    assert "method=" in result


def test_sanitize_args_truncates_long_value() -> None:
    result = _sanitize_args("fetch", {"data": "x" * 100})
    assert len(result) < 65
    assert "..." in result


class TestStatusCollector:
    def _make_collector(self) -> tuple[StatusCollector, io.StringIO]:
        buf = io.StringIO()
        console = Console(file=buf, force_terminal=False, no_color=True)
        collector = StatusCollector(console)
        return collector, buf

    def test_route_event_renders_concise(self) -> None:
        collector, buf = self._make_collector()
        collector._on_event(
            "route",
            {
                "intent": "question_answering",
                "confidence": 0.95,
                "reason": "ml",
                "run_id": "abc",
            },
        )
        output = buf.getvalue()
        assert "route →" in output
        assert "question_answering" in output

    def test_plan_event_renders_workflow(self) -> None:
        collector, buf = self._make_collector()
        collector._on_event(
            "plan",
            {
                "strategy": "dag",
                "name": "research_and_summarize",
                "reason": "multi-step",
                "run_id": "abc",
            },
        )
        output = buf.getvalue()
        assert "workflow →" in output
        assert "research_and_summarize" in output

    def test_plan_step_renders_workflow(self) -> None:
        collector, buf = self._make_collector()
        collector._on_event(
            "plan.step",
            {
                "strategy": "single",
                "detail": "question_answering",
                "run_id": "abc",
            },
        )
        output = buf.getvalue()
        assert "workflow →" in output
        assert "question_answering" in output

    def test_tool_call_renders_concise(self) -> None:
        collector, buf = self._make_collector()
        collector._on_event(
            "tool.call",
            {
                "tool": "web_search",
                "args": {"query": "llama.cpp"},
                "run_id": "abc",
            },
        )
        output = buf.getvalue()
        assert "calling tool:" in output
        assert "web_search" in output
        assert "llama.cpp" in output

    def test_tool_result_renders_status(self) -> None:
        collector, buf = self._make_collector()
        collector._on_event(
            "tool.result",
            {
                "tool": "web_search",
                "success": True,
                "result": "ok",
                "run_id": "abc",
            },
        )
        output = buf.getvalue()
        assert "tool returned (ok)" in output

    def test_tool_result_failed(self) -> None:
        collector, buf = self._make_collector()
        collector._on_event(
            "tool.result",
            {
                "tool": "web_search",
                "success": False,
                "result": "error",
                "run_id": "abc",
            },
        )
        output = buf.getvalue()
        assert "tool returned (failed)" in output

    def test_synthesis_span_renders(self) -> None:
        collector, buf = self._make_collector()
        collector._on_event(
            "span.enter", {"name": "question_answering", "depth": 2, "run_id": "abc"}
        )
        output = buf.getvalue()
        assert "synthesizing →" in output
        assert "question_answering" in output

    def test_non_handler_span_ignored(self) -> None:
        collector, buf = self._make_collector()
        collector._on_event("span.enter", {"name": "planning", "depth": 1, "run_id": "abc"})
        output = buf.getvalue()
        assert output == ""

    def test_tracks_run_id(self) -> None:
        collector, buf = self._make_collector()
        collector._on_event("route", {"intent": "test", "run_id": "my-run-456"})
        assert collector._run_id == "my-run-456"

    def test_trace_hint_no_file(self) -> None:
        collector, buf = self._make_collector()
        collector._run_id = "nonexistent"
        assert collector.trace_hint() == ""

    def test_subscribe_adds_listener(self) -> None:
        collector, buf = self._make_collector()
        collector.subscribe()
        assert collector._subscribed is True
        collector.subscribe()
        assert collector._subscribed is True

    def test_dag_exec_renders_node(self) -> None:
        collector, buf = self._make_collector()
        collector._on_event(
            "dag.exec", {"node": "search", "intent": "function_calling", "run_id": "abc"}
        )
        output = buf.getvalue()
        assert "node →" in output
        assert "search" in output
