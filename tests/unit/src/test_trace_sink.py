from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from unittest.mock import MagicMock

from src.graph.trace_types import (
    ExecutionTrace,
    NodeTrace,
    ToolCallTrace,
    _redact_sensitive,
)
from src.trace_sink import (
    FileTraceSink,
    MetricsSummary,
    MultiSink,
    build_metrics_summary,
    build_trace_from_run,
    generate_run_id,
    write_metrics_artifact,
)


class TestExecutionTrace:
    def test_serializes_to_json(self) -> None:
        trace = ExecutionTrace(
            run_id="abc123",
            workflow_name="test",
            nodes={
                "a": NodeTrace(
                    node_id="a",
                    intent="general",
                    input_="hello",
                    output="hi",
                    elapsed_ms=10.0,
                ),
            },
            node_order=["a"],
            final_status="completed",
            elapsed_ms=100.0,
        )
        data = json.loads(trace.to_json())

        assert data["version"] == "1.0"
        assert data["run_id"] == "abc123"
        assert data["workflow_name"] == "test"
        assert data["nodes"]["a"]["input"] == "hello"
        assert data["nodes"]["a"]["output"] == "hi"
        assert data["nodes"]["a"]["elapsed_ms"] == 10.0
        assert data["final_status"] == "completed"

    def test_truncates_large_outputs(self) -> None:
        trace = ExecutionTrace(
            run_id="test",
            nodes={
                "a": NodeTrace(
                    node_id="a",
                    intent="general",
                    input_="x" * 600,
                    output="y" * 1200,
                    elapsed_ms=1.0,
                ),
            },
        )
        data = json.loads(trace.to_json())

        assert len(data["nodes"]["a"]["input"]) <= 503  # 500 + "..."
        assert data["nodes"]["a"]["input"].endswith("...")
        assert len(data["nodes"]["a"]["output"]) <= 1003  # 1000 + "..."
        assert data["nodes"]["a"]["output"].endswith("...")

    def test_redacts_sensitive_fields(self) -> None:
        raw = {"api_key": "sk-123456", "token": "abc", "data": "safe"}
        result = _redact_sensitive(raw)

        assert result["api_key"] == "***REDACTED***"
        assert result["token"] == "***REDACTED***"
        assert result["data"] == "safe"

    def test_add_tool_call(self) -> None:
        trace = ExecutionTrace(run_id="test")
        call = ToolCallTrace(
            tool_name="web_search",
            arguments={"query": "llama.cpp"},
            result_summary="search results",
            success=True,
            elapsed_ms=500.0,
        )
        trace.add_tool_call(call)

        assert len(trace.tool_calls) == 1
        assert trace.tool_calls[0].tool_name == "web_search"

    def test_tool_call_appears_in_json(self) -> None:
        trace = ExecutionTrace(run_id="test")
        trace.add_tool_call(
            ToolCallTrace(
                tool_name="web_search",
                arguments={"query": "test"},
                result_summary="ok",
                success=True,
                elapsed_ms=100.0,
            )
        )
        data = json.loads(trace.to_json())

        assert len(data["tool_calls"]) == 1
        assert data["tool_calls"][0]["tool_name"] == "web_search"

    def test_node_order_preserved(self) -> None:
        trace = ExecutionTrace(run_id="test")
        trace.node_order = ["first", "second", "third"]
        data = json.loads(trace.to_json())

        assert data["node_order"] == ["first", "second", "third"]


class TestFileTraceSink:
    def test_writes_json_artifact(self, tmp_path: Path) -> None:
        trace = ExecutionTrace(run_id="test-run-123")
        sink = FileTraceSink(artifacts_dir=tmp_path)

        sink.emit(trace)

        artifact = tmp_path / "trace_test-run-123.json"
        assert artifact.exists()
        data = json.loads(artifact.read_text(encoding="utf-8"))
        assert data["run_id"] == "test-run-123"
        assert data["version"] == "1.0"

    def test_creates_artifacts_directory(self, tmp_path: Path) -> None:
        new_dir = tmp_path / "new-traces"
        assert not new_dir.exists()

        FileTraceSink(artifacts_dir=new_dir)

        assert new_dir.exists()

    def test_does_not_crash_on_write_failure(self, tmp_path: Path) -> None:
        trace = ExecutionTrace(run_id="test")
        sink = FileTraceSink(artifacts_dir=tmp_path / "nonexistent" / "deep")

        sink.emit(trace)  # should not raise


