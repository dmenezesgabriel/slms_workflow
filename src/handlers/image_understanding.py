from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from src import trace
from src.llm_client import LLMClient, LLMRequest
from src.model_registry import MODEL_REGISTRY, ModelProfile
from src.patterns import IMAGE_REF_RE as _IMAGE_REF_PATTERN
from src.schemas import FinalAnswer, ImageDescription


def _extract_image_path(text: str) -> Path | None:
    match = _IMAGE_REF_PATTERN.search(text)
    return Path(match.group("path")).expanduser().resolve() if match else None


def _strip_image_refs(text: str) -> str:
    return _IMAGE_REF_PATTERN.sub("", text).strip()


def _to_data_url(path: Path) -> str:
    mime_type, _ = mimetypes.guess_type(path)
    encoded = base64.b64encode(path.read_bytes()).decode()
    return f"data:{mime_type or 'image/png'};base64,{encoded}"


def _build_user_content(user_input: str, image_path: Path) -> list[dict[str, Any]]:
    text = _strip_image_refs(user_input) or "Describe what you see in this image."
    return [
        {
            "type": "text",
            "text": text + "\nBe concise. Mention visible objects, visible text, and layout.",
        },
        {"type": "image_url", "image_url": {"url": _to_data_url(image_path)}},
    ]


class ImageUnderstandingHandler:
    id = "image_understanding"
    intent = id

    def __init__(self, profile: ModelProfile | None = None) -> None:
        self._profile = profile or MODEL_REGISTRY["image_understanding"]

    def execute(self, input: str, llm: LLMClient) -> BaseModel:
        return self.handle(input, llm)

    def handle(self, user_input: str, llm: LLMClient) -> BaseModel:
        trace.handler("image_understanding", user_input)
        trace.span_enter("image_understanding")
        image_path = _extract_image_path(user_input)

        if image_path is None:
            trace.span_exit("image_understanding")
            return FinalAnswer(
                answer="Image understanding detected but no image path found. Use @./image.png"
            )

        if not image_path.exists():
            trace.span_exit("image_understanding")
            return FinalAnswer(answer=f"Image file not found: {image_path}")

        result = llm.structured(
            LLMRequest(
                model=self._profile.model,
                system=self._profile.system
                + " Return JSON with description, visible_objects, and visible_text.",
                user=_build_user_content(user_input, image_path),
                max_tokens=self._profile.max_tokens,
                temperature=self._profile.temperature,
            ),
            ImageDescription,
        )
        trace.span_exit("image_understanding")
        return result


_handler = ImageUnderstandingHandler()
handle = _handler.handle
