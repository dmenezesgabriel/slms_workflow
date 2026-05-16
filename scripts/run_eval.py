from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evals.quality_gate import (  # noqa: E402
    compare_reports,
    default_report_path,
    generate_report,
    write_report,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the frozen quality benchmark and write a JSON report."
    )
    parser.add_argument(
        "--dataset-version", default="v1", help="Fixture dataset version to evaluate"
    )
    parser.add_argument(
        "--split",
        default="all",
        help="Fixture split to evaluate: all, dev, heldout, or default for legacy datasets",
    )
    parser.add_argument(
        "--label",
        default="latest",
        help="Output label used when --output is not provided (for example: baseline, latest, pr-123)",
    )
    parser.add_argument(
        "--output", type=Path, help="Explicit output path for the generated JSON report"
    )
    parser.add_argument(
        "--compare-to",
        type=Path,
        help="Optional baseline JSON report. When provided, the output report includes metric deltas and gate results.",
    )
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    report = generate_report(dataset_version=args.dataset_version, split=args.split)

    if args.compare_to is not None:
        baseline = json.loads(args.compare_to.read_text())
        report["comparison"] = compare_reports(baseline, report)

    output_path = args.output or default_report_path(
        args.label, dataset_version=args.dataset_version, split=args.split
    )
    write_report(report, output_path)
    print(output_path)


if __name__ == "__main__":
    main()
