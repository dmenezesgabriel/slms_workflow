# Observability: Trace Sinks & Runtime Metrics

## Architecture

Every user request produces a single `ExecutionTrace` that captures the full
execution: chosen route, DAG nodes visited, tool calls, timing, and final
status. The trace is broadcast to all registered **sinks** through a
`MultiSink` fan-out. No sink can crash the run — failures are caught and
recorded in the runtime metrics.

```
User Input → Orchestrator → build_trace_from_run() → MultiSink.emit(trace)
                                                           ├── FileTraceSink   → artifacts/trace_{run_id}.json
                                                           ├── StatusCollector → live CLI console
                                                           └── (your sink)     → ...
                              build_metrics_summary(trace) → write_metrics_artifact()
                                                              → artifacts/metrics_{run_id}.json
```

## Sink Interface

Any object with an `emit(self, trace: ExecutionTrace) -> None` method is a
valid sink. The protocol is defined in `src/trace_sink.py`:

```python
class TraceSink(Protocol):
    def emit(self, trace: ExecutionTrace) -> None: ...
```

### How to Add a New Sink

1. Create a class that implements the `emit` method.
2. Register it with the `MultiSink` in the `Orchestrator`.

Example — a logging sink:

```python
import logging
from src.graph.trace_types import ExecutionTrace

class LoggingSink:
    def __init__(self) -> None:
        self.logger = logging.getLogger("trace")

    def emit(self, trace: ExecutionTrace) -> None:
        self.logger.info("Run %s: %s route, %d tools, %s",
                         trace.run_id, trace.route_strategy,
                         len(trace.tool_calls), trace.final_status)
```

Registering in `Orchestrator.__init__`:

```python
self._trace_sink = MultiSink([
    FileTraceSink(),
    LoggingSink(),
])
```

### Built-in Sinks

| Sink | File | Writes |
|------|------|--------|
| `FileTraceSink` | `src/trace_sink.py` | `artifacts/trace_{run_id}.json` |
| `StatusCollector` | `src/ui.py` | Live console output (via `trace.subscribe`) |

## MultiSink

`MultiSink` (in `src/trace_sink.py`) holds a list of sinks and fans out every
`emit` call to all of them. Sink failures are caught individually so one
failing sink does not block others. Failures are returned from `emit()` and
stored in `sink_failures`:

```python
multi = MultiSink([sink_a, sink_b])
failures = multi.emit(trace)        # returns list[dict[str, str]]
multi.sink_failures                  # same list, persisted
```

Each failure entry:
```json
{"sink": "SinkClassName", "error": "exception message"}
```

## Metrics Summary

After every run a `MetricsSummary` dataclass is built from the
`ExecutionTrace` and persisted alongside the trace artifact.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `run_id` | `str` | Unique run identifier |
| `route_strategy` | `str` | `"single"`, `"composed"`, `"agent"`, or `"direct"` |
| `workflow_name` | `str` | Name of the executed workflow graph |
| `tool_count` | `int` | Number of tool calls during the run |
| `fallback_route` | `bool` | `True` when `route_strategy == "agent"` (the fallback path) |
| `elapsed_ms` | `float` | Total wall-clock time in milliseconds |
| `completion_status` | `str` | `"completed"` or error status |
| `node_count` | `int` | Number of DAG nodes executed |
| `sink_failures` | `list[dict]` | Per-sink failures captured during fan-out |

### Artifact Location

Written to `artifacts/metrics_{run_id}.json` by `write_metrics_artifact()`.

```json
{
  "run_id": "a1b2c3d4e5f6",
  "route_strategy": "composed",
  "workflow_name": "on_demand_qa",
  "tool_count": 3,
  "fallback_route": false,
  "elapsed_ms": 2450.3,
  "completion_status": "completed",
  "node_count": 4,
  "sink_failures": []
}
```

## Future: OpenTelemetry Sink Mapping

The internal event and span model maps naturally to OpenTelemetry concepts.
A future `OTelSpanSink` would implement `TraceSink` and translate each
`ExecutionTrace` into OTel spans and attributes.

| Internal Concept | OpenTelemetry |
|---|---|
| `ExecutionTrace` | A `tracing.Span` / `tracing.Trace` |
| `run_id` | `trace_id` (converted to 16-byte) |
| `span_enter` / `span_exit` | `startSpan` / `endSpan` |
| `NodeTrace` per DAG node | Child span under the run trace |
| `ToolCallTrace` | Span event with tool attributes |
| `route_strategy` | `Span.SetAttribute("workflow.route", ...)` |
| `tool_count`, `node_count` | Span metrics / attributes |
| `elapsed_ms` | Span duration |
| `MetricsSummary` | OTel metrics (counter / histogram) |

A skeletal implementation sketch:

```python
from opentelemetry import trace as otel_trace
from src.graph.trace_types import ExecutionTrace

class OTelSpanSink:
    def __init__(self) -> None:
        self.tracer = otel_trace.get_tracer(__name__)

    def emit(self, trace_data: ExecutionTrace) -> None:
        with self.tracer.start_as_current_span(
            f"workflow.{trace_data.workflow_name}",
            attributes={
                "run_id": trace_data.run_id,
                "route": trace_data.route_strategy,
                "tool_count": len(trace_data.tool_calls),
                "node_count": len(trace_data.node_order),
                "elapsed_ms": trace_data.elapsed_ms,
            },
        ) as span:
            for tc in trace_data.tool_calls:
                span.add_event(
                    f"tool.{tc.tool_name}",
                    {"success": tc.success, "elapsed_ms": tc.elapsed_ms},
                )
```

## Existing Tests

Unit tests covering metrics, multi-sink fan-out, and sink failure isolation
live in `tests/unit/src/test_trace_sink.py`.
