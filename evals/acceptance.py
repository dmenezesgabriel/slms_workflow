"""End-to-end acceptance benchmark for complex user-facing prompts.

This runner executes one case at a time against the local llama.cpp OpenAI
server, checks explicit ground-truth criteria, and can log metrics plus the
server config artifact to MLflow.

Examples:
    uv run python -m evals.acceptance --case hitchhiker --mlflow
    uv run python -m evals.acceptance --all --model qwen3.5-0.8b-text --mlflow
"""

from __future__ import annotations

import argparse
import io
import json
import os
import time
from contextlib import redirect_stderr
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

os.environ["SLM_TRACE"] = "1"


@dataclass(frozen=True)
class AcceptanceCase:
    id: str
    prompt: str
    ground_truth: str
    required_any: tuple[tuple[str, ...], ...]
    required_all: tuple[str, ...] = ()
    expected_trace_any: tuple[str, ...] = ()
    max_latency_ms: float = 180_000.0
    notes: str = ""


@dataclass(frozen=True)
class AcceptanceResult:
    case: AcceptanceCase
    answer: str
    trace_lines: list[str]
    elapsed_ms: float
    passed: bool
    failures: list[str] = field(default_factory=list)


CASES: tuple[AcceptanceCase, ...] = (
    AcceptanceCase(
        id="python_creator",
        prompt="Who created the Python programming language and when was it first released?",
        ground_truth=(
            "Python was created by Guido van Rossum. Development began in the late 1980s "
            "and Python 0.9.0 was first released in 1991."
        ),
        required_any=(
            ("guido", "rossum"),
            ("1991", "1989", "1990"),
        ),
        expected_trace_any=("question_answering",),
        notes="Well-known authorship fact; SLMs reliably know this without retrieval.",
    ),
    AcceptanceCase(
        id="ml_pt",
        prompt="O que é machine learning e como ele funciona?",
        ground_truth=(
            "Machine learning é um subcampo da inteligência artificial onde sistemas "
            "aprendem padrões a partir de dados sem serem explicitamente programados. "
            "A resposta deve mencionar dados, modelos ou treinamento."
        ),
        required_any=(
            ("aprendizado", "machine learning", "aprender"),
            ("dados", "data", "modelo", "treinamento"),
        ),
        expected_trace_any=("question_answering",),
        notes="Portuguese-language query; tests multilingual grounding.",
    ),
    AcceptanceCase(
        id="binary_search_complexity",
        prompt="What is the time complexity of binary search and why?",
        ground_truth=(
            "Binary search has O(log n) time complexity because it halves the search "
            "space at each step, requiring at most log₂(n) comparisons."
        ),
        required_any=(
            ("log", "o(log", "logarithm"),
            ("halv", "divid", "split", "middle"),
        ),
        expected_trace_any=("question_answering", "agent"),
        notes="Algorithmic reasoning; SLMs know this reliably. Tests structured technical output.",
    ),
    AcceptanceCase(
        id="hitchhiker",
        prompt="which is the movie which says that the meaning of life is 42?",
        ground_truth=(
            "The answer should identify The Hitchhiker's Guide to the Galaxy. "
            "The number 42 is a running joke/answer to the ultimate question in that work; "
            "a film adaptation exists."
        ),
        required_any=(("hitchhiker",),),
        expected_trace_any=("web_search", "wikipedia"),
        notes="Ambiguous cultural clue; must be solved by retrieval/title "
        "resolution, not a hardcoded branch.",
    ),
    AcceptanceCase(
        id="gba_pokemon_first",
        prompt="which pokemon game of gameboy advance should I play first?",
        ground_truth=(
            "Mainline Pokémon games on Game Boy Advance include Ruby/Sapphire, FireRed/LeafGreen, "
            "and Emerald. For a first GBA Pokémon game, FireRed or LeafGreen are strong beginner "
            "recommendations because they remake the original Kanto games and are approachable; "
            "Emerald is often recommended after that as the most complete Hoenn version."
        ),
        required_any=(("firered", "fire red", "leafgreen", "leaf green", "emerald"),),
        expected_trace_any=("web_search", "wikipedia", "question_answering"),
        notes="Recommendation prompt should ground itself in known GBA "
        "titles and explain the first-play rationale.",
    ),
    AcceptanceCase(
        id="solid",
        prompt="explain me S.O.L.I.D principles one by one",
        ground_truth=(
            "SOLID is five object-oriented design principles: Single "
            "Responsibility, Open/Closed, Liskov Substitution, Interface "
            "Segregation, and Dependency Inversion. The answer should "
            "explain each principle separately."
        ),
        required_any=(
            ("single responsibility",),
            ("open/closed", "open closed", "open-closed"),
            ("liskov",),
            ("interface segregation",),
            ("dependency inversion",),
        ),
        expected_trace_any=("question_answering",),
        notes="Structured technical explanation; no network is required but "
        "all five principles must be present.",
    ),
)

CASE_BY_ID = {case.id: case for case in CASES}


def _capture_run(fn: Callable[[], str]) -> tuple[str, list[str], float]:
    buf = io.StringIO()
    started = time.perf_counter()
    with redirect_stderr(buf):
        answer = fn()
    elapsed_ms = (time.perf_counter() - started) * 1000
    return answer, [line for line in buf.getvalue().splitlines() if line.strip()], elapsed_ms


def _contains_any(answer: str, variants: tuple[str, ...]) -> bool:
    lower = answer.lower()
    return any(variant.lower() in lower for variant in variants)


