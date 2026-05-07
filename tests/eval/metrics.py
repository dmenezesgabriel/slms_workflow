"""Metric types and computation helpers for the offline evaluation runner."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class RoutingMetrics:
    total: int = 0
    correct: int = 0
    en_total: int = 0
    en_correct: int = 0
    pt_total: int = 0
    pt_correct: int = 0
    latencies_ms: list[float] = field(default_factory=list)

    @property
    def accuracy(self) -> float:
        return self.correct / self.total if self.total else 0.0

    @property
    def en_accuracy(self) -> float:
        return self.en_correct / self.en_total if self.en_total else 0.0

    @property
    def pt_accuracy(self) -> float:
        return self.pt_correct / self.pt_total if self.pt_total else 0.0

    @property
    def p50_ms(self) -> float:
        s = sorted(self.latencies_ms)
        return s[len(s) // 2] if s else 0.0

    @property
    def p95_ms(self) -> float:
        s = sorted(self.latencies_ms)
        idx = max(0, int(len(s) * 0.95) - 1)
        return s[idx] if s else 0.0


@dataclass
class ToolMetrics:
    total: int = 0
    tool_correct: int = 0
    arg_correct: int = 0

    @property
    def tool_accuracy(self) -> float:
        return self.tool_correct / self.total if self.total else 0.0

    @property
    def arg_accuracy(self) -> float:
        return self.arg_correct / self.total if self.total else 0.0


@dataclass
class NERMetrics:
    total_expected: int = 0
    found: int = 0
    label_errors: int = 0

    @property
    def recall(self) -> float:
        return self.found / self.total_expected if self.total_expected else 0.0


def timed(fn: Callable[[], object]) -> tuple[object, float]:
    """Call *fn* and return (result, elapsed_ms)."""
    t0 = time.perf_counter()
    result = fn()
    return result, (time.perf_counter() - t0) * 1000


def pct(value: float) -> str:
    return f"{value * 100:.1f}%"
