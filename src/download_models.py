from __future__ import annotations

import argparse

from src.model_registry import (
    MODEL_ARTIFACTS,
    QWEN35_08B_ARTIFACT,
    download_artifact,
    download_gguf,
    known_model_aliases,
)

# Backwards-compatible constants used by older docs/scripts.
REPO_ID = QWEN35_08B_ARTIFACT.repo_id
LOCAL_SUBDIR = QWEN35_08B_ARTIFACT.local_subdir
TEXT_MODEL_FILENAME = QWEN35_08B_ARTIFACT.filename
MMPROJ_FILENAME = QWEN35_08B_ARTIFACT.mmproj_filename or "mmproj-F16.gguf"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Download small GGUF model artifacts from Hugging Face."
    )
    parser.add_argument(
        "--model",
        default="qwen3.5-0.8b-text",
        choices=known_model_aliases(),
        help="Known project model alias to download.",
    )
    parser.add_argument("--repo-id", help="Custom Hugging Face repo id containing a GGUF file.")
    parser.add_argument("--filename", help="Custom GGUF filename in --repo-id.")
    parser.add_argument(
        "--local-subdir",
        help="Subdirectory under models/ for a custom download (default: repo name).",
    )
    parser.add_argument(
        "--include-mmproj",
        action="store_true",
        help="Also download a known model's multimodal projector when available.",
    )
    return parser


def main() -> None:
    args = _build_parser().parse_args()

    if args.repo_id or args.filename:
        if not (args.repo_id and args.filename):
            raise SystemExit("--repo-id and --filename must be provided together")
        local_subdir = args.local_subdir or args.repo_id.split("/", 1)[-1]
        path = download_gguf(
            repo_id=args.repo_id,
            filename=args.filename,
            local_subdir=local_subdir,
        )
        print(f"Downloaded custom model: {path}")
        return

    artifact = MODEL_ARTIFACTS[args.model]
    paths = download_artifact(
        artifact, include_mmproj=args.include_mmproj or args.model.endswith("vision")
    )
    for path in paths:
        print(f"Downloaded: {path}")


if __name__ == "__main__":
    main()
