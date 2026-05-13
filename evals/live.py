"""
Live evaluation benchmark: complex prompts, both languages, all paths.

Runs every test with full trace capture, scores outputs, and prints a
structured report so you can see exactly which component decided what
and whether the result was good.

Usage:
    uv run python -m evals.live                    # all groups
    uv run python -m evals.live routing            # one group only
    uv run python -m evals.live --model alias --mlflow
"""

from __future__ import annotations

import argparse
import io
import os
import time
from contextlib import redirect_stderr
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

# Force trace on for the entire run
os.environ["SLM_TRACE"] = "1"

from src.techniques.scoring import score_result  # noqa: E402

# ---------------------------------------------------------------------------
# Test case types
# ---------------------------------------------------------------------------

RESET = "\033[0m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
CYAN = "\033[36m"
BOLD = "\033[1m"
DIM = "\033[2m"


@dataclass
class Case:
    id: str
    prompt: str
    lang: str  # en / pt
    expect_path: str  # intent or tool name expected in trace
    expect_in_answer: list[str] = field(default_factory=list)  # key terms answer must contain
    note: str = ""  # what this case is testing


@dataclass
class Result:
    case: Case
    answer: str
    trace_lines: list[str]
    elapsed_ms: float
    quality: float
    is_usable: bool
    quality_reason: str
    path_confirmed: bool  # expected_path found in trace

    def verdict(self) -> str:
        if not self.is_usable:
            return f"{RED}FAIL{RESET}"
        if not self.path_confirmed:
            return f"{YELLOW}WARN{RESET}"
        return f"{GREEN}PASS{RESET}"


# ---------------------------------------------------------------------------
# Test cases organised by group
# ---------------------------------------------------------------------------

ROUTING_CASES: list[Case] = [
    Case(
        "R01",
        "summarize this text for me",
        "en",
        "summarization",
        note="clear summarization intent",
    ),
    Case(
        "R02",
        "tl;dr this article about climate change",
        "en",
        "summarization",
        note="abbreviated style",
    ),
    Case(
        "R03",
        "what is the capital of Japan?",
        "en",
        "question_answering",
        note="classic factual QA",
    ),
    Case(
        "R04",
        "calculate 144 divided by 12",
        "en",
        "function_calling",
        note="math → deterministic calculator",
    ),
    Case(
        "R05",
        "search for open source AI models",
        "en",
        "function_calling",
        note="explicit search intent",
    ),
    Case(
        "R06",
        "classify this review as positive or negative",
        "en",
        "classification",
        note="clear classification intent",
    ),
    Case("R07", "hello, how are you?", "en", "general", note="greeting → general"),
    # Portuguese
    Case("R08", "qual é a capital do Japão?", "pt", "question_answering", note="factual QA in PT"),
    Case("R09", "resume este artigo para mim", "pt", "summarization", note="summarization in PT"),
    Case("R10", "calcule 144 dividido por 12", "pt", "function_calling", note="math in PT"),
    Case(
        "R11",
        "quem é Linus Torvalds?",
        "pt",
        "question_answering",
        note="entity QA in PT — was misrouted before fix",
    ),
    Case(
        "R12",
        "me fale sobre o Rio de Janeiro",
        "pt",
        "question_answering",
        note="PT entity lookup — needed verb fix",
    ),
    # Edge cases
    Case(
        "R13",
        "what is the best way to learn Python?",
        "en",
        "question_answering",
        note="ambiguous: could be QA or function_calling",
    ),
    Case(
        "R14",
        "I need help understanding machine learning",
        "en",
        "question_answering",
        note="indirect phrasing",
    ),
]

