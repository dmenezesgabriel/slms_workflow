from __future__ import annotations

from pathlib import Path

from huggingface_hub import hf_hub_download

MODELS_DIR = Path("models")

REPO_ID = "unsloth/Qwen3.5-0.8B-GGUF"
LOCAL_SUBDIR = "qwen3.5-0.8b"

TEXT_MODEL_FILENAME = "Qwen3.5-0.8B-UD-Q4_K_XL.gguf"
MMPROJ_FILENAME = "mmproj-F16.gguf"


def download_gguf(
    *,
    repo_id: str,
    filename: str,
    local_subdir: str,
) -> Path:
    target_dir = MODELS_DIR / local_subdir
    target_dir.mkdir(parents=True, exist_ok=True)

    path = hf_hub_download(
        repo_id=repo_id,
        filename=filename,
        local_dir=target_dir,
    )

    return Path(path)


def main() -> None:
    model_path = download_gguf(
        repo_id=REPO_ID,
        filename=TEXT_MODEL_FILENAME,
        local_subdir=LOCAL_SUBDIR,
    )

    mmproj_path = download_gguf(
        repo_id=REPO_ID,
        filename=MMPROJ_FILENAME,
        local_subdir=LOCAL_SUBDIR,
    )

    print(f"Downloaded model: {model_path}")
    print(f"Downloaded mmproj: {mmproj_path}")


if __name__ == "__main__":
    main()
