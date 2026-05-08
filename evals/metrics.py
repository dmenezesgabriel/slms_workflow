"""
Per-technique metric dataclasses for the offline evaluation pipeline.

Each class covers one technique and exposes:
  - raw counters (incremented during evaluation)
  - computed properties (accuracy, rates, etc.)
  - to_mlflow_dict() → flat {dotted.name: float} dict for MLflow logging

Naming convention for MLflow keys:
  <technique>.<metric>   e.g.  router.tfidf.accuracy
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def timed(fn: Callable[[], object]) -> tuple[object, float]:
    """Call *fn* and return (result, elapsed_ms)."""
    t0 = time.perf_counter()
    result = fn()
    return result, (time.perf_counter() - t0) * 1000


def pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    idx = max(0, int(len(s) * p) - 1)
    return s[idx]


# ---------------------------------------------------------------------------
# TF-IDF Router
# ---------------------------------------------------------------------------


@dataclass
class RoutingMetrics:
    """Metrics for the TF-IDF fast-path router."""

    total: int = 0
    correct: int = 0
    en_total: int = 0
    en_correct: int = 0
    pt_total: int = 0
    pt_correct: int = 0
    below_threshold: int = 0
    latencies_ms: list[float] = field(default_factory=list)
    confidences: list[float] = field(default_factory=list)

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
    def below_threshold_rate(self) -> float:
        return self.below_threshold / self.total if self.total else 0.0

    @property
    def confidence_mean(self) -> float:
        return sum(self.confidences) / len(self.confidences) if self.confidences else 0.0

    @property
    def confidence_p10(self) -> float:
        return _percentile(self.confidences, 0.10)

    @property
    def p50_ms(self) -> float:
        return _percentile(self.latencies_ms, 0.50)

    @property
    def p95_ms(self) -> float:
        return _percentile(self.latencies_ms, 0.95)

    def to_mlflow_dict(self) -> dict[str, float]:
        return {
            "router.tfidf.accuracy": round(self.accuracy, 4),
            "router.tfidf.en_accuracy": round(self.en_accuracy, 4),
            "router.tfidf.pt_accuracy": round(self.pt_accuracy, 4),
            "router.tfidf.below_threshold_rate": round(self.below_threshold_rate, 4),
            "router.tfidf.confidence_mean": round(self.confidence_mean, 4),
            "router.tfidf.confidence_p10": round(self.confidence_p10, 4),
            "router.tfidf.latency_p50_ms": round(self.p50_ms, 2),
            "router.tfidf.latency_p95_ms": round(self.p95_ms, 2),
        }


# ---------------------------------------------------------------------------
# Deterministic Tool Selection
# ---------------------------------------------------------------------------


@dataclass
class ToolMetrics:
    """Metrics for the deterministic tool-selection paths (math, regex, NER)."""

    total: int = 0
    tool_correct: int = 0
    arg_correct: int = 0
    handled_deterministically: int = 0

    @property
    def tool_accuracy(self) -> float:
        return self.tool_correct / self.total if self.total else 0.0

    @property
    def arg_accuracy(self) -> float:
        return self.arg_correct / self.total if self.total else 0.0

    @property
    def coverage(self) -> float:
        """Fraction of cases handled without needing an LLM call."""
        return self.handled_deterministically / self.total if self.total else 0.0

    def to_mlflow_dict(self) -> dict[str, float]:
        return {
            "tools.deterministic.tool_accuracy": round(self.tool_accuracy, 4),
            "tools.deterministic.arg_accuracy": round(self.arg_accuracy, 4),
            "tools.deterministic.coverage": round(self.coverage, 4),
        }


# ---------------------------------------------------------------------------
# NER Entity Extraction
# ---------------------------------------------------------------------------


@dataclass
class NERMetrics:
    """Metrics for the spaCy NER pipeline and temporal-signal detection."""

    total_expected: int = 0
    found: int = 0
    label_errors: int = 0
    temporal_correct: int = 0
    temporal_total: int = 0

    @property
    def recall(self) -> float:
        return self.found / self.total_expected if self.total_expected else 0.0

    @property
    def temporal_accuracy(self) -> float:
        return self.temporal_correct / self.temporal_total if self.temporal_total else 0.0

    def to_mlflow_dict(self) -> dict[str, float]:
        return {
            "ner.entity_recall": round(self.recall, 4),
            "ner.temporal_accuracy": round(self.temporal_accuracy, 4),
        }


# ---------------------------------------------------------------------------
# Summarization Content Guard
# ---------------------------------------------------------------------------


@dataclass
class SummarizationGuardMetrics:
    """Metrics for the content guard that rejects degenerate summarization inputs."""

    degenerate_total: int = 0
    guard_caught: int = 0
    legitimate_total: int = 0
    guard_false_positives: int = 0

    @property
    def hit_rate(self) -> float:
        """Fraction of degenerate inputs correctly blocked."""
        return self.guard_caught / self.degenerate_total if self.degenerate_total else 0.0

    @property
    def false_positive_rate(self) -> float:
        """Fraction of legitimate inputs incorrectly blocked."""
        return self.guard_false_positives / self.legitimate_total if self.legitimate_total else 0.0

    def to_mlflow_dict(self) -> dict[str, float]:
        return {
            "summarization.guard_hit_rate": round(self.hit_rate, 4),
            "summarization.guard_false_positive_rate": round(self.false_positive_rate, 4),
        }


# ---------------------------------------------------------------------------
# QA Proper-Noun Fallback (N09 fix)
# ---------------------------------------------------------------------------


@dataclass
class QAProperNounMetrics:
    """Metrics for the proper-noun Wikipedia fallback in the QA handler."""

    total: int = 0
    correct: int = 0
    triggered: int = 0

    @property
    def accuracy(self) -> float:
        """Correct entity extracted / cases where extraction was expected."""
        return self.correct / self.total if self.total else 0.0

    @property
    def trigger_rate(self) -> float:
        """Fraction of all cases where the fallback was triggered."""
        return self.triggered / self.total if self.total else 0.0

    def to_mlflow_dict(self) -> dict[str, float]:
        return {
            "qa.proper_noun_accuracy": round(self.accuracy, 4),
            "qa.proper_noun_trigger_rate": round(self.trigger_rate, 4),
        }