NER_TOOL_CASES: list[Case] = [
    Case(
        "N01",
        "Tell me about OpenAI",
        "en",
        "wikipedia",
        expect_in_answer=["OpenAI", "AI", "artificial"],
        note="ORG entity → wikipedia lookup",
    ),
    Case(
        "N02",
        "Who is Linus Torvalds?",
        "en",
        "wikipedia",
        expect_in_answer=["Linux", "Torvalds"],
        note="PER entity → wikipedia lookup",
    ),
    Case(
        "N03",
        "Where is the Amazon rainforest?",
        "en",
        "wikipedia",
        expect_in_answer=["Amazon", "South America"],
        note="LOC entity → wikipedia lookup",
    ),
    Case(
        "N04",
        "What are the latest news about OpenAI?",
        "en",
        "web_search",
        expect_in_answer=["OpenAI"],
        note="ORG + temporal → web_search",
    ),
    Case(
        "N05",
        "O que é a Petrobras?",
        "pt",
        "wikipedia",
        expect_in_answer=["Petrobras", "petróleo", "Brazil"],
        note="PT ORG → wikipedia",
    ),
    Case(
        "N06",
        "Me fale sobre o Rio de Janeiro",
        "pt",
        "wikipedia",
        expect_in_answer=["Rio de Janeiro"],
        note="PT LOC → wikipedia",
    ),
    Case(
        "N07",
        "Quem foi Alan Turing?",
        "pt",
        "wikipedia",
        expect_in_answer=["Turing", "computação", "computer"],
        note="PT PER → wikipedia",
    ),
    Case(
        "N08",
        "Tell me about the Python programming language",
        "en",
        "wikipedia",
        expect_in_answer=["Python", "programming"],
        note="MISC entity — Python is ambiguous (snake vs lang)",
    ),
    Case(
        "N09",
        "What is spaCy?",
        "en",
        "wikipedia",
        expect_in_answer=["spaCy", "NLP", "natural"],
        note="MISC/ORG tech entity",
    ),
]

WORKFLOW_CASES: list[Case] = [
    Case(
        "W01",
        "quantum computing",
        "en",
        "web_search",
        expect_in_answer=["quantum"],
        note="research_and_summarize: search → summarize",
    ),
    Case(
        "W02",
        "Guido van Rossum",
        "en",
        "wikipedia",
        expect_in_answer=["Guido", "Python"],
        note="wiki_and_answer: wikipedia → answer",
    ),
    Case(
        "W03",
        "GPT-4 release",
        "en",
        "web_search",
        expect_in_answer=["GPT"],
        note="research_and_classify: search → classify",
    ),
    Case(
        "W04",
        "Python programming language",
        "en",
        "wikipedia",
        expect_in_answer=["Python"],
        note="wiki_and_answer: Python topic",
    ),
]

REFERENCE_CASES: list[Case] = [
    Case(
        "X01",
        "what is that movie that says the meaning of life is 42?",
        "en",
        "web_search",
        expect_in_answer=["Hitchhiker", "Galaxy"],
        note="ambiguous clue → generic web search/title resolution, no hardcoded answer",
    ),
]

AGENT_CASES: list[Case] = [
    Case(
        "A01",
        "search for llama.cpp and tell me what it is",
        "en",
        "web_search",
        expect_in_answer=["llama", "inference"],
        note="search → answer — baseline agent task",
    ),
    Case(
        "A02",
        "what is the square root of 256?",
        "en",
        "calculator",
        expect_in_answer=["16"],
        note="calculator → final_answer",
    ),
    Case(
        "A03",
        "calculate 7 times 8 and tell me if the result is even or odd",
        "en",
        "calculator",
        expect_in_answer=["56"],
        note="calculator then reasoning",
    ),
    Case(
        "A04",
        "pesquise sobre o framework FastAPI",
        "pt",
        "web_search",
        expect_in_answer=["FastAPI"],
        note="PT search agent",
    ),
]

ALL_GROUPS: dict[str, list[Case]] = {
    "routing": ROUTING_CASES,
    "ner_tool": NER_TOOL_CASES,
    "workflow": WORKFLOW_CASES,
    "reference": REFERENCE_CASES,
    "agent": AGENT_CASES,
}


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def _capture_run(fn: Callable[[], str]) -> tuple[str, list[str], float]:
    """Call fn(), capture stderr trace lines and elapsed ms."""
    buf = io.StringIO()
    t0 = time.perf_counter()
    with redirect_stderr(buf):
        answer = fn()
    elapsed = (time.perf_counter() - t0) * 1000
    traces = [line for line in buf.getvalue().splitlines() if line.strip()]
    return answer, traces, elapsed


def _run_direct(prompt: str) -> str:
    from src.main import run
    from src.providers.openai_local import OpenAILocalClient

    result = run(prompt, OpenAILocalClient())
    from src.context import extract_text

    return extract_text(result)


def _run_workflow(name: str, prompt: str) -> str:
    from src import trace as trace_module
    from src.context import extract_text
    from src.providers.openai_local import OpenAILocalClient
    from src.workflow import WORKFLOW_REGISTRY, run_workflow

    trace_module.init()
    wf = WORKFLOW_REGISTRY[name]
    result = run_workflow(wf, prompt, OpenAILocalClient())
    return extract_text(result)


