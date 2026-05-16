from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean
from typing import Any, Literal
from unittest.mock import MagicMock

from sklearn.metrics import confusion_matrix, f1_score, precision_recall_fscore_support

from src import main as main_module
from src.handlers import summarization
from src.lexical_scoring import combined_lexical_score
from src.retrievers.default import DefaultRetriever
from src.router import classify_ml
from src.schemas import FinalAnswer
from src.techniques.grounding import evaluate as evaluate_grounding_answer
from src.text_normalization import normalize_text
from src.tool_selection import deterministic_decision, rank_tool_candidates

_FIXTURES_DIR = Path(__file__).resolve().parent.parent / "tests" / "evals" / "fixtures"
_BASELINE_DIR = Path(__file__).resolve().parent.parent / "artifacts" / "evals"
_DEFAULT_SPLIT = "default"
_TOOL_TOP_K = 2

ROUTING_LABELS = [
    "summarization",
    "question_answering",
    "function_calling",
    "classification",
    "image_understanding",
    "general",
    "unclassified",
]
RETRIEVAL_STRATEGY_LABELS = [
    "url_fetch",
    "time_sensitive",
    "reference_lookup",
    "recommendation_lookup",
    "concept_lookup",
    "entity_lookup",
    "direct_what_is",
    "none",
]

DEFAULT_THRESHOLDS: dict[str, dict[str, float]] = {
    "routing": {"protected_accuracy_min": 1.0, "target_improvement_delta_min": 0.10},
    "tool_selection": {"protected_accuracy_min": 1.0, "target_improvement_delta_min": 0.10},
    "retrieval_strategy": {
        "protected_accuracy_min": 1.0,
        "target_improvement_delta_min": 0.10,
    },
    "follow_up_detection": {
        "protected_accuracy_min": 1.0,
        "target_improvement_delta_min": 0.10,
        "false_link_rate_max": 0.0,
    },
    "summarization_guard": {
        "protected_accuracy_min": 1.0,
        "valid_short_input_rejection_rate_max": 0.0,
    },
    "grounding": {
        "protected_accuracy_min": 1.0,
        "target_improvement_delta_min": 0.10,
        "unsupported_claim_recall_min": 0.80,
    },
    "summarization_answer_quality": {
        "protected_accuracy_min": 1.0,
        "required_concept_coverage_min": 0.80,
    },
}


@dataclass
class CaseResult:
    case_id: str
    cohort: str
    dataset_split: str
    expected: Any
    actual: Any
    passed: bool
    details: dict[str, Any]


@dataclass
class CapabilitySection:
    name: str
    evaluation_level: Literal["decision", "answer"]
    metrics: dict[str, Any]
    cases: list[CaseResult]
    automation_gaps: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "evaluation_level": self.evaluation_level,
            "metrics": self.metrics,
            "cases": [asdict(case) for case in self.cases],
            "automation_gaps": self.automation_gaps,
        }


class _RecordingRetriever(DefaultRetriever):
    strategy: str = "none"
    force_empty_entity: bool = False

    def _fetch_time_sensitive(self, user_input: str) -> str:
        self.strategy = "time_sensitive"
        return "context"

    def _fetch_reference(self, user_input: str) -> str:
        self.strategy = "reference_lookup"
        return "context"

    def _fetch_recommendation(self, user_input: str) -> str:
        self.strategy = "recommendation_lookup"
        return "context"

    def _fetch_concept(self, user_input: str) -> str:
        self.strategy = "concept_lookup"
        return "context"

    def _fetch_entity(self, user_input: str) -> str:
        if self.force_empty_entity or user_input == "__force_empty_entity__":
            return ""
        self.strategy = "entity_lookup"
        return "context"

    def _fetch_wikipedia(self, query: str, user_input: str) -> str:
        self.strategy = "direct_what_is"
        return "context"


def _fixture_root(dataset_version: str) -> Path:
    return _FIXTURES_DIR / dataset_version