class TestBuildTraceFromRun:
    def test_builds_full_trace(self) -> None:
        exec_trace = ExecutionTrace(
            workflow_name="test_wf",
            nodes={
                "n1": NodeTrace(
                    node_id="n1",
                    intent="general",
                    input_="in",
                    output="out",
                    elapsed_ms=5.0,
                ),
            },
            node_order=["n1"],
        )
        result = build_trace_from_run(
            run_id="run-1",
            workflow_name="test_wf",
            workflow_description="test workflow",
            route_strategy="composed",
            route_confidence=0.95,
            exec_trace=exec_trace,
            start_time=1000.0,
            end_time=2000.0,
            final_status="completed",
        )

        assert result.run_id == "run-1"
        assert result.workflow_name == "test_wf"
        assert result.route_strategy == "composed"
        assert result.elapsed_ms == 1000000.0  # 1000s * 1000
        assert result.nodes["n1"].intent == "general"
        assert result.node_order == ["n1"]

    def test_handles_none_exec_trace(self) -> None:
        result = build_trace_from_run(
            run_id="run-2",
            workflow_name="wf",
            workflow_description="",
            route_strategy="single",
            route_confidence=0.8,
            exec_trace=None,
            start_time=0.0,
            end_time=1.0,
        )

        assert result.nodes == {}
        assert result.node_order == []
        assert result.tool_calls == []


class TestGenerateRunId:
    def test_generates_unique_ids(self) -> None:
        ids = {generate_run_id() for _ in range(100)}
        assert len(ids) == 100

    def test_id_is_hex_string(self) -> None:
        rid = generate_run_id()
        assert len(rid) == 12
        int(rid, 16)  # should not raise


class TestMetricsSummary:
    def test_default_sink_failures_empty(self) -> None:
        m = MetricsSummary(
            run_id="r1",
            route_strategy="single",
            workflow_name="wf",
            tool_count=0,
            fallback_route=False,
            elapsed_ms=10.0,
            completion_status="completed",
            node_count=0,
        )
        assert m.sink_failures == []

    def test_serializes_to_dict(self) -> None:
        m = MetricsSummary(
            run_id="r1",
            route_strategy="composed",
            workflow_name="wf",
            tool_count=3,
            fallback_route=False,
            elapsed_ms=500.0,
            completion_status="completed",
            node_count=2,
            sink_failures=[{"sink": "FakeSink", "error": "boom"}],
        )
        d = asdict(m)
        assert d["run_id"] == "r1"
        assert d["tool_count"] == 3
        assert d["sink_failures"] == [{"sink": "FakeSink", "error": "boom"}]


class TestBuildMetricsSummary:
    def test_metrics_from_completed_trace(self) -> None:
        trace = ExecutionTrace(
            run_id="run-1",
            workflow_name="test-wf",
            route_strategy="single",
            final_status="completed",
            elapsed_ms=150.0,
            node_order=["a", "b"],
        )
        trace.add_tool_call(
            ToolCallTrace(
                tool_name="search",
                arguments={"q": "x"},
                result_summary="ok",
                success=True,
                elapsed_ms=50.0,
            )
        )
        trace.add_tool_call(
            ToolCallTrace(
                tool_name="fetch",
                arguments={"url": "y"},
                result_summary="ok",
                success=True,
                elapsed_ms=30.0,
            )
        )

        metrics = build_metrics_summary(trace)

        assert metrics.run_id == "run-1"
        assert metrics.workflow_name == "test-wf"
        assert metrics.route_strategy == "single"
        assert metrics.tool_count == 2
        assert metrics.node_count == 2
        assert metrics.fallback_route is False
        assert metrics.elapsed_ms == 150.0
        assert metrics.completion_status == "completed"

    def test_fallback_route_agent(self) -> None:
        trace = ExecutionTrace(
            run_id="run-2",
            route_strategy="agent",
            workflow_name="agent",
            final_status="completed",
            elapsed_ms=0.0,
            node_order=[],
        )
        metrics = build_metrics_summary(trace)
        assert metrics.fallback_route is True

    def test_fallback_route_non_agent(self) -> None:
        for strat in ("single", "composed", "direct"):
            trace = ExecutionTrace(
                run_id="x",
                route_strategy=strat,
                workflow_name="wf",
                final_status="completed",
                elapsed_ms=0.0,
                node_order=[],
            )
            assert build_metrics_summary(trace).fallback_route is False

    def test_zero_tool_and_node_counts_for_empty_trace(self) -> None:
        trace = ExecutionTrace(run_id="empty")
        metrics = build_metrics_summary(trace)
        assert metrics.tool_count == 0
        assert metrics.node_count == 0


class TestWriteMetricsArtifact:
    def test_writes_json_file(self, tmp_path: Path) -> None:
        metrics = MetricsSummary(
            run_id="m1",
            route_strategy="single",
            workflow_name="wf",
            tool_count=1,
            fallback_route=False,
            elapsed_ms=100.0,
            completion_status="completed",
            node_count=1,
        )
        path = write_metrics_artifact(metrics, tmp_path)
        assert path == tmp_path / "metrics_m1.json"
        assert path.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["run_id"] == "m1"
        assert data["route_strategy"] == "single"
        assert data["tool_count"] == 1
        assert data["elapsed_ms"] == 100.0

    def test_creates_directory(self, tmp_path: Path) -> None:
        deep = tmp_path / "a" / "b"
        metrics = MetricsSummary(
            run_id="m2",
            route_strategy="composed",
            workflow_name="wf",
            tool_count=0,
            fallback_route=False,
            elapsed_ms=0.0,
            completion_status="completed",
            node_count=0,
        )
        path = write_metrics_artifact(metrics, deep)
        assert path.exists()