def _run_agent(prompt: str) -> str:
    from src import trace as trace_module
    from src.agent import run_agent
    from src.context import extract_text
    from src.providers.openai_local import OpenAILocalClient

    trace_module.init()
    result = run_agent(prompt, OpenAILocalClient())
    return extract_text(result)


def _path_in_trace(expected: str, traces: list[str]) -> bool:
    joined = " ".join(traces).lower()
    return expected.lower() in joined


def _terms_in_answer(terms: list[str], answer: str) -> tuple[int, int]:
    found = sum(1 for t in terms if t.lower() in answer.lower())
    return found, len(terms)


# ---------------------------------------------------------------------------
# Group runners
# ---------------------------------------------------------------------------


def run_routing(cases: list[Case]) -> list[Result]:
    results = []
    for c in cases:

        def run_case(prompt: str = c.prompt) -> str:
            return _run_direct(prompt)

        answer, traces, elapsed = _capture_run(run_case)
        sc = score_result(answer)
        path_ok = _path_in_trace(c.expect_path, traces)
        results.append(
            Result(
                case=c,
                answer=answer,
                trace_lines=traces,
                elapsed_ms=elapsed,
                quality=sc.quality,
                is_usable=sc.is_usable,
                quality_reason=sc.reason,
                path_confirmed=path_ok,
            )
        )
    return results


def run_ner_tool(cases: list[Case]) -> list[Result]:
    # NER tool cases go through direct handler for function_calling intent
    return run_routing(cases)  # same pipeline — intent is routed naturally


def run_workflow_group(cases: list[Case]) -> list[Result]:
    wf_map = {
        "W01": "research_and_summarize",
        "W02": "wiki_and_answer",
        "W03": "research_and_classify",
        "W04": "wiki_and_answer",
    }
    results = []
    for c in cases:
        wf_name = wf_map.get(c.id, "research_and_summarize")

        def run_case(prompt: str = c.prompt, workflow_name: str = wf_name) -> str:
            return _run_workflow(workflow_name, prompt)

        answer, traces, elapsed = _capture_run(run_case)
        sc = score_result(answer)
        path_ok = _path_in_trace(c.expect_path, traces)
        results.append(
            Result(
                case=c,
                answer=answer,
                trace_lines=traces,
                elapsed_ms=elapsed,
                quality=sc.quality,
                is_usable=sc.is_usable,
                quality_reason=sc.reason,
                path_confirmed=path_ok,
            )
        )
    return results


def run_agent_group(cases: list[Case]) -> list[Result]:
    results = []
    for c in cases:

        def run_case(prompt: str = c.prompt) -> str:
            return _run_agent(prompt)

        answer, traces, elapsed = _capture_run(run_case)
        sc = score_result(answer)
        path_ok = _path_in_trace(c.expect_path, traces)
        results.append(
            Result(
                case=c,
                answer=answer,
                trace_lines=traces,
                elapsed_ms=elapsed,
                quality=sc.quality,
                is_usable=sc.is_usable,
                quality_reason=sc.reason,
                path_confirmed=path_ok,
            )
        )
    return results


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

_TRACE_KEYS = (
    "route",
    "ner",
    "retrieval",
    "tool.call",
    "tool.result",
    "agent.step",
    "workflow.step",
    "agent.final",
    "handler",
    "llm.request",
    "llm.response",
    "grounding.check",
    "grounding.result",
    "plan.step",
    "composition",
    "dag.exec",
    "dag.skip",
    "fast_path",
)


def _summarise_trace(traces: list[str]) -> str:
    """Compact one-line summary of what happened (path taken)."""
    seen = []
    for line in traces:
        for key in _TRACE_KEYS:
            if f"[trace] {key}" in line:
                # Extract first value after the key
                rest = line.split(key, 1)[1].strip()
                # Pick the most informative token
                token = rest.split()[0] if rest else ""
                label = f"{key}({token})" if token else key
                if label not in seen:
                    seen.append(label)
    return " → ".join(seen) if seen else "(no trace)"


