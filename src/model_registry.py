from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Mapping

from huggingface_hub import hf_hub_download


@dataclass(frozen=True)
class ModelProfile:
    model: str
    system: str
    max_tokens: int = 256
    temperature: float = 0.0


QWEN35_08B_TEXT = "qwen3.5-0.8b-text"
QWEN35_08B_VISION = "qwen3.5-0.8b-vision"
QWEN25_05B_INSTRUCT = "qwen2.5-0.5b-instruct-q4km"
SMOLLM2_360M_INSTRUCT = "smollm2-360m-instruct-q4km"
MODELS_DIR = Path("models")


@dataclass(frozen=True)
class ModelArtifact:
    """A small GGUF artifact the project knows how to fetch and serve locally."""

    alias: str
    repo_id: str
    filename: str
    local_subdir: str
    mmproj_filename: str | None = None

    @property
    def model_path(self) -> Path:
        return MODELS_DIR / self.local_subdir / self.filename

    @property
    def mmproj_path(self) -> Path | None:
        if self.mmproj_filename is None:
            return None
        return MODELS_DIR / self.local_subdir / self.mmproj_filename


QWEN35_08B_ARTIFACT = ModelArtifact(
    alias=QWEN35_08B_TEXT,
    repo_id="unsloth/Qwen3.5-0.8B-GGUF",
    filename="Qwen3.5-0.8B-UD-Q4_K_XL.gguf",
    local_subdir="qwen3.5-0.8b",
    mmproj_filename="mmproj-F16.gguf",
)

QWEN25_05B_ARTIFACT = ModelArtifact(
    alias=QWEN25_05B_INSTRUCT,
    repo_id="Qwen/Qwen2.5-0.5B-Instruct-GGUF",
    filename="qwen2.5-0.5b-instruct-q4_k_m.gguf",
    local_subdir="qwen2.5-0.5b-instruct",
)

SMOLLM2_360M_ARTIFACT = ModelArtifact(
    alias=SMOLLM2_360M_INSTRUCT,
    repo_id="bartowski/SmolLM2-360M-Instruct-GGUF",
    filename="SmolLM2-360M-Instruct-Q4_K_M.gguf",
    local_subdir="smollm2-360m-instruct",
)

MODEL_ARTIFACTS: dict[str, ModelArtifact] = {
    QWEN35_08B_TEXT: QWEN35_08B_ARTIFACT,
    QWEN35_08B_VISION: QWEN35_08B_ARTIFACT,
    QWEN25_05B_INSTRUCT: QWEN25_05B_ARTIFACT,
    SMOLLM2_360M_INSTRUCT: SMOLLM2_360M_ARTIFACT,
}


MODEL_REGISTRY: dict[str, ModelProfile] = {
    "router": ModelProfile(
        model=QWEN35_08B_TEXT,
        system=(
            "You are a strict intent classifier. "
            "Return only valid JSON matching the requested schema."
        ),
        max_tokens=128,
        temperature=0.0,
    ),
    "summarization": ModelProfile(
        model=QWEN35_08B_TEXT,
        system=(
            "You summarize only the text provided by the user. "
            "Do not invent topics, titles, names, countries, companies, or claims. "
            "If the input is too short or incomplete, say that in the JSON. "
            "Preserve the original topic, names, numbers, dates, decisions, and action items."
        ),
        max_tokens=384,
        temperature=0.0,
    ),
    "question_answering": ModelProfile(
        model=QWEN35_08B_TEXT,
        system=(
            "You answer questions concisely and directly. If context is provided, ground the "
            "answer in that context and do not ignore named titles, entities, or evidence. "
            "For 'which movie/book/song/work says ...' questions, identify the work/title, "
            "not only the quoted value. When giving recommendations, prefer official/original "
            "items unless the user asks for unofficial alternatives. When context includes an "
            "inferred likely answer, include one short supporting detail from the evidence. "
            "If the context is insufficient or "
            "conflicting, say so."
        ),
        max_tokens=256,
        temperature=0.0,
    ),
    "function_calling": ModelProfile(
        model=QWEN35_08B_TEXT,
        # Tool list is injected dynamically by the handler via tool_prompt()
        system="You select and invoke a tool to fulfill the user's request.",
        max_tokens=192,
        temperature=0.0,
    ),
    "classification": ModelProfile(
        model=QWEN35_08B_TEXT,
        system=(
            "You assign a SHORT label (1-5 words, snake_case) to user input. "
            "Examples: programming_language, positive_sentiment, news_article, financial_report. "
            "The label field must be a short category name, never a long description. "
            "Return only valid JSON matching the requested schema."
        ),
        max_tokens=192,
        temperature=0.0,
    ),
    "image_understanding": ModelProfile(
        model=QWEN35_08B_VISION,
        system="You answer questions about images concisely and accurately.",
        max_tokens=256,
        temperature=0.0,
    ),
    "general": ModelProfile(
        model=QWEN35_08B_TEXT,
        system=(
            "You are a concise multilingual local assistant running on a small model. "
            "Answer clearly and avoid unnecessary verbosity."
        ),
        max_tokens=256,
        temperature=0.2,
    ),
    "agent": ModelProfile(
        model=QWEN35_08B_TEXT,
        system=(
            "You are a task planner. Choose one action per step.\n"
            "Actions:\n"
            "  web_search — action_input = the search query (words only)\n"
            "  web_fetch  — action_input = https:// URL\n"
            "  wikipedia  — action_input = topic name\n"
            "  calculator — action_input = math expression like '3+4*2'\n"
            "  summarize  — action_input = 'key findings' (uses previous result)\n"
            "  classify   — action_input = category type (uses previous result)\n"
            "  answer     — action_input = the question (uses previous result)\n"
            "  final_answer — action_input = your complete answer; set is_final=true\n"
            "Once you have tool results, use final_answer immediately.\n"
            "Return only valid JSON matching the schema."
        ),
        max_tokens=256,
        temperature=0.0,
    ),
}