def _available_splits(dataset_version: str) -> list[str]:
    root = _fixture_root(dataset_version)
    dev_dir = root / "dev"
    heldout_dir = root / "heldout"
    if dev_dir.exists() or heldout_dir.exists():
        splits = [name for name in ("dev", "heldout") if (root / name).exists()]
        return splits or ["dev"]
    return [_DEFAULT_SPLIT]


def _resolve_splits(dataset_version: str, split: str) -> list[str]:
    available = _available_splits(dataset_version)
    if split == "all":
        return available
    if split == _DEFAULT_SPLIT and available == [_DEFAULT_SPLIT]:
        return available
    if split not in available:
        raise ValueError(
            f"Unknown split {split!r} for dataset {dataset_version!r}. Available: {available}"
        )
    return [split]


def _load_cases(dataset_version: str, split: str, name: str) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    root = _fixture_root(dataset_version)
    for active_split in _resolve_splits(dataset_version, split):
        base_dir = root if active_split == _DEFAULT_SPLIT else root / active_split
        fixture_path = base_dir / f"{name}.json"
        if not fixture_path.exists():
            continue
        payload = json.loads(fixture_path.read_text())
        for case in payload["cases"]:
            entry = dict(case)
            entry.setdefault("dataset_split", active_split)
            cases.append(entry)
    return cases


def _cohort_accuracy(cases: list[CaseResult], cohort: str) -> float:
    members = [case for case in cases if case.cohort == cohort]
    if not members:
        return 0.0
    return sum(1 for case in members if case.passed) / len(members)


def _split_accuracy(cases: list[CaseResult]) -> dict[str, float]:
    splits = sorted({case.dataset_split for case in cases})
    return {
        split: sum(1 for case in cases if case.dataset_split == split and case.passed)
        / max(1, sum(1 for case in cases if case.dataset_split == split))
        for split in splits
    }


def _mean_latency_ms(durations: list[float]) -> float:
    return round(mean(durations) * 1000, 3) if durations else 0.0


def _base_metrics(cases: list[CaseResult], durations: list[float]) -> dict[str, Any]:
    return {
        "case_count": len(cases),
        "split_accuracy": _split_accuracy(cases),
        "protected_accuracy": _cohort_accuracy(cases, "protected"),
        "target_improvement_accuracy": _cohort_accuracy(cases, "target_improvement"),
        "mean_case_latency_ms": _mean_latency_ms(durations),
    }


def _classification_metrics(
    cases: list[CaseResult],
    labels: list[str],
    durations: list[float],
    include_low_confidence_rate: bool = False,
) -> dict[str, Any]:
    y_true = [str(case.expected) for case in cases]
    y_pred = [str(case.actual) for case in cases]
    precision, recall, f1, support = precision_recall_fscore_support(
        y_true,
        y_pred,
        labels=labels,
        zero_division=0,
    )
    matrix = confusion_matrix(y_true, y_pred, labels=labels)
    metrics: dict[str, Any] = {
        **_base_metrics(cases, durations),
        "accuracy": sum(1 for case in cases if case.passed) / len(cases),
        "macro_f1": float(
            f1_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)
        ),
        "confusion_matrix": {
            row_label: {
                col_label: int(matrix[row_idx][col_idx]) for col_idx, col_label in enumerate(labels)
            }
            for row_idx, row_label in enumerate(labels)
        },
        "per_label": {
            label: {
                "precision": float(precision[idx]),
                "recall": float(recall[idx]),
                "f1": float(f1[idx]),
                "support": int(support[idx]),
            }
            for idx, label in enumerate(labels)
        },
    }
    if include_low_confidence_rate:
        metrics["low_confidence_fallback_rate"] = sum(
            1 for case in cases if case.details.get("below_threshold", False)
        ) / len(cases)
    return metrics


def _primary_metric(metrics: dict[str, Any]) -> float:
    for key in ("accuracy", "pass_fail_accuracy", "top_1_accuracy"):
        if key in metrics:
            return float(metrics[key])
    return 0.0