def _print_result(r: Result, verbose: bool = False) -> None:
    verdict = r.verdict()
    found, total = _terms_in_answer(r.case.expect_in_answer, r.answer)
    term_ok = f"{found}/{total}" if total else "—"
    path_icon = "✓" if r.path_confirmed else "?"
    q_color = GREEN if r.quality >= 0.6 else (YELLOW if r.quality >= 0.3 else RED)

    print(
        f"  {verdict} [{r.case.id}] {r.case.prompt[:55]:<55} "
        f"{q_color}q={r.quality:.2f}{RESET}  terms={term_ok}  "
        f"path={path_icon}  {r.elapsed_ms:>6.0f}ms"
    )
    print(f"         {DIM}{r.case.note}{RESET}")
    print(f"         path: {DIM}{_summarise_trace(r.trace_lines)}{RESET}")
    if verbose or not r.is_usable or not r.path_confirmed:
        short = r.answer[:200].replace("\n", " ")
        print(f"         ans:  {short}")
    print()


def _group_stats(results: list[Result]) -> tuple[int, int, int, float]:
    """Returns (pass, warn, fail, avg_ms)."""
    verdicts = [r.verdict() for r in results]
    p = sum(1 for v in verdicts if "PASS" in v)
    w = sum(1 for v in verdicts if "WARN" in v)
    f = sum(1 for v in verdicts if "FAIL" in v)
    avg = sum(r.elapsed_ms for r in results) / len(results) if results else 0
    return p, w, f, avg


def _attribution_table(all_results: dict[str, list[Result]]) -> None:
    print(f"\n{BOLD}{'─'*60}")
    print("ATTRIBUTION: which technique drove each result")
    print(f"{'─'*60}{RESET}")

    technique_hits: dict[str, int] = {
        "TF-IDF router (fast path)": 0,
        "LLM router (fallback)": 0,
        "Math regex": 0,
        "Regex tool pattern": 0,
        "NER entity dispatch": 0,
        "LLM tool decision": 0,
        "Result quality scorer": 0,
        "Fuzzy workflow match": 0,
    }
    total = 0

    for results in all_results.values():
        for r in results:
            total += 1
            joined = " ".join(r.trace_lines)
            if "reason='ml'" in joined:
                technique_hits["TF-IDF router (fast path)"] += 1
            if "reason='llm'" in joined:
                technique_hits["LLM router (fallback)"] += 1
            if "fast_path kind='math_regex'" in joined:
                technique_hits["Math regex"] += 1
            if "fast_path kind='regex_tool'" in joined:
                technique_hits["Regex tool pattern"] += 1
            if "fast_path kind='ner_entity'" in joined or "[trace] ner" in joined:
                technique_hits["NER entity dispatch"] += 1
            if "low quality result" in joined:
                technique_hits["Result quality scorer"] += 1

    print(f"  {'Technique':<35} {'Queries':<10} {'Coverage'}")
    print(f"  {'─'*35} {'─'*10} {'─'*10}")
    for name, hits in technique_hits.items():
        bar = "█" * int(hits / max(total, 1) * 20)
        print(f"  {name:<35} {hits:<10} {bar} {hits/total*100:.0f}%")
    print(f"\n  Total queries evaluated: {total}")


def _pitfalls_summary(all_results: dict[str, list[Result]]) -> None:
    print(f"\n{BOLD}{'─'*60}")
    print("PITFALLS & FINDINGS")
    print(f"{'─'*60}{RESET}")

    fails = [(g, r) for g, rs in all_results.items() for r in rs if "FAIL" in r.verdict()]
    warns = [(g, r) for g, rs in all_results.items() for r in rs if "WARN" in r.verdict()]

    if not fails and not warns:
        print(f"  {GREEN}No failures or warnings detected.{RESET}")
        return

    if fails:
        print(f"\n  {RED}FAILURES ({len(fails)}):{RESET}")
        for g, r in fails:
            print(f"    [{g}/{r.case.id}] {r.case.prompt[:60]}")
            print(f"      reason: {r.quality_reason}  quality={r.quality:.2f}")
            print(f"      note: {r.case.note}")
            print(f"      ans: {r.answer[:120]}")

    if warns:
        print(f"\n  {YELLOW}PATH MISMATCHES ({len(warns)}):{RESET}")
        for g, r in warns:
            found, _ = _terms_in_answer(r.case.expect_in_answer, r.answer)
            print(f"    [{g}/{r.case.id}] {r.case.prompt[:60]}")
            print(
                f"      expected path: {r.case.expect_path!r}  "
                f"terms found: {found}/{len(r.case.expect_in_answer)}"
            )
            print(f"      trace: {_summarise_trace(r.trace_lines)}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Live benchmark for the unified SLM harness")
    parser.add_argument(
        "group", nargs="?", choices=sorted(ALL_GROUPS), help="Optional group to run"
    )
    parser.add_argument("--model", help="Override all text specialist roles with a model alias")
    parser.add_argument("--router-model", help="Override only the router model")
    parser.add_argument("--qa-model", help="Override only the QA model")
    parser.add_argument("--summarization-model", help="Override only the summarization model")
    parser.add_argument("--classification-model", help="Override only the classification model")
    parser.add_argument("--function-model", help="Override only the tool-selection model")
    parser.add_argument("--agent-model", help="Override only the planner-agent model")
    parser.add_argument("--no-model-download", action="store_true")
    parser.add_argument(
        "--mlflow", action="store_true", help="Log aggregate live metrics to MLflow"
    )
    return parser


