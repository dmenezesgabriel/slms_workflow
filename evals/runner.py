"""
Offline evaluation runner — tests deterministic components without an LLM.

Logs every run to MLflow (file-based, no server needed).
Results are also saved to results.json for historical comparison.

Usage:
    uv run python -m evals.runner            # run + log to MLflow
    uv run python -m evals.runner --save     # also write results.json
    uv run python -m evals.runner --no-mlflow

CLI inspection (no server):
    .venv/bin/mlflow runs list --experiment-name slms_evaluation
    .venv/bin/python -m evals.compare
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import mlflow

from src.router import classify_ml
from src.schemas import IntentClassification
from evals.dataset import (
    NER_CASES,
    QA_PROPER_NOUN_CASES,
    ROUTING_CASES,
    SUMMARIZATION_GUARD_CASES,
    TEMPORAL_CASES,
    TOOL_CASES,
)
from evals.metrics import (
    NERMetrics,
    QAProperNounMetrics,
    RoutingMetrics,
    SummarizationGuardMetrics,
    ToolMetrics,
    pct,
    timed,
)

_MLFLOW_EXPERIMENT = "slms_evaluation"
_MLRUNS_DIR = str(Path(__file__).parent.parent / "mlruns")


# ---------------------------------------------------------------------------
# Router (TF-IDF fast path)
# ---------------------------------------------------------------------------


def _eval_routing() -> RoutingMetrics:
    m = RoutingMetrics()
    failures: list[str] = []

    for prompt, expected, lang in ROUTING_CASES:

        def _run(p: str = prompt) -> IntentClassification | None:
            return classify_ml(p)

        classification, elapsed = timed(_run)
        m.total += 1
        m.latencies_ms.append(elapsed)

        if lang == "en":
            m.en_total += 1
        else:
            m.pt_total += 1

        if classification is None:
            m.below_threshold += 1
            failures.append(
                f"  MISS  [{lang}] {prompt!r} → expected {expected!r} (below threshold)"
            )
            continue

        assert isinstance(classification, IntentClassification)
        m.confidences.append(classification.confidence)
        got = classification.intent
        ok = got == expected
        if ok:
            m.correct += 1
            if lang == "en":
                m.en_correct += 1
            else:
                m.pt_correct += 1
        else:
            failures.append(f"  FAIL  [{lang}] {prompt!r} → got {got!r}, expected {expected!r}")

    if failures:
        print("\n[routing failures]")
        for f in failures:
            print(f)

    return m


# ---------------------------------------------------------------------------
# Deterministic tool selection
# ---------------------------------------------------------------------------


def _eval_tools() -> ToolMetrics:
    from src.handlers.function_calling import deterministic_decision

    m = ToolMetrics()
    failures: list[str] = []

    for prompt, expected_tool, arg_key, arg_substring in TOOL_CASES:
        decision = deterministic_decision(prompt)
        m.total += 1

        if decision is None:
            failures.append(f"  MISS  {prompt!r} → expected tool={expected_tool!r} (no decision)")
            continue

        m.handled_deterministically += 1
        tool_ok = decision.tool_name == expected_tool
        if tool_ok:
            m.tool_correct += 1
        else:
            failures.append(
                f"  TOOL  {prompt!r} → got {decision.tool_name!r}, expected {expected_tool!r}"
            )
            continue

        arg_val = str(decision.arguments.get(arg_key, ""))
        arg_ok = arg_substring.lower() in arg_val.lower()
        if arg_ok:
            m.arg_correct += 1
        else:
            failures.append(
                f"  ARG   {prompt!r} → {arg_key}={arg_val!r}, "
                f"expected to contain {arg_substring!r}"
            )

    if failures:
        print("\n[tool failures]")
        for f in failures:
            print(f)

    return m


# ---------------------------------------------------------------------------
# NER — entity recall + temporal accuracy
# ---------------------------------------------------------------------------


def _eval_ner() -> NERMetrics | None:
    try:
        from src import ner as ner_mod
    except ImportError:
        return None

    m = NERMetrics()
    failures: list[str] = []

    for prompt, expected_entities in NER_CASES:
        try:
            entities = ner_mod.extract(prompt)
        except Exception as exc:
            failures.append(f"  ERR   {prompt!r} → {exc}")
            m.total_expected += len(expected_entities)
            continue

        entity_texts = [e.text.lower() for e in entities]
        for frag, label in expected_entities:
            m.total_expected += 1
            found = any(frag.lower() in t for t in entity_texts)
            if found:
                m.found += 1
            else:
                failures.append(
                    f"  MISS  {prompt!r} → expected ({frag!r}, {label!r}), "
                    f"got {[(e.text, e.label) for e in entities]}"
                )

    # Temporal-signal accuracy
    for text, expected_temporal in TEMPORAL_CASES:
        m.temporal_total += 1
        got = ner_mod.is_temporal(text)
        if got == expected_temporal:
            m.temporal_correct += 1
        else:
            failures.append(
                f"  TEMP  {text!r} → expected is_temporal={expected_temporal}, got {got}"
            )

    if failures:
        print("\n[ner failures]")
        for f in failures:
            print(f)

    return m


# ---------------------------------------------------------------------------
# Summarization content guard
# ---------------------------------------------------------------------------


def _eval_summarization_guard() -> SummarizationGuardMetrics:
    from src.handlers.summarization import handle
    from src.schemas import FinalAnswer

    m = SummarizationGuardMetrics()
    failures: list[str] = []

    class _NeverCallLLM:
        def structured(self, *a: object, **kw: object) -> object:
            raise AssertionError("LLM must not be called for degenerate input")

    class _AlwaysOkLLM:
        def structured(self, *a: object, **kw: object) -> object:
            from src.schemas import SummaryResult

            return SummaryResult(title="t", summary="s", key_points=[])

    for prompt, should_block in SUMMARIZATION_GUARD_CASES:
        if should_block:
            m.degenerate_total += 1
            try:
                result = handle(prompt, _NeverCallLLM())  # type: ignore[arg-type]
                if isinstance(result, FinalAnswer):
                    m.guard_caught += 1
                else:
                    failures.append(
                        f"  MISS  {prompt!r} → guard did not block (got {type(result).__name__})"
                    )
            except AssertionError:
                failures.append(f"  FAIL  {prompt!r} → LLM was called for degenerate input")
        else:
            m.legitimate_total += 1
            try:
                result = handle(prompt, _AlwaysOkLLM())  # type: ignore[arg-type]
                from src.schemas import SummaryResult

                if not isinstance(result, SummaryResult):
                    m.guard_false_positives += 1
                    failures.append(
                        f"  FP    {prompt!r} → guard blocked legitimate input"
                    )
            except AssertionError:
                m.guard_false_positives += 1
                failures.append(f"  FP    {prompt!r} → LLM not called for legitimate input")

    if failures:
        print("\n[summarization guard failures]")
        for f in failures:
            print(f)

    return m


# ---------------------------------------------------------------------------
# QA proper-noun fallback (N09)
# ---------------------------------------------------------------------------


def _eval_qa_proper_noun() -> QAProperNounMetrics:
    from src.handlers.question_answering import _PROPER_NOUN_RE, _WHAT_IS_RE

    m = QAProperNounMetrics()
    failures: list[str] = []

    for prompt, expected_entity in QA_PROPER_NOUN_CASES:
        m.total += 1
        wi = _WHAT_IS_RE.search(prompt)

        if wi is not None:
            match = _PROPER_NOUN_RE.search(prompt, wi.end())
            extracted = match.group(1) if match else None
            m.triggered += 1
        else:
            extracted = None

        if extracted == expected_entity:
            if expected_entity is not None:
                m.correct += 1
        else:
            failures.append(
                f"  FAIL  {prompt!r} → extracted={extracted!r}, expected={expected_entity!r}"
            )

    # Cases where expected_entity is None and we correctly extracted nothing
    # are implicitly correct (total - correct covers expected-None cases that fired)
    # Re-count: correct = cases where (extracted == expected_entity)
    m.correct = sum(
        1
        for prompt, expected_entity in QA_PROPER_NOUN_CASES
        if _extract_entity(prompt) == expected_entity
    )

    if failures:
        print("\n[qa proper-noun failures]")
        for f in failures:
            print(f)

    return m


def _extract_entity(prompt: str) -> str | None:
    from src.handlers.question_answering import _PROPER_NOUN_RE, _WHAT_IS_RE

    wi = _WHAT_IS_RE.search(prompt)
    if wi is None:
        return None
    m = _PROPER_NOUN_RE.search(prompt, wi.end())
    return m.group(1) if m else None


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def _row(label: str, value: str, width: int = 32) -> str:
    return f"  {label:<{width}} {value}"


def _print_report(
    rm: RoutingMetrics,
    tm: ToolMetrics,
    nm: NERMetrics | None,
    sgm: SummarizationGuardMetrics,
    qam: QAProperNounMetrics,
) -> None:
    print("\n" + "=" * 56)
    print("  EVALUATION REPORT")
    print("=" * 56)

    print("\n── Technique: TF-IDF Router ─────────────────────────────")
    print(_row("Overall accuracy:", f"{pct(rm.accuracy)}  ({rm.correct}/{rm.total})"))
    print(_row("English accuracy:", f"{pct(rm.en_accuracy)}  ({rm.en_correct}/{rm.en_total})"))
    print(_row("Portuguese accuracy:", f"{pct(rm.pt_accuracy)}  ({rm.pt_correct}/{rm.pt_total})"))
    print(_row("Below-threshold rate:", pct(rm.below_threshold_rate)))
    print(_row("Confidence mean / p10:", f"{rm.confidence_mean:.2f} / {rm.confidence_p10:.2f}"))
    print(_row("Latency p50 / p95:", f"{rm.p50_ms:.1f} ms / {rm.p95_ms:.1f} ms"))

    print("\n── Technique: Deterministic Tools ───────────────────────")
    print(_row("Tool name accuracy:", f"{pct(tm.tool_accuracy)}  ({tm.tool_correct}/{tm.total})"))
    print(_row("Arg quality:", f"{pct(tm.arg_accuracy)}  ({tm.arg_correct}/{tm.total})"))
    print(_row("LLM-free coverage:", pct(tm.coverage)))

    if nm is not None:
        print("\n── Technique: NER (spaCy xx_ent_wiki_sm) ────────────────")
        print(_row("Entity recall:", f"{pct(nm.recall)}  ({nm.found}/{nm.total_expected})"))
        print(_row("Temporal accuracy:", f"{pct(nm.temporal_accuracy)}  ({nm.temporal_correct}/{nm.temporal_total})"))
    else:
        print("\n── Technique: NER ───────────────────────────────────────")
        print("  (skipped — spaCy model not available)")

    print("\n── Technique: Summarization Guard ───────────────────────")
    print(_row("Guard hit rate:", f"{pct(sgm.hit_rate)}  ({sgm.guard_caught}/{sgm.degenerate_total})"))
    print(_row("False-positive rate:", f"{pct(sgm.false_positive_rate)}  ({sgm.guard_false_positives}/{sgm.legitimate_total})"))

    print("\n── Technique: QA Proper-Noun Fallback ───────────────────")
    print(_row("Extraction accuracy:", f"{pct(qam.accuracy)}  ({qam.correct}/{qam.total})"))
    print(_row("Trigger rate:", pct(qam.trigger_rate)))

    print("\n" + "=" * 56 + "\n")


# ---------------------------------------------------------------------------
# MLflow logging
# ---------------------------------------------------------------------------


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], text=True
        ).strip()
    except Exception:
        return "unknown"


def _log_to_mlflow(
    rm: RoutingMetrics,
    tm: ToolMetrics,
    nm: NERMetrics | None,
    sgm: SummarizationGuardMetrics,
    qam: QAProperNounMetrics,
) -> str:
    mlflow.set_tracking_uri(_MLRUNS_DIR)
    mlflow.set_experiment(_MLFLOW_EXPERIMENT)

    with mlflow.start_run(run_name=f"eval_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}") as run:
        mlflow.set_tags({
            "git_sha": _git_sha(),
            "mode": "offline",
        })

        # Dataset sizes as params
        from evals.dataset import (
            NER_CASES,
            QA_PROPER_NOUN_CASES,
            ROUTING_CASES,
            SUMMARIZATION_GUARD_CASES,
            TEMPORAL_CASES,
            TOOL_CASES,
        )
        mlflow.log_params({
            "dataset.routing_cases": len(ROUTING_CASES),
            "dataset.tool_cases": len(TOOL_CASES),
            "dataset.ner_cases": len(NER_CASES),
            "dataset.temporal_cases": len(TEMPORAL_CASES),
            "dataset.guard_cases": len(SUMMARIZATION_GUARD_CASES),
            "dataset.qa_proper_noun_cases": len(QA_PROPER_NOUN_CASES),
        })

        # Per-technique metrics
        mlflow.log_metrics(rm.to_mlflow_dict())
        mlflow.log_metrics(tm.to_mlflow_dict())
        if nm is not None:
            mlflow.log_metrics(nm.to_mlflow_dict())
        mlflow.log_metrics(sgm.to_mlflow_dict())
        mlflow.log_metrics(qam.to_mlflow_dict())

        return run.info.run_id


# ---------------------------------------------------------------------------
# JSON results
# ---------------------------------------------------------------------------


def _to_dict(
    rm: RoutingMetrics,
    tm: ToolMetrics,
    nm: NERMetrics | None,
    sgm: SummarizationGuardMetrics,
    qam: QAProperNounMetrics,
) -> dict[str, object]:
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "routing": rm.to_mlflow_dict(),
        "tool": tm.to_mlflow_dict(),
        "ner": nm.to_mlflow_dict() if nm is not None else None,
        "summarization": sgm.to_mlflow_dict(),
        "qa": qam.to_mlflow_dict(),
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    save = "--save" in sys.argv
    use_mlflow = "--no-mlflow" not in sys.argv

    print("Running routing evaluation…")
    rm = _eval_routing()

    print("Running tool selection evaluation…")
    tm = _eval_tools()

    print("Running NER evaluation…")
    nm = _eval_ner()

    print("Running summarization guard evaluation…")
    sgm = _eval_summarization_guard()

    print("Running QA proper-noun fallback evaluation…")
    qam = _eval_qa_proper_noun()

    _print_report(rm, tm, nm, sgm, qam)

    run_id: str | None = None
    if use_mlflow:
        run_id = _log_to_mlflow(rm, tm, nm, sgm, qam)
        print(f"MLflow run logged: {run_id}")
        print(f"  Tracking URI : {_MLRUNS_DIR}")
        print(f"  Experiment   : {_MLFLOW_EXPERIMENT}")
        print(f"  CLI commands :")
        print(f"    mlflow runs list --experiment-name {_MLFLOW_EXPERIMENT}")
        print(f"    python -m evals.compare\n")

    if save:
        out = Path(__file__).parent / "results.json"
        history: list[dict] = []  # type: ignore[type-arg]
        if out.exists():
            history = json.loads(out.read_text())
        entry = _to_dict(rm, tm, nm, sgm, qam)
        if run_id:
            entry["mlflow_run_id"] = run_id
        history.append(entry)
        out.write_text(json.dumps(history, indent=2))
        print(f"Results appended to {out}\n")


if __name__ == "__main__":
    main()