_MODEL_ROLE_ALIASES = {
    "qa": "question_answering",
    "question-answering": "question_answering",
    "function": "function_calling",
    "tool": "function_calling",
    "summary": "summarization",
    "summarizer": "summarization",
    "classifier": "classification",
}


def known_model_aliases() -> list[str]:
    return sorted(MODEL_ARTIFACTS)


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


def download_artifact(artifact: ModelArtifact, *, include_mmproj: bool = False) -> list[Path]:
    paths = [
        download_gguf(
            repo_id=artifact.repo_id,
            filename=artifact.filename,
            local_subdir=artifact.local_subdir,
        )
    ]
    if include_mmproj and artifact.mmproj_filename is not None:
        paths.append(
            download_gguf(
                repo_id=artifact.repo_id,
                filename=artifact.mmproj_filename,
                local_subdir=artifact.local_subdir,
            )
        )
    return paths


def ensure_model_available(model: str, *, auto_download: bool = True) -> Path | None:
    """Ensure a known model alias/path exists locally.

    For known project aliases, missing GGUF files are downloaded from Hugging
    Face. Unknown OpenAI/llama.cpp aliases return None because there is no safe
    way to infer a repo and GGUF filename from an alias alone.
    """

    maybe_path = Path(model)
    if maybe_path.suffix == ".gguf":
        if maybe_path.exists():
            return maybe_path
        raise FileNotFoundError(f"Model path does not exist: {model}")

    artifact = MODEL_ARTIFACTS.get(model)
    if artifact is None:
        return None

    if artifact.model_path.exists():
        return artifact.model_path
    if not auto_download:
        raise FileNotFoundError(
            f"Model alias {model!r} is known but {artifact.model_path} is missing"
        )
    return download_artifact(artifact, include_mmproj=model.endswith("vision"))[0]


def apply_model_overrides(
    *,
    default_model: str | None = None,
    role_models: Mapping[str, str | None] | None = None,
) -> None:
    """Override model aliases used by one or more specialist roles.

    This keeps experimentation cheap: the same deterministic harness can be run
    with different local llama.cpp aliases without changing prompts or code.
    """

    if default_model:
        for role, profile in list(MODEL_REGISTRY.items()):
            if role != "image_understanding":
                MODEL_REGISTRY[role] = replace(profile, model=default_model)

    for role, model in (role_models or {}).items():
        if not model:
            continue
        normalized = _MODEL_ROLE_ALIASES.get(role, role)
        if normalized not in MODEL_REGISTRY:
            raise ValueError(
                f"Unknown model role {role!r}. Available roles: {', '.join(MODEL_REGISTRY)}"
            )
        MODEL_REGISTRY[normalized] = replace(MODEL_REGISTRY[normalized], model=model)