def _role_models(args: argparse.Namespace) -> dict[str, str | None]:
    return {
        "router": args.router_model,
        "question_answering": args.qa_model,
        "summarization": args.summarization_model,
        "classification": args.classification_model,
        "function_calling": args.function_model,
        "agent": args.agent_model,
    }


def _configure_models(args: argparse.Namespace) -> None:
    from src.model_registry import apply_model_overrides, ensure_model_available

    for model in {m for m in [args.model, *_role_models(args).values()] if m}:
        ensure_model_available(model, auto_download=not args.no_model_download)
    apply_model_overrides(default_model=args.model, role_models=_role_models(args))


def _log_live_to_mlflow(all_results: dict[str, list[Result]], args: argparse.Namespace) -> str:
    import mlflow

    mlflow.set_tracking_uri(str(Path(__file__).parent.parent / "mlruns"))
    mlflow.set_experiment("slms_live_evaluation")
    run_name = f"live_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    with mlflow.start_run(run_name=run_name) as run:
        params = {"model.default": args.model or "registry"}
        params.update({f"model.{k}": v for k, v in _role_models(args).items() if v})
        params["group"] = args.group or "all"
        mlflow.log_params(params)

        total_cases = 0
        total_pass = 0
        for group_name, results in all_results.items():
            passed, warned, failed, avg_ms = _group_stats(results)
            total = len(results)
            total_cases += total
            total_pass += passed
            prefix = f"live.{group_name}"
            mlflow.log_metrics(
                {
                    f"{prefix}.pass_rate": passed / total if total else 0.0,
                    f"{prefix}.warn_count": float(warned),
                    f"{prefix}.fail_count": float(failed),
                    f"{prefix}.avg_latency_ms": avg_ms,
                }
            )
        mlflow.log_metric(
            "live.overall.pass_rate", total_pass / total_cases if total_cases else 0.0
        )
        return run.info.run_id


def main() -> None:
    args = _build_parser().parse_args()
    group_filter = args.group
    _configure_models(args)

    runners: dict[str, tuple[list[Case], Callable[[list[Case]], list[Result]]]] = {
        "routing": (ROUTING_CASES, run_routing),
        "ner_tool": (NER_TOOL_CASES, run_ner_tool),
        "workflow": (WORKFLOW_CASES, run_workflow_group),
        "reference": (REFERENCE_CASES, run_routing),
        "agent": (AGENT_CASES, run_agent_group),
    }

    all_results: dict[str, list[Result]] = {}

    for group_name, (cases, runner) in runners.items():
        if group_filter and group_filter != group_name:
            continue

        print(f"\n{BOLD}{'═'*60}")
        print(f"  GROUP: {group_name.upper()}  ({len(cases)} cases)")
        print(f"{'═'*60}{RESET}\n")

        results = runner(cases)
        all_results[group_name] = results

        for r in results:
            _print_result(r)

        p, w, f, avg = _group_stats(results)
        total = len(results)
        print(
            f"  {BOLD}Summary:{RESET} "
            f"{GREEN}PASS={p}{RESET}  {YELLOW}WARN={w}{RESET}  {RED}FAIL={f}{RESET}  "
            f"avg={avg:.0f}ms  pass_rate={p/total*100:.0f}%"
        )

    if not group_filter:
        _attribution_table(all_results)
        _pitfalls_summary(all_results)

        total_p = sum(_group_stats(rs)[0] for rs in all_results.values())
        total_all = sum(len(rs) for rs in all_results.values())
        print(
            f"\n{BOLD}OVERALL: {total_p}/{total_all} passed "
            f"({total_p/total_all*100:.0f}%){RESET}\n"
        )

    if args.mlflow:
        run_id = _log_live_to_mlflow(all_results, args)
        print(f"{BOLD}MLflow run:{RESET} {run_id}")


if __name__ == "__main__":
    main()