def _report_levels(capabilities: list[CapabilitySection]) -> dict[str, dict[str, Any]]:
    levels: dict[str, list[CapabilitySection]] = {"decision": [], "answer": []}
    for capability in capabilities:
        levels[capability.evaluation_level].append(capability)
    return {
        level: {
            "capabilities": [capability.name for capability in sections],
            "mean_accuracy": round(
                mean(_primary_metric(capability.metrics) for capability in sections), 4
            )
            if sections
            else 0.0,
        }
        for level, sections in levels.items()
    }


def evaluate_routing(dataset_version: str, split: str) -> CapabilitySection:
    cases: list[CaseResult] = []
    durations: list[float] = []
    for case in _load_cases(dataset_version, split, "routing"):
        started = time.perf_counter()
        classification = classify_ml(case["prompt"])
        durations.append(time.perf_counter() - started)
        actual = "below_threshold" if classification is None else classification.intent
        cases.append(
            CaseResult(
                case_id=case["id"],
                cohort=case["cohort"],
                dataset_split=case["dataset_split"],
                expected=case["expected_intent"],
                actual=actual,
                passed=actual == case["expected_intent"],
                details={
                    "prompt": case["prompt"],
                    "confidence": None if classification is None else classification.confidence,
                    "below_threshold": classification is None,
                },
            )
        )
    return CapabilitySection(
        name="routing",
        evaluation_level="decision",
        metrics=_classification_metrics(
            cases, ROUTING_LABELS + ["below_threshold"], durations, True
        ),
        cases=cases,
        automation_gaps=[],
    )


def evaluate_tool_selection(dataset_version: str, split: str) -> CapabilitySection:
    cases: list[CaseResult] = []
    durations: list[float] = []
    for case in _load_cases(dataset_version, split, "tool_selection"):
        tool_registry = MagicMock()
        tool_registry.__contains__.return_value = True
        started = time.perf_counter()
        ranked = rank_tool_candidates(case["prompt"], tool_registry)
        durations.append(time.perf_counter() - started)
        decision = deterministic_decision(case["prompt"], tool_registry)
        actual_tool = "none" if decision is None else decision.tool_name
        expected_tool = case["expected_tool"]
        passed = actual_tool == expected_tool
        arg_match = False
        if decision is not None and expected_tool != "none":
            key = case["expected_argument_key"]
            expected_substring = case["expected_argument_contains"]
            arg_match = expected_substring.lower() in str(decision.arguments.get(key, "")).lower()
            passed = passed and arg_match
        elif expected_tool == "none":
            arg_match = True

        ranked_names = [candidate.decision.tool_name for candidate in ranked]
        top_k_hit = expected_tool == "none" and not ranked_names
        if expected_tool != "none":
            top_k_hit = expected_tool in ranked_names[:_TOOL_TOP_K]
        cases.append(
            CaseResult(
                case_id=case["id"],
                cohort=case["cohort"],
                dataset_split=case["dataset_split"],
                expected=expected_tool,
                actual=actual_tool,
                passed=passed,
                details={
                    "prompt": case["prompt"],
                    "arguments": None if decision is None else decision.arguments,
                    "arg_match": arg_match,
                    "ranked_candidates": ranked_names,
                    "top_k_hit": top_k_hit,
                },
            )
        )
    total = len(cases)
    false_positive_rate = sum(
        1 for case in cases if case.expected == "none" and case.actual != "none"
    ) / max(1, sum(1 for case in cases if case.expected == "none"))
    false_negative_rate = sum(
        1 for case in cases if case.expected != "none" and case.actual == "none"
    ) / max(1, sum(1 for case in cases if case.expected != "none"))
    metrics = {
        **_base_metrics(cases, durations),
        "top_1_accuracy": sum(1 for case in cases if case.passed) / total,
        "top_k_accuracy": sum(1 for case in cases if case.details["top_k_hit"]) / total,
        "top_k": _TOOL_TOP_K,
        "ranked_candidates_available": True,
        "false_positive_rate": false_positive_rate,
        "false_negative_rate": false_negative_rate,
    }
    return CapabilitySection(
        name="tool_selection",
        evaluation_level="decision",
        metrics=metrics,
        cases=cases,
        automation_gaps=[],
    )


