from __future__ import annotations

import re

from app.llm_client import LLMRequest
from app.model_registry import MODEL_REGISTRY
from app.schemas import IntentClassification


_IMAGE_REF_PATTERN = re.compile(r"@\S+\.(?:png|jpg|jpeg|webp|bmp|gif)", re.IGNORECASE)


def contains_image_reference(text: str) -> bool:
    return _IMAGE_REF_PATTERN.search(text) is not None


def deterministic_route(text: str) -> str | None:
    q = text.lower().strip()

    if not q:
        return "unclassified"

    if contains_image_reference(text):
        return "image_understanding"

    if len(q) <= 2:
        return "general"

    if q in {"hi", "hello", "hey", "olá", "oi"}:
        return "general"

    if any(x in q for x in ["summarize", "summary", "resume", "resuma", "tl;dr"]):
        return "summarization"

    if any(x in q for x in ["tool", "function", "calculate", "calculator", "call", "execute"]):
        return "function_calling"

    if any(x in q for x in ["image", "picture", "photo", "screenshot", "vision"]):
        return "image_understanding"

    if any(x in q for x in ["classify", "intent", "category", "label"]):
        return "classification"

    if q.endswith("?") or any(
        x in q
        for x in [
            "what is",
            "who is",
            "how do",
            "how can",
            "why",
            "when",
            "where",
            "qual é",
            "como",
            "por que",
        ]
    ):
        return "question_answering"

    return None


def route_task(user_input: str, llm) -> IntentClassification:
    deterministic = deterministic_route(user_input)

    if deterministic is not None:
        return IntentClassification(
            intent=deterministic,
            confidence=1.0,
            reason="Matched deterministic routing rule.",
        )

    profile = MODEL_REGISTRY["router"]

    result = llm.structured(
        LLMRequest(
            model=profile.model,
            system=profile.system,
            user=(
                "Classify this user input into one of: "
                "summarization, question_answering, function_calling, "
                "classification, image_understanding, general, unclassified.\n\n"
                f"User input: {user_input}"
            ),
            max_tokens=profile.max_tokens,
            temperature=profile.temperature,
        ),
        IntentClassification,
    )

    if result.confidence < 0.60:
        return IntentClassification(
            intent="general",
            confidence=result.confidence,
            reason=f"Low confidence route fallback. Original reason: {result.reason}",
        )

    return result