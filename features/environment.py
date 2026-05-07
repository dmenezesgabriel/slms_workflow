from __future__ import annotations

import statistics
from typing import Any

from src.scoring import score_result


def before_all(context: Any) -> None:
    context.evaluation_results = []


def after_scenario(context: Any, scenario: Any) -> None:
    answer = getattr(context, "last_answer", None)
    if answer is None:
        return

    score = score_result(answer)
    context.evaluation_results.append(
        {
            "name": scenario.name,
            "status": str(scenario.status),
            "elapsed_ms": getattr(context, "last_elapsed_ms", 0.0),
            "quality": score.quality,
            "usable": score.is_usable,
        }
    )

    context.last_answer = None
    context.last_trace_lines = []
    context.last_elapsed_ms = 0.0


def after_all(context: Any) -> None:
    results = getattr(context, "evaluation_results", [])
    if not results:
        return

    latencies = [result["elapsed_ms"] for result in results]
    qualities = [result["quality"] for result in results]
    usable_count = sum(1 for result in results if result["usable"])
    total = len(results)
    p50_ms = statistics.median(latencies)
    p95_ms = sorted(latencies)[max(0, int(total * 0.95) - 1)]
    quality_mean = sum(qualities) / total

    print("\nLive integration metrics")
    print(f"  cases: {total}")
    print(f"  usable accuracy: {usable_count / total:.2%}")
    print(f"  quality mean: {quality_mean:.2f}")
    print(f"  latency p50: {p50_ms:.1f} ms")
    print(f"  latency p95: {p95_ms:.1f} ms")