class TestMultiSink:
    def test_emit_fans_out_to_all_sinks(self) -> None:
        sink1 = MagicMock()
        sink2 = MagicMock()
        multi = MultiSink([sink1, sink2])
        trace = ExecutionTrace(run_id="fanout-test")

        multi.emit(trace)

        sink1.emit.assert_called_once_with(trace)
        sink2.emit.assert_called_once_with(trace)

    def test_all_sinks_receive_same_trace(self) -> None:
        traces1: list[ExecutionTrace] = []
        traces2: list[ExecutionTrace] = []

        def collect1(t: ExecutionTrace) -> None:
            traces1.append(t)

        def collect2(t: ExecutionTrace) -> None:
            traces2.append(t)

        sink1 = MagicMock()
        sink1.emit.side_effect = collect1
        sink2 = MagicMock()
        sink2.emit.side_effect = collect2
        multi = MultiSink([sink1, sink2])
        trace = ExecutionTrace(run_id="same-trace")

        multi.emit(trace)

        assert len(traces1) == 1
        assert len(traces2) == 1
        assert traces1[0].run_id == "same-trace"
        assert traces2[0].run_id == "same-trace"

    def test_sink_failure_does_not_block_other_sinks(self) -> None:
        sink1 = MagicMock()
        sink2 = MagicMock()
        sink2.emit.side_effect = ValueError("sink2 exploded")
        sink3 = MagicMock()
        multi = MultiSink([sink1, sink2, sink3])
        trace = ExecutionTrace(run_id="fail-isolation")

        failures = multi.emit(trace)

        sink1.emit.assert_called_once_with(trace)
        sink3.emit.assert_called_once_with(trace)
        assert len(failures) == 1
        assert "sink2 exploded" in failures[0]["error"]

    def test_sink_failure_tracked_by_name(self) -> None:
        class FailingSink:
            def emit(self, trace: ExecutionTrace) -> None:
                raise RuntimeError("oh no")

        sink = FailingSink()
        good = MagicMock()
        multi = MultiSink([good, sink])
        trace = ExecutionTrace(run_id="fail-name")

        failures = multi.emit(trace)

        assert len(failures) == 1
        assert failures[0]["sink"] == "FailingSink"
        assert failures[0]["error"] == "oh no"

    def test_add_sink_after_construction(self) -> None:
        sink1 = MagicMock()
        sink2 = MagicMock()
        multi = MultiSink([sink1])
        multi.add(sink2)
        trace = ExecutionTrace(run_id="add-after")

        multi.emit(trace)

        sink1.emit.assert_called_once_with(trace)
        sink2.emit.assert_called_once_with(trace)

    def test_empty_sink_list_does_not_error(self) -> None:
        multi = MultiSink()
        trace = ExecutionTrace(run_id="empty")
        failures = multi.emit(trace)
        assert failures == []

    def test_sink_failures_persisted_in_attribute(self) -> None:
        sink1 = MagicMock()
        sink1.emit.side_effect = ValueError("fail")
        multi = MultiSink([sink1])
        trace = ExecutionTrace(run_id="attr-test")

        multi.emit(trace)

        assert len(multi.sink_failures) == 1
        assert multi.sink_failures[0]["error"] == "fail"

    def test_sink_failures_cleared_between_emits(self) -> None:
        sink1 = MagicMock()
        sink1.emit.side_effect = ValueError("first fail")
        multi = MultiSink([sink1])

        multi.emit(ExecutionTrace(run_id="first"))
        assert len(multi.sink_failures) == 1

        sink1.emit.side_effect = None
        multi.emit(ExecutionTrace(run_id="second"))
        assert len(multi.sink_failures) == 0


class TestFileTraceSinkWriteMetrics:
    def test_writes_metrics_when_flag_enabled(self, tmp_path: Path) -> None:
        trace = ExecutionTrace(
            run_id="wm-test",
            workflow_name="wf",
            route_strategy="single",
            final_status="completed",
            elapsed_ms=50.0,
            node_order=["n1"],
        )
        sink = FileTraceSink(artifacts_dir=tmp_path, write_metrics=True)
        sink.emit(trace)

        metrics_file = tmp_path / "metrics_wm-test.json"
        assert metrics_file.exists()
        data = json.loads(metrics_file.read_text(encoding="utf-8"))
        assert data["run_id"] == "wm-test"
        assert data["elapsed_ms"] == 50.0

    def test_does_not_write_metrics_when_flag_disabled(self, tmp_path: Path) -> None:
        trace = ExecutionTrace(
            run_id="no-metrics",
            workflow_name="wf",
            route_strategy="single",
            final_status="completed",
            elapsed_ms=10.0,
        )
        sink = FileTraceSink(artifacts_dir=tmp_path, write_metrics=False)
        sink.emit(trace)

        metrics_file = tmp_path / "metrics_no-metrics.json"
        assert not metrics_file.exists()