def evaluate_retrieval_strategy(dataset_version: str, split: str) -> CapabilitySection:
    cases: list[CaseResult] = []
    durations: list[float] = []
    for case in _load_cases(dataset_version, split, "retrieval_strategy"):
        web_fetch = MagicMock()
        web_fetch.execute.return_value = "page"
        retriever = _RecordingRetriever(
            web_fetch=web_fetch,
            web_search=MagicMock(),
            wikipedia=MagicMock(),
        )
        prompt = case["prompt"]
        if case.get("force_no_entity", False):
            retriever.force_empty_entity = True
        started = time.perf_counter()
        retriever.fetch_context(prompt)
        durations.append(time.perf_counter() - started)
        actual = "url_fetch" if web_fetch.execute.called else retriever.strategy
        cases.append(
            CaseResult(
                case_id=case["id"],
                cohort=case["cohort"],
                dataset_split=case["dataset_split"],
                expected=case["expected_strategy"],
                actual=actual,
                passed=actual == case["expected_strategy"],
                details={"prompt": prompt},
            )
        )
    precision, recall, f1, support = precision_recall_fscore_support(
        [str(case.expected) for case in cases],
        [str(case.actual) for case in cases],
        labels=RETRIEVAL_STRATEGY_LABELS,
        zero_division=0,
    )
    metrics = {
        **_base_metrics(cases, durations),
        "accuracy": sum(1 for case in cases if case.passed) / len(cases),
        "failure_to_recover_rate": sum(1 for case in cases if case.actual == "none") / len(cases),
        "per_strategy": {
            label: {
                "precision": float(precision[idx]),
                "recall": float(recall[idx]),
                "f1": float(f1[idx]),
                "support": int(support[idx]),
            }
            for idx, label in enumerate(RETRIEVAL_STRATEGY_LABELS)
        },
    }
    return CapabilitySection(
        name="retrieval_strategy",
        evaluation_level="decision",
        metrics=metrics,
        cases=cases,
        automation_gaps=[
            "Retrieval eval still measures strategy branch selection more directly than downstream answer quality."
        ],
    )


def evaluate_follow_up_detection(dataset_version: str, split: str) -> CapabilitySection:
    cases: list[CaseResult] = []
    durations: list[float] = []
    for case in _load_cases(dataset_version, split, "follow_up_detection"):
        turns = [(turn["user"], turn["assistant"]) for turn in case["turns"]]
        started = time.perf_counter()
        context = main_module._conversation_context(case["prompt"], turns)
        durations.append(time.perf_counter() - started)
        actual = context is not None
        expected = bool(case["expected_use_context"])
        cases.append(
            CaseResult(
                case_id=case["id"],
                cohort=case["cohort"],
                dataset_split=case["dataset_split"],
                expected=expected,
                actual=actual,
                passed=actual == expected,
                details={
                    "prompt": case["prompt"],
                    "turn_count": len(turns),
                    "context": context,
                },
            )
        )
    y_true = [bool(case.expected) for case in cases]
    y_pred = [bool(case.actual) for case in cases]
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_true,
        y_pred,
        labels=[True, False],
        zero_division=0,
    )
    negative_cases = [case for case in cases if case.expected is False]
    false_link_rate = sum(1 for case in negative_cases if case.actual is True) / max(
        1, len(negative_cases)
    )
    metrics = {
        **_base_metrics(cases, durations),
        "accuracy": sum(1 for case in cases if case.passed) / len(cases),
        "precision": float(precision[0]),
        "recall": float(recall[0]),
        "f1": float(f1[0]),
        "false_link_rate": false_link_rate,
    }
    return CapabilitySection(
        name="follow_up_detection",
        evaluation_level="decision",
        metrics=metrics,
        cases=cases,
        automation_gaps=[],
    )


