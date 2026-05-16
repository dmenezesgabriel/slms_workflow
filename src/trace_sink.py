from __future__ import annotations

import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Protocol

from src.graph.trace_types import ExecutionTrace

logger = logging.getLogger(__name__)


class TraceSink(Protocol):
    def emit(self, trace: ExecutionTrace) -> None: ...


_DEFAULT_ARTIFACTS_DIR = Path("artifacts")


@dataclass
class MetricsSummary:
    run_id: str
    route_strategy: str
    workflow_name: str
    tool_count: int
    fallback_route: bool
    elapsed_ms: float
    completion_status: str
    node_count: int
    sink_failures: list[dict[str, str]] = field(default_factory=list)


def build_metrics_summary(exec_trace: ExecutionTrace) -> MetricsSummary:
    return MetricsSummary(
        run_id=exec_trace.run_id,
        route_strategy=exec_trace.route_strategy,
        workflow_name=exec_trace.workflow_name,
        tool_count=len(exec_trace.tool_calls),
        fallback_route=exec_trace.route_strategy == "agent",
        elapsed_ms=exec_trace.elapsed_ms,
        completion_status=exec_trace.final_status,
        node_count=len(exec_trace.node_order),
    )


def write_metrics_artifact(
    metrics: MetricsSummary,
    artifacts_dir: Path = _DEFAULT_ARTIFACTS_DIR,
) -> Path:
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    path = artifacts_dir / f"metrics_{metrics.run_id}.json"
    path.write_text(
        json.dumps(asdict(metrics), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.debug("Metrics artifact written: %s", path)
    return path


class MultiSink:
    def __init__(self, sinks: list[TraceSink] | None = None) -> None:
        self._sinks: list[TraceSink] = sinks or []
        self.sink_failures: list[dict[str, str]] = []

    def add(self, sink: TraceSink) -> None:
        self._sinks.append(sink)

    def emit(self, trace: ExecutionTrace) -> list[dict[str, str]]:
        self.sink_failures.clear()
        for sink in self._sinks:
            try:
                sink.emit(trace)
            except Exception as exc:
                logger.exception("Sink %s failed", type(sink).__name__)
                self.sink_failures.append(
                    {
                        "sink": type(sink).__name__,
                        "error": str(exc),
                    }
                )
        return self.sink_failures


@dataclass
class FileTraceSink:
    artifacts_dir: Path = field(default_factory=lambda: _DEFAULT_ARTIFACTS_DIR)
    write_metrics: bool = False

    def __post_init__(self) -> None:
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

    def emit(self, trace: ExecutionTrace) -> None:
        filename = f"trace_{trace.run_id}.json"
        path = self.artifacts_dir / filename
        try:
            content = trace.to_json(indent=2, redact=True)
            path.write_text(content, encoding="utf-8")
            logger.debug("Trace artifact written: %s", path)
        except Exception:
            logger.exception("Failed to write trace artifact: %s", path)
        if self.write_metrics:
            try:
                metrics = build_metrics_summary(trace)
                write_metrics_artifact(metrics, self.artifacts_dir)
            except Exception:
                logger.exception("Failed to write metrics artifact")


def generate_run_id() -> str:
    return uuid.uuid4().hex[:12]


def build_trace_from_run(
    run_id: str,
    workflow_name: str,
    workflow_description: str,
    route_strategy: str,
    route_confidence: float,
    exec_trace: ExecutionTrace | None,
    start_time: float,
    end_time: float,
    final_status: str = "completed",
    error: str | None = None,
) -> ExecutionTrace:
    result = ExecutionTrace(
        version="1.0",
        run_id=run_id,
        workflow_name=workflow_name,
        workflow_description=workflow_description,
        route_strategy=route_strategy,
        route_confidence=route_confidence,
        start_time=start_time,
        end_time=end_time,
        elapsed_ms=round((end_time - start_time) * 1000, 1),
        final_status=final_status,
        error=error,
    )
    if exec_trace is not None:
        result.nodes = dict(exec_trace.nodes)
        result.node_order = list(exec_trace.node_order)
        result.tool_calls = list(exec_trace.tool_calls)
    return result
