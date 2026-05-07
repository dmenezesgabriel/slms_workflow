"""
Offline evaluation runner — tests deterministic components without an LLM.

Usage:
    uv run python -m tests.eval.runner            # print report
    uv run python -m tests.eval.runner --save     # also write results.json
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from app.router import classify_ml
from app.schemas import IntentClassification
from tests.eval.dataset import NER_CASES, ROUTING_CASES, TOOL_CASES
from tests.eval.metrics import NERMetrics, RoutingMetrics, ToolMetrics, pct, timed

# ---------------------------------------------------------------------------
# Routing evaluation (TF-IDF fast path only)
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
            failures.append(
                f"  MISS  [{lang}] {prompt!r} → expected {expected!r} (below threshold)"
            )
            continue

        assert isinstance(classification, IntentClassification)
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
# Tool selection evaluation (deterministic paths only)
# ---------------------------------------------------------------------------


def _eval_tools() -> ToolMetrics:
    from app.handlers.function_calling import deterministic_decision

    m = ToolMetrics()
    failures: list[str] = []

    for prompt, expected_tool, arg_key, arg_substring in TOOL_CASES:
        decision = deterministic_decision(prompt)
        m.total += 1

        if decision is None:
            failures.append(f"  MISS  {prompt!r} → expected tool={expected_tool!r} (no decision)")
            continue

        tool_ok = decision.tool_name == expected_tool
        if tool_ok:
            m.tool_correct += 1
        else:
            failures.append(
                f"  TOOL  {prompt!r} → got {decision.tool_name!r}, " f"expected {expected_tool!r}"
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
# NER evaluation (spaCy model, lazy loaded)
# ---------------------------------------------------------------------------


def _eval_ner() -> NERMetrics | None:
    try:
        from app import ner as ner_mod
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

    if failures:
        print("\n[ner failures]")
        for f in failures:
            print(f)

    return m


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def _row(label: str, value: str, width: int = 28) -> str:
    return f"  {label:<{width}} {value}"


def _print_report(rm: RoutingMetrics, tm: ToolMetrics, nm: NERMetrics | None) -> None:
    print("\n" + "=" * 50)
    print("  EVALUATION REPORT")
    print("=" * 50)

    print("\n── Routing (TF-IDF fast path) ──────────────────")
    print(_row("Overall accuracy:", f"{pct(rm.accuracy)}  ({rm.correct}/{rm.total})"))
    print(_row("English accuracy:", f"{pct(rm.en_accuracy)}  ({rm.en_correct}/{rm.en_total})"))
    print(_row("Portuguese accuracy:", f"{pct(rm.pt_accuracy)}  ({rm.pt_correct}/{rm.pt_total})"))
    print(_row("Latency p50 / p95:", f"{rm.p50_ms:.1f} ms / {rm.p95_ms:.1f} ms"))

    print("\n── Tool selection (deterministic) ──────────────")
    print(_row("Tool name accuracy:", f"{pct(tm.tool_accuracy)}  ({tm.tool_correct}/{tm.total})"))
    print(_row("Arg quality:", f"{pct(tm.arg_accuracy)}  ({tm.arg_correct}/{tm.total})"))

    if nm is not None:
        print("\n── NER entity recall ───────────────────────────")
        print(
            _row(
                "Entity recall:",
                f"{pct(nm.recall)}  ({nm.found}/{nm.total_expected})",
            )
        )
    else:
        print("\n── NER entity recall ───────────────────────────")
        print("  (skipped — app.ner not available)")

    print("\n" + "=" * 50 + "\n")


def _to_dict(rm: RoutingMetrics, tm: ToolMetrics, nm: NERMetrics | None) -> dict[str, object]:
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "routing": {
            "accuracy": round(rm.accuracy, 4),
            "en_accuracy": round(rm.en_accuracy, 4),
            "pt_accuracy": round(rm.pt_accuracy, 4),
            "correct": rm.correct,
            "total": rm.total,
            "latency_p50_ms": round(rm.p50_ms, 2),
            "latency_p95_ms": round(rm.p95_ms, 2),
        },
        "tool": {
            "tool_accuracy": round(tm.tool_accuracy, 4),
            "arg_accuracy": round(tm.arg_accuracy, 4),
            "correct": tm.tool_correct,
            "total": tm.total,
        },
        "ner": (
            {
                "recall": round(nm.recall, 4),
                "found": nm.found,
                "total_expected": nm.total_expected,
            }
            if nm is not None
            else None
        ),
    }


def main() -> None:
    save = "--save" in sys.argv

    print("Running routing evaluation…")
    rm = _eval_routing()

    print("Running tool selection evaluation…")
    tm = _eval_tools()

    print("Running NER evaluation…")
    nm = _eval_ner()

    _print_report(rm, tm, nm)

    if save:
        out = Path(__file__).parent / "results.json"
        history: list[dict] = []  # type: ignore[type-arg]
        if out.exists():
            history = json.loads(out.read_text())
        history.append(_to_dict(rm, tm, nm))
        out.write_text(json.dumps(history, indent=2))
        print(f"Results appended to {out}\n")


if __name__ == "__main__":
    main()
