from __future__ import annotations

import json
from pathlib import Path

from evals.quality_gate import compare_reports, generate_report, write_report


def test_quality_report_v1_preserves_legacy_shape() -> None:
    report = generate_report(dataset_version="v1")

    assert report["dataset_version"] == "v1"
    assert report["evaluated_splits"] == ["default"]
    assert set(report["capabilities"]) == {
        "routing",
        "tool_selection",
        "retrieval_strategy",
        "follow_up_detection",
        "summarization_guard",
        "grounding",
    }
    assert report["capabilities"]["routing"]["evaluation_level"] == "decision"
    assert report["capabilities"]["grounding"]["evaluation_level"] == "answer"


def test_quality_report_v2_tracks_splits_levels_and_answer_quality(tmp_path: Path) -> None:
    report = generate_report(dataset_version="v2", split="all")

    assert report["dataset_version"] == "v2"
    assert report["evaluated_splits"] == ["dev", "heldout"]
    assert report["evaluation_levels"]["decision"]["capabilities"]
    assert "summarization_answer_quality" in report["capabilities"]

    routing = report["capabilities"]["routing"]
    assert routing["metrics"]["split_accuracy"]["dev"] >= 0.0
    assert routing["metrics"]["split_accuracy"]["heldout"] >= 0.0
    assert "mean_case_latency_ms" in routing["metrics"]

    tool_selection = report["capabilities"]["tool_selection"]
    assert tool_selection["metrics"]["ranked_candidates_available"] is True
    assert tool_selection["metrics"]["top_k"] == 2
    assert (
        tool_selection["metrics"]["top_k_accuracy"] >= tool_selection["metrics"]["top_1_accuracy"]
    )

    summary_quality = report["capabilities"]["summarization_answer_quality"]
    assert summary_quality["evaluation_level"] == "answer"
    assert summary_quality["metrics"]["real_generated_case_count"] > 0

    grounding = report["capabilities"]["grounding"]
    assert grounding["metrics"]["real_generated_case_count"] > 0

    output_path = tmp_path / "quality-report-v2.json"
    write_report(report, output_path)
    saved = json.loads(output_path.read_text())
    assert saved["evaluation_levels"] == report["evaluation_levels"]


def test_quality_comparison_includes_gate_results() -> None:
    baseline = generate_report(dataset_version="v1")
    candidate = generate_report(dataset_version="v1")

    comparison = compare_reports(baseline, candidate)

    assert "routing" in comparison
    assert "all_pass" in comparison
    assert isinstance(comparison["routing"]["passes_gate"], bool)


def test_cross_version_comparison_skips_missing_capabilities() -> None:
    baseline = generate_report(dataset_version="v1")
    candidate = generate_report(dataset_version="v2", split="all")

    comparison = compare_reports(baseline, candidate)

    assert comparison["summarization_answer_quality"]["passes_gate"] is True
    assert "skipped gate comparison" in comparison["summarization_answer_quality"]["reasons"][0]
