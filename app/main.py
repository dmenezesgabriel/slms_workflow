from __future__ import annotations

import base64
import mimetypes
import re
from pathlib import Path

from app.llm_client import LLMRequest
from app.model_registry import MODEL_REGISTRY
from app.providers.openai_local import OpenAILocalClient
from app.router import route_task
from app.schemas import (
    ClassificationResult,
    FinalAnswer,
    ImageDescription,
    SummaryResult,
    ToolDecision,
)
from app.tools import execute_tool_decision


_IMAGE_REF_PATTERN = re.compile(r"@(?P<path>\S+\.(?:png|jpg|jpeg|webp|bmp|gif))", re.IGNORECASE)


def extract_image_path(user_input: str) -> Path | None:
    match = _IMAGE_REF_PATTERN.search(user_input)

    if match is None:
        return None

    raw_path = match.group("path")
    return Path(raw_path).expanduser().resolve()


def strip_image_references(user_input: str) -> str:
    return _IMAGE_REF_PATTERN.sub("", user_input).strip()


def image_to_data_url(path: Path) -> str:
    mime_type, _ = mimetypes.guess_type(path)

    if mime_type is None:
        mime_type = "image/png"

    encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"


def build_image_user_content(user_input: str, image_path: Path) -> list[dict]:
    text_prompt = strip_image_references(user_input)

    if not text_prompt:
        text_prompt = "Describe what you see in this image."

    image_url = image_to_data_url(image_path)

    return [
        {
            "type": "text",
            "text": (
                text_prompt
                + "\nBe concise. Mention visible objects, visible text, and layout."
            ),
        },
        {
            "type": "image_url",
            "image_url": {
                "url": image_url,
            },
        },
    ]


def run(user_input: str, llm: OpenAILocalClient | None = None):
    llm = llm or OpenAILocalClient()

    intent = route_task(user_input, llm)

    if intent.intent == "summarization":
        profile = MODEL_REGISTRY["summarization"]
        return llm.structured(
            LLMRequest(
                model=profile.model,
                system=profile.system,
                user=(
                    "Summarize the article between <article> and </article>.\n\n"
                    f"<article>\n{user_input}\n</article>"
                ),
                max_tokens=profile.max_tokens,
                temperature=profile.temperature,
            ),
            SummaryResult,
        )

    if intent.intent == "function_calling":
        profile = MODEL_REGISTRY["function_calling"]

        decision = llm.structured(
            LLMRequest(
                model=profile.model,
                system=profile.system,
                user=user_input,
                max_tokens=profile.max_tokens,
                temperature=profile.temperature,
            ),
            ToolDecision,
        )

        if not decision.needs_tool:
            return FinalAnswer(answer=decision.reason)

        tool_result = execute_tool_decision(decision)

        if tool_result.success:
            return FinalAnswer(
                answer=f"{tool_result.tool_name} result: {tool_result.result}"
            )

        return FinalAnswer(
            answer=(
                f"Tool execution failed for {tool_result.tool_name}: "
                f"{tool_result.error}"
            )
        )

    if intent.intent == "classification":
        profile = MODEL_REGISTRY["classification"]
        return llm.structured(
            LLMRequest(
                model=profile.model,
                system=profile.system,
                user=user_input,
                max_tokens=profile.max_tokens,
                temperature=profile.temperature,
            ),
            ClassificationResult,
        )

    if intent.intent == "image_understanding":
        image_path = extract_image_path(user_input)

        if image_path is None:
            return FinalAnswer(
                answer=(
                    "Image understanding was detected, but no image path was found. "
                    "Use a path like @./image.png or @/home/user/Pictures/image.jpg."
                )
            )

        if not image_path.exists():
            return FinalAnswer(answer=f"Image file not found: {image_path}")

        profile = MODEL_REGISTRY["image_understanding"]

        return llm.structured(
            LLMRequest(
                model=profile.model,
                system=(
                    profile.system
                    + " Return JSON with description, visible_objects, and visible_text."
                ),
                user=build_image_user_content(user_input, image_path),
                max_tokens=profile.max_tokens,
                temperature=profile.temperature,
            ),
            ImageDescription,
        )

    if intent.intent == "question_answering":
        profile = MODEL_REGISTRY["question_answering"]
        return llm.structured(
            LLMRequest(
                model=profile.model,
                system=profile.system,
                user=user_input,
                max_tokens=profile.max_tokens,
                temperature=profile.temperature,
            ),
            FinalAnswer,
        )

    if intent.intent == "unclassified":
        return FinalAnswer(answer="I could not classify this request.")

    profile = MODEL_REGISTRY["general"]
    return llm.structured(
        LLMRequest(
            model=profile.model,
            system=profile.system,
            user=user_input,
            max_tokens=profile.max_tokens,
            temperature=profile.temperature,
        ),
        FinalAnswer,
    )


if __name__ == "__main__":
    client = OpenAILocalClient()

    while True:
        user_input = input("\n> ").strip()

        if user_input in {"exit", "quit"}:
            break

        result = run(user_input, client)
        print(result.model_dump_json(indent=2))