def evaluate_summarization_guard(dataset_version: str, split: str) -> CapabilitySection:
    cases: list[CaseResult] = []
    durations: list[float] = []
    for case in _load_cases(dataset_version, split, "summarization_guard"):
        started = time.perf_counter()
        result = summarization.handle(case["prompt"], MagicMock())
        durations.append(time.perf_counter() - started)
        actual_blocked = (
            isinstance(result, FinalAnswer) and result.answer == "No text provided to summarize."
        )
        expected_blocked = bool(case["expected_blocked"])
        cases.append(
            CaseResult(
                case_id=case["id"],
                cohort=case["cohort"],
                dataset_split=case["dataset_split"],
                expected=expected_blocked,
                actual=actual_blocked,
                passed=actual_blocked == expected_blocked,
                details={"prompt": case["prompt"]},
            )
        )
    valid_short_cases = [
        case for case in cases if case.cohort == "target_improvement" and case.expected is False
    ]
    metrics = {
        **_base_metrics(cases, durations),
        "accuracy": sum(1 for case in cases if case.passed) / len(cases),
        "valid_short_input_rejection_rate": sum(
            1 for case in valid_short_cases if case.actual is True
        )
        / max(1, len(valid_short_cases)),
    }
    return CapabilitySection(
        name="summarization_guard",
        evaluation_level="decision",
        metrics=metrics,
        cases=cases,
        automation_gaps=[],
    )


def _detect_unsupported_claim(result_issues: list[str]) -> bool:
    return any(
        issue.startswith("faithfulness") or issue.startswith("numeric mismatch")
        for issue in result_issues
    )


def evaluate_grounding(dataset_version: str, split: str) -> CapabilitySection:
    cases: list[CaseResult] = []
    durations: list[float] = []
    unsupported_truth: list[bool] = []
    unsupported_pred: list[bool] = []
    real_generated_case_count = 0
    for case in _load_cases(dataset_version, split, "grounding"):
        started = time.perf_counter()
        result = evaluate_grounding_answer(case["answer"], case["context"])
        durations.append(time.perf_counter() - started)
        actual_passed = result.route == "accept"
        expected_passed = bool(case["expected_passed"])
        predicted_unsupported = _detect_unsupported_claim(result.issues)
        unsupported_truth.append(bool(case["expected_unsupported_claim_detected"]))
        unsupported_pred.append(predicted_unsupported)
        if case.get("source_kind") == "captured_model_output":
            real_generated_case_count += 1
        cases.append(
            CaseResult(
                case_id=case["id"],
                cohort=case["cohort"],
                dataset_split=case["dataset_split"],
                expected=expected_passed,
                actual=actual_passed,
                passed=actual_passed == expected_passed,
                details={
                    "route": result.route,
                    "score": result.score,
                    "issues": result.issues,
                    "predicted_unsupported_claim_detected": predicted_unsupported,
                    "source_kind": case.get("source_kind", "synthetic"),
                },
            )
        )
    precision, recall, f1, _ = precision_recall_fscore_support(
        unsupported_truth,
        unsupported_pred,
        labels=[True, False],
        zero_division=0,
    )
    metrics = {
        **_base_metrics(cases, durations),
        "pass_fail_accuracy": sum(1 for case in cases if case.passed) / len(cases),
        "unsupported_claim_precision": float(precision[0]),
        "unsupported_claim_recall": float(recall[0]),
        "unsupported_claim_f1": float(f1[0]),
        "mean_score": mean([float(case.details["score"]) for case in cases]),
        "real_generated_case_count": real_generated_case_count,
    }
    return CapabilitySection(
        name="grounding",
        evaluation_level="answer",
        metrics=metrics,
        cases=cases,
        automation_gaps=[
            "Grounding now includes captured model outputs, but labels remain human-reviewed fixtures rather than fully live end-to-end scoring."
        ],
    )


