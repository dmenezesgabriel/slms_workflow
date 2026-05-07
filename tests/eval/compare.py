"""
Compare the most recent evaluation runs stored in MLflow.

Usage (no server needed):
    .venv/bin/python -m tests.eval.compare          # last 5 runs
    .venv/bin/python -m tests.eval.compare --n 10   # last N runs
"""

from __future__ import annotations

import sys
from pathlib import Path

import mlflow

_MLRUNS_DIR = str(Path(__file__).parent.parent.parent / "mlruns")
_EXPERIMENT = "slms_evaluation"

_TECHNIQUES = {
    "TF-IDF Router": [
        "router.tfidf.accuracy",
        "router.tfidf.en_accuracy",
        "router.tfidf.pt_accuracy",
        "router.tfidf.below_threshold_rate",
        "router.tfidf.confidence_mean",
        "router.tfidf.confidence_p10",
        "router.tfidf.latency_p50_ms",
        "router.tfidf.latency_p95_ms",
    ],
    "Deterministic Tools": [
        "tools.deterministic.tool_accuracy",
        "tools.deterministic.arg_accuracy",
        "tools.deterministic.coverage",
    ],
    "NER (spaCy)": [
        "ner.entity_recall",
        "ner.temporal_accuracy",
    ],
    "Summarization Guard": [
        "summarization.guard_hit_rate",
        "summarization.guard_false_positive_rate",
    ],
    "QA Proper-Noun Fallback": [
        "qa.proper_noun_accuracy",
        "qa.proper_noun_trigger_rate",
    ],
}

_METRIC_WIDTH = 40
_COL_WIDTH = 10


def _pct(v: float | None) -> str:
    if v is None:
        return "  —  "
    return f"{v * 100:6.1f}%"


def _ms(v: float | None) -> str:
    if v is None:
        return "  —  "
    return f"{v:6.1f}ms"


def _fmt(key: str, v: float | None) -> str:
    if v is None:
        return "    —    "
    if "latency" in key:
        return _ms(v)
    return _pct(v)


def main() -> None:
    n = 5
    for i, arg in enumerate(sys.argv[1:]):
        if arg == "--n" and i + 2 < len(sys.argv):
            n = int(sys.argv[i + 2])

    mlflow.set_tracking_uri(_MLRUNS_DIR)
    client = mlflow.MlflowClient()
    exp = client.get_experiment_by_name(_EXPERIMENT)
    if exp is None:
        print(f"No experiment named {_EXPERIMENT!r} found in {_MLRUNS_DIR}")
        print("Run 'python -m tests.eval.runner' first to create it.")
        sys.exit(1)

    runs = client.search_runs(
        experiment_ids=[exp.experiment_id],
        order_by=["start_time DESC"],
        max_results=n,
    )

    if not runs:
        print("No runs found.")
        sys.exit(0)

    # Header
    run_labels = [r.data.tags.get("mlflow.runName", r.info.run_id[:8]) for r in runs]
    header = f"  {'Metric':<{_METRIC_WIDTH}}" + "".join(f"{lbl:>{_COL_WIDTH}}" for lbl in run_labels)
    sep = "─" * len(header)

    print(f"\n{'═' * len(header)}")
    print(f"  METRIC COMPARISON  (last {len(runs)} runs, newest first)")
    print(f"{'═' * len(header)}")

    for technique, keys in _TECHNIQUES.items():
        print(f"\n  ── {technique} {'─' * max(0, len(sep) - len(technique) - 6)}")
        for key in keys:
            values = [r.data.metrics.get(key) for r in runs]
            row = f"  {key:<{_METRIC_WIDTH}}" + "".join(f"{_fmt(key, v):>{_COL_WIDTH}}" for v in values)

            # Highlight if latest run differs from previous
            if len(values) >= 2 and values[0] is not None and values[1] is not None:
                delta = values[0] - values[1]
                arrow = " ▲" if delta > 0.001 else (" ▼" if delta < -0.001 else "  ")
                row += arrow
            print(row)

    print(f"\n  Runs compared: {', '.join(r.info.run_id[:8] for r in runs)}")
    print(f"  Tracking URI:  {_MLRUNS_DIR}\n")


if __name__ == "__main__":
    main()