def _evaluate(
    case: AcceptanceCase, answer: str, trace_lines: list[str], elapsed_ms: float
) -> AcceptanceResult:
    failures: list[str] = []
    lower_answer = answer.lower()
    joined_trace = " ".join(trace_lines).lower()

    for variants in case.required_any:
        if not _contains_any(answer, variants):
            failures.append(f"missing one of: {', '.join(variants)}")

    for term in case.required_all:
        if term.lower() not in lower_answer:
            failures.append(f"missing required term: {term}")

    if case.expected_trace_any and not any(
        t.lower() in joined_trace for t in case.expected_trace_any
    ):
        failures.append(f"trace missing one of: {', '.join(case.expected_trace_any)}")

    if elapsed_ms > case.max_latency_ms:
        failures.append(f"latency {elapsed_ms:.0f}ms exceeded {case.max_latency_ms:.0f}ms")

    return AcceptanceResult(case, answer, trace_lines, elapsed_ms, not failures, failures)


def _run_case(case: AcceptanceCase) -> AcceptanceResult:
    from src.context import extract_text
    from src.main import run
    from src.providers.openai_local import OpenAILocalClient

    answer, trace, elapsed = _capture_run(
        lambda: extract_text(run(case.prompt, OpenAILocalClient()))
    )
    return _evaluate(case, answer, trace, elapsed)


def _configure_models(args: argparse.Namespace) -> None:
    from src.model_registry import apply_model_overrides, ensure_model_available

    role_models = {
        "router": args.router_model,
        "question_answering": args.qa_model,
        "summarization": args.summarization_model,
        "classification": args.classification_model,
        "function_calling": args.function_model,
        "agent": args.agent_model,
    }
    for model in {m for m in [args.model, *role_models.values()] if m}:
        ensure_model_available(model, auto_download=not args.no_model_download)
    apply_model_overrides(default_model=args.model, role_models=role_models)


def _print_result(result: AcceptanceResult, *, verbose: bool) -> None:
    status = "PASS" if result.passed else "FAIL"
    print(f"[{status}] {result.case.id}  {result.elapsed_ms:.0f}ms")
    print(f"  prompt: {result.case.prompt}")
    print(f"  ground truth: {result.case.ground_truth}")
    print(f"  trace: {' | '.join(result.trace_lines) or '(none)'}")
    if result.failures:
        print(f"  failures: {result.failures}")
    if verbose or not result.passed:
        print(f"  answer: {result.answer}")
    print()


def _log_to_mlflow(results: list[AcceptanceResult], args: argparse.Namespace) -> str:
    import mlflow

    tracking_dir = Path(__file__).parent.parent / "mlruns"
    mlflow.set_tracking_uri(str(tracking_dir))
    mlflow.set_experiment("slms_acceptance")

    with mlflow.start_run(
        run_name=f"acceptance_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    ) as run:
        mlflow.log_params(
            {
                "model.default": args.model or "registry",
                "model.router": args.router_model or "registry",
                "model.qa": args.qa_model or "registry",
                "cases": ",".join(r.case.id for r in results),
            }
        )
        total = len(results)
        passed = sum(1 for r in results if r.passed)
        mlflow.log_metrics(
            {
                "acceptance.pass_rate": passed / total if total else 0.0,
                "acceptance.pass_count": float(passed),
                "acceptance.avg_latency_ms": (
                    sum(r.elapsed_ms for r in results) / total if total else 0.0
                ),
            }
        )
        for result in results:
            prefix = f"case.{result.case.id}"
            mlflow.log_metrics(
                {
                    f"{prefix}.passed": 1.0 if result.passed else 0.0,
                    f"{prefix}.latency_ms": result.elapsed_ms,
                }
            )
        config_path = Path(args.server_config)
        if config_path.exists():
            mlflow.log_artifact(str(config_path), artifact_path="llama_cpp_server_config")
        mlflow.log_text(
            json.dumps(
                [
                    {
                        "id": r.case.id,
                        "prompt": r.case.prompt,
                        "ground_truth": r.case.ground_truth,
                        "answer": r.answer,
                        "trace": r.trace_lines,
                        "passed": r.passed,
                        "failures": r.failures,
                        "elapsed_ms": r.elapsed_ms,
                    }
                    for r in results
                ],
                indent=2,
            ),
            "acceptance_results.json",
        )
        return run.info.run_id


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run complex SLM acceptance tests one case at a time"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--case", choices=sorted(CASE_BY_ID), help="Single acceptance case to run")
    group.add_argument("--all", action="store_true", help="Run all cases sequentially")
    parser.add_argument(
        "--model", help="Override all text specialist roles with a llama.cpp model alias"
    )
    parser.add_argument("--router-model", help="Override only the router model")
    parser.add_argument("--qa-model", help="Override only the QA model")
    parser.add_argument("--summarization-model", help="Override only summarization model")
    parser.add_argument("--classification-model", help="Override only classification model")
    parser.add_argument("--function-model", help="Override only function-calling model")
    parser.add_argument("--agent-model", help="Override only agent model")
    parser.add_argument("--no-model-download", action="store_true")
    parser.add_argument("--server-config", default="server_config.json")
    parser.add_argument("--mlflow", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    _configure_models(args)
    cases = list(CASES if args.all else (CASE_BY_ID[args.case],))
    results = []
    for case in cases:
        result = _run_case(case)
        results.append(result)
        _print_result(result, verbose=args.verbose)
    if args.mlflow:
        print(f"MLflow run: {_log_to_mlflow(results, args)}")
    if not all(r.passed for r in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