def _normalized_contains(text: str, phrase: str) -> bool:
    normalized_text = normalize_text(text, strip_punctuation=True)
    normalized_phrase = normalize_text(phrase, strip_punctuation=True)
    return normalized_phrase in normalized_text


def _concept_covered(output_text: str, concept: str) -> bool:
    if _normalized_contains(output_text, concept):
        return True
    return combined_lexical_score(output_text, concept).score >= 0.55


def evaluate_summarization_answer_quality(
    dataset_version: str, split: str
) -> CapabilitySection | None:
    raw_cases = _load_cases(dataset_version, split, "summarization_answer_quality")
    if not raw_cases:
        return None
    cases: list[CaseResult] = []
    durations: list[float] = []
    coverage_scores: list[float] = []
    for case in raw_cases:
        started = time.perf_counter()
        output_text = " ".join(
            [case.get("title", ""), case.get("summary", ""), *case.get("key_points", [])]
        ).strip()
        required = case["required_concepts"]
        forbidden = case.get("forbidden_concepts", [])
        covered = [concept for concept in required if _concept_covered(output_text, concept)]
        forbidden_hits = [
            concept for concept in forbidden if _normalized_contains(output_text, concept)
        ]
        coverage = len(covered) / max(1, len(required))
        passed = coverage >= case.get("min_required_coverage", 1.0) and not forbidden_hits
        durations.append(time.perf_counter() - started)
        coverage_scores.append(coverage)
        cases.append(
            CaseResult(
                case_id=case["id"],
                cohort=case["cohort"],
                dataset_split=case["dataset_split"],
                expected=bool(case.get("expected_passed", True)),
                actual=passed,
                passed=passed == bool(case.get("expected_passed", True)),
                details={
                    "source_kind": case.get("source_kind", "captured_model_output"),
                    "model_alias": case.get("model_alias"),
                    "covered_concepts": covered,
                    "missing_concepts": [concept for concept in required if concept not in covered],
                    "forbidden_hits": forbidden_hits,
                    "coverage": coverage,
                },
            )
        )
    metrics = {
        **_base_metrics(cases, durations),
        "accuracy": sum(1 for case in cases if case.passed) / len(cases),
        "required_concept_coverage": mean(coverage_scores),
        "forbidden_concept_hit_rate": sum(1 for case in cases if case.details["forbidden_hits"])
        / len(cases),
        "real_generated_case_count": sum(
            1 for case in cases if case.details["source_kind"] == "captured_model_output"
        ),
    }
    return CapabilitySection(
        name="summarization_answer_quality",
        evaluation_level="answer",
        metrics=metrics,
        cases=cases,
        automation_gaps=[
            "Summarization answer quality is scored on captured outputs with human-selected required concepts, not a reference-summary semantic metric."
        ],
    )


def generate_report(dataset_version: str = "v1", split: str = "all") -> dict[str, Any]:
    capabilities: list[CapabilitySection] = [
        evaluate_routing(dataset_version, split),
        evaluate_tool_selection(dataset_version, split),
        evaluate_retrieval_strategy(dataset_version, split),
        evaluate_follow_up_detection(dataset_version, split),
        evaluate_summarization_guard(dataset_version, split),
        evaluate_grounding(dataset_version, split),
    ]
    summarization_answer_quality = evaluate_summarization_answer_quality(dataset_version, split)
    if summarization_answer_quality is not None:
        capabilities.append(summarization_answer_quality)

    resolved_splits = _resolve_splits(dataset_version, split)
    return {
        "dataset_version": dataset_version,
        "dataset_split": split,
        "evaluated_splits": resolved_splits,
        "fixture_root": str(_fixture_root(dataset_version)),
        "thresholds": DEFAULT_THRESHOLDS,
        "evaluation_levels": _report_levels(capabilities),
        "capabilities": {capability.name: capability.as_dict() for capability in capabilities},
    }


