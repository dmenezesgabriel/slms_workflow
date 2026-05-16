from __future__ import annotations

from dataclasses import dataclass

from src import trace
from src.lexical_scoring import LexicalMatch, best_lexical_match
from src.llm_client import LLMClient, LLMRequest
from src.model_registry import MODEL_REGISTRY, ModelProfile
from src.patterns import IMAGE_REF_RE as _IMAGE_REF_PATTERN
from src.router_prototypes import ROUTER_PROTOTYPES
from src.schemas import IntentClassification, IntentName
from src.text_normalization import normalize_text

_FAST_ROUTE_THRESHOLD = 0.25
_LLM_FALLBACK_THRESHOLD = 0.60


@dataclass(frozen=True)
class PrototypeClassification:
    intent: IntentName
    match: LexicalMatch
    prototype: str


class _MLRouter:
    def __init__(self) -> None:
        self._prototypes = ROUTER_PROTOTYPES

    def classify(self, text: str) -> tuple[IntentName, float]:
        result = self.classify_with_details(text)
        return result.intent, result.match.score

    def classify_with_details(self, text: str) -> PrototypeClassification:
        normalized_text = normalize_text(text, strip_punctuation=True)
        best_result: PrototypeClassification | None = None

        for intent, prototypes in self._prototypes.items():
            match = best_lexical_match(normalized_text, list(prototypes))
            if match is None:
                continue
            candidate = PrototypeClassification(intent=intent, match=match, prototype=match.value)
            if best_result is None or candidate.match.score > best_result.match.score:
                best_result = candidate

        if best_result is None:
            return PrototypeClassification(
                intent="general",
                prototype="",
                match=LexicalMatch(
                    value="", score=0.0, token_overlap=0.0, fuzzy=0.0, char_ngram=0.0
                ),
            )
        return best_result


_ml_router = _MLRouter()


class Router:
    def __init__(self, profile: ModelProfile | None = None) -> None:
        self._profile = profile or MODEL_REGISTRY["router"]

    def classify_ml(self, user_input: str) -> IntentClassification | None:
        if not user_input.strip():
            return IntentClassification(
                intent="unclassified", confidence=1.0, reason="Empty input."
            )
        if _IMAGE_REF_PATTERN.search(user_input):
            return IntentClassification(
                intent="image_understanding", confidence=1.0, reason="Image path detected."
            )
        result = _ml_router.classify_with_details(user_input)
        if result.match.score >= _FAST_ROUTE_THRESHOLD:
            return IntentClassification(
                intent=result.intent,
                confidence=result.match.score,
                reason=(
                    "Prototype router match: "
                    f"'{result.prototype}' (overlap={result.match.token_overlap:.2f}, "
                    f"fuzzy={result.match.fuzzy:.2f}, char_ngram={result.match.char_ngram:.2f})."
                ),
            )
        return None

    def route(self, user_input: str, llm: LLMClient) -> IntentClassification:
        if not user_input.strip():
            return IntentClassification(
                intent="unclassified", confidence=1.0, reason="Empty input."
            )

        if _IMAGE_REF_PATTERN.search(user_input):
            return IntentClassification(
                intent="image_understanding",
                confidence=1.0,
                reason="Image path reference detected.",
            )

        fast_result = self.classify_ml(user_input)
        if fast_result is not None:
            trace.route(fast_result.intent, fast_result.confidence, "ml")
            return fast_result

        result = llm.structured(
            LLMRequest(
                model=self._profile.model,
                system=self._profile.system,
                user=(
                    "Classify this user input into one of: "
                    "summarization, question_answering, function_calling, "
                    "classification, image_understanding, general, unclassified.\n\n"
                    f"User input: {user_input}"
                ),
                max_tokens=self._profile.max_tokens,
                temperature=self._profile.temperature,
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


_router = Router()


def classify_ml(user_input: str) -> IntentClassification | None:
    return _router.classify_ml(user_input)


def route_task(
    user_input: str,
    llm: LLMClient,
    router: Router | None = None,
) -> IntentClassification:
    return (router or _router).route(user_input, llm)
