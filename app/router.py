from __future__ import annotations

import re

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app import trace
from app.llm_client import LLMClient, LLMRequest
from app.model_registry import MODEL_REGISTRY
from app.schemas import IntentClassification, IntentName

_IMAGE_REF_PATTERN = re.compile(r"@\S+\.(?:png|jpg|jpeg|webp|bmp|gif)", re.IGNORECASE)

_FAST_ROUTE_THRESHOLD = 0.25
_LLM_FALLBACK_THRESHOLD = 0.60

# Phrases that anchor each intent. Adding phrases here improves coverage — no retraining needed.
_INTENT_EXAMPLES: dict[IntentName, list[str]] = {
    "summarization": [
        "summarize this",
        "give me a summary",
        "tl;dr",
        "sum this up",
        "brief summary",
        "condense this",
        "make it shorter",
        "abstract",
        "can you summarize",
        # pt_BR
        "resuma",
        "resumo disso",
        "resume este texto",
        "me dá um resumo",
        "resumo deste",
        "pode resumir",
        "faça um resumo",
    ],
    "question_answering": [
        "what is the capital",
        "what is machine learning",
        "what is Docker",
        "what is a neural network",
        "who invented",
        "how does this work",
        "why does",
        "when did this happen",
        "where is located",
        "explain to me",
        "tell me about",
        "could you explain",
        "help me understand",
        # pt_BR
        "qual é a capital",
        "como funciona",
        "o que é",
        "quem é",
        "quem foi",
        "me fale sobre",
        "me conta sobre",
        "me explique",
        "onde fica",
        "por que",
        "quando foi",
        "me diga sobre",
        "I want to know about",
        "can you tell me",
    ],
    "function_calling": [
        "calculate",
        "compute this",
        "what is 3 plus 5",
        "run the tool",
        "evaluate this expression",
        "math problem",
        "add these numbers",
        "multiply",
        "divide by",
        "what is 2 times 3",
        "calcule",
        "resultado de",
        "search for",
        "search the web for",
        "look up",
        "fetch the url",
        "fetch this page",
        "look up on wikipedia",
        "find information about",
    ],
    "classification": [
        "classify this text",
        "determine the category",
        "label this text",
        "detect the sentiment",
        "is this positive or negative",
        "what type of text is this",
        "categorize this",
        "assign a label",
        "find the category",
        "determine intent of this text",
    ],
    "image_understanding": [
        "what is in this image",
        "describe the picture",
        "analyze this photo",
        "what do you see",
        "look at this image",
        "read this screenshot",
        "what does the image show",
    ],
    "general": [
        "hello",
        "hi there",
        "hey",
        "good morning",
        "good evening",
        "how are you",
        "what can you do",
        "thanks",
        "thank you",
        "oi",
        "olá",
    ],
}


class _MLRouter:
    def __init__(self) -> None:
        examples: list[str] = []
        labels: list[IntentName] = []

        for intent, phrases in _INTENT_EXAMPLES.items():
            examples.extend(phrases)
            labels.extend([intent] * len(phrases))

        self._labels = labels
        self._vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=1, sublinear_tf=True)
        self._matrix = self._vectorizer.fit_transform(examples)

    def classify(self, text: str) -> tuple[IntentName, float]:
        # Classify on the first 100 chars — intent is at the start, content words dilute signal
        snippet = text[:100].lower()
        vec = self._vectorizer.transform([snippet])
        scores = cosine_similarity(vec, self._matrix)[0]
        best_idx = int(np.argmax(scores))
        score = min(1.0, float(scores[best_idx]))  # clamp floating-point noise above 1.0
        return self._labels[best_idx], score


_ml_router = _MLRouter()


def classify_ml(user_input: str) -> IntentClassification | None:
    """Run only the TF-IDF fast path; returns None when score is below threshold.

    Useful for offline evaluation and testing without an LLM connection.
    """
    if not user_input.strip():
        return IntentClassification(intent="unclassified", confidence=1.0, reason="Empty input.")
    if _IMAGE_REF_PATTERN.search(user_input):
        return IntentClassification(
            intent="image_understanding", confidence=1.0, reason="Image path detected."
        )
    intent, score = _ml_router.classify(user_input)
    if score >= _FAST_ROUTE_THRESHOLD:
        return IntentClassification(intent=intent, confidence=score, reason="ML router match.")
    return None


def route_task(user_input: str, llm: LLMClient) -> IntentClassification:
    if not user_input.strip():
        return IntentClassification(intent="unclassified", confidence=1.0, reason="Empty input.")

    if _IMAGE_REF_PATTERN.search(user_input):
        return IntentClassification(
            intent="image_understanding", confidence=1.0, reason="Image path reference detected."
        )

    intent, score = _ml_router.classify(user_input)

    if score >= _FAST_ROUTE_THRESHOLD:
        result = IntentClassification(intent=intent, confidence=score, reason="ML router match.")
        trace.route(result.intent, result.confidence, "ml")
        return result

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

    if result.confidence < _LLM_FALLBACK_THRESHOLD:
        fallback = IntentClassification(
            intent="general",
            confidence=result.confidence,
            reason=f"Low confidence fallback. Original: {result.reason}",
        )
        trace.route(fallback.intent, fallback.confidence, "llm-lowconf")
        return fallback

    trace.route(result.intent, result.confidence, "llm")
    return result