def compare_reports(baseline: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    comparison: dict[str, Any] = {}
    for capability, thresholds in DEFAULT_THRESHOLDS.items():
        if capability not in baseline.get("capabilities", {}) or capability not in candidate.get(
            "capabilities", {}
        ):
            comparison[capability] = {
                "passes_gate": True,
                "reasons": ["capability not present in both reports; skipped gate comparison"],
            }
            continue
        base_metrics = baseline["capabilities"][capability]["metrics"]
        new_metrics = candidate["capabilities"][capability]["metrics"]
        capability_result: dict[str, Any] = {
            "protected_accuracy_delta": new_metrics.get("protected_accuracy", 0.0)
            - base_metrics.get("protected_accuracy", 0.0),
            "target_improvement_accuracy_delta": new_metrics.get("target_improvement_accuracy", 0.0)
            - base_metrics.get("target_improvement_accuracy", 0.0),
            "passes_gate": True,
            "reasons": [],
        }
        protected_floor = thresholds.get("protected_accuracy_min")
        if (
            protected_floor is not None
            and new_metrics.get("protected_accuracy", 0.0) < protected_floor
        ):
            capability_result["passes_gate"] = False
            capability_result["reasons"].append(
                f"protected_accuracy {new_metrics.get('protected_accuracy', 0.0):.3f} < {protected_floor:.3f}"
            )
        target_delta_min = thresholds.get("target_improvement_delta_min")
        if (
            target_delta_min is not None
            and capability_result["target_improvement_accuracy_delta"] < target_delta_min
        ):
            capability_result["passes_gate"] = False
            capability_result["reasons"].append(
                "target_improvement_accuracy_delta "
                f"{capability_result['target_improvement_accuracy_delta']:.3f} < {target_delta_min:.3f}"
            )
        if capability == "follow_up_detection":
            false_link_rate_max = thresholds.get("false_link_rate_max")
            if (
                false_link_rate_max is not None
                and new_metrics.get("false_link_rate", 1.0) > false_link_rate_max
            ):
                capability_result["passes_gate"] = False
                capability_result["reasons"].append(
                    f"false_link_rate {new_metrics.get('false_link_rate', 1.0):.3f} > {false_link_rate_max:.3f}"
                )
        if capability == "summarization_guard":
            rate_max = thresholds.get("valid_short_input_rejection_rate_max")
            if (
                rate_max is not None
                and new_metrics.get("valid_short_input_rejection_rate", 1.0) > rate_max
            ):
                capability_result["passes_gate"] = False
                capability_result["reasons"].append(
                    "valid_short_input_rejection_rate "
                    f"{new_metrics.get('valid_short_input_rejection_rate', 1.0):.3f} > {rate_max:.3f}"
                )
        if capability == "grounding":
            recall_min = thresholds.get("unsupported_claim_recall_min")
            if (
                recall_min is not None
                and new_metrics.get("unsupported_claim_recall", 0.0) < recall_min
            ):
                capability_result["passes_gate"] = False
                capability_result["reasons"].append(
                    f"unsupported_claim_recall {new_metrics.get('unsupported_claim_recall', 0.0):.3f} < {recall_min:.3f}"
                )
        if capability == "summarization_answer_quality":
            coverage_min = thresholds.get("required_concept_coverage_min")
            if (
                coverage_min is not None
                and new_metrics.get("required_concept_coverage", 0.0) < coverage_min
            ):
                capability_result["passes_gate"] = False
                capability_result["reasons"].append(
                    f"required_concept_coverage {new_metrics.get('required_concept_coverage', 0.0):.3f} < {coverage_min:.3f}"
                )
        comparison[capability] = capability_result
    comparison["all_pass"] = all(
        item.get("passes_gate", True) for item in comparison.values() if isinstance(item, dict)
    )
    return comparison


def write_report(report: dict[str, Any], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return output_path


def default_report_path(label: str, dataset_version: str = "v1", split: str = "all") -> Path:
    suffix = f"-{split}" if split not in {"all", _DEFAULT_SPLIT} else ""
    return _BASELINE_DIR / f"{label}-{dataset_version}{suffix}.json"
