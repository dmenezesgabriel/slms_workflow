from __future__ import annotations

from unittest.mock import MagicMock

from src import trace
from src.graph.trace_types import ExecutionTrace


class TestToolCallRecording:
    def test_tool_call_records_to_exec_trace(self) -> None:
        trace.init()
        exec_trace = ExecutionTrace(run_id="test-recording")
        trace.set_exec_trace(exec_trace)

        trace.tool_call("web_search", {"query": "hello"})
        trace.tool_result("web_search", True, "search results here")

        assert len(exec_trace.tool_calls) == 1
        call = exec_trace.tool_calls[0]
        assert call.tool_name == "web_search"
        assert call.arguments == {"query": "hello"}
        assert call.success is True
        assert call.result_summary == "search results here"
        assert call.elapsed_ms >= 0

        trace.set_exec_trace(None)

    def test_multiple_tool_calls_recorded(self) -> None:
        trace.init()
        exec_trace = ExecutionTrace(run_id="test-multi")
        trace.set_exec_trace(exec_trace)

        trace.tool_call("web_search", {"query": "first"})
        trace.tool_result("web_search", True, "first result")
        trace.tool_call("calculator", {"expression": "1+1"})
        trace.tool_result("calculator", True, "2")

        assert len(exec_trace.tool_calls) == 2
        assert exec_trace.tool_calls[0].tool_name == "web_search"
        assert exec_trace.tool_calls[1].tool_name == "calculator"

        trace.set_exec_trace(None)

    def test_tool_call_skips_when_no_exec_trace(self) -> None:
        trace.init()
        trace.set_exec_trace(None)

        trace.tool_call("web_search", {"query": "hello"})
        trace.tool_result("web_search", True, "ok")

    def test_tool_result_graceful_without_preceding_call(self) -> None:
        trace.init()
        exec_trace = ExecutionTrace(run_id="test-orphan")
        trace.set_exec_trace(exec_trace)

        trace.tool_result("unknown_tool", True, "result")
        assert len(exec_trace.tool_calls) == 1
        assert exec_trace.tool_calls[0].tool_name == "unknown_tool"
        assert exec_trace.tool_calls[0].arguments == {}
        assert exec_trace.tool_calls[0].elapsed_ms == 0.0

        trace.set_exec_trace(None)


class TestSubscriberLifecycle:
    def test_unsubscribe_removes_callback(self) -> None:
        trace.init()
        calls: list[str] = []

        def cb(event: str, fields: dict) -> None:
            calls.append(event)

        trace.subscribe(cb)
        trace._emit("test.event")
        assert len(calls) == 1

        trace.unsubscribe(cb)
        trace._emit("test.event")
        assert len(calls) == 1

    def test_unsubscribe_twice_is_safe(self) -> None:
        trace.init()

        def cb(event: str, fields: dict) -> None:
            pass

        trace.subscribe(cb)
        trace.unsubscribe(cb)
        trace.unsubscribe(cb)


class TestStatusCollectorUnsubscribe:
    def test_unsubscribe_detaches_from_module(self) -> None:
        from src.ui import StatusCollector

        trace.init()
        collector = StatusCollector(MagicMock())
        collector.subscribe()
        assert len(trace._subscribers) == 1

        collector.unsubscribe()
        assert len(trace._subscribers) == 0


class TestExecTraceCleanup:
    def test_set_exec_trace_on_init_clears_state(self) -> None:
        trace.init()
        exec_trace = ExecutionTrace(run_id="test-cleanup")
        trace.set_exec_trace(exec_trace)
        trace.tool_call("web_search", {"q": "test"})

        trace.init()
        assert trace._current_exec_trace is None
        assert len(trace._tool_call_data) == 0
