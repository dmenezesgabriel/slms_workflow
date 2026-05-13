from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal, Protocol

from src import text_utils as ctx
from src import trace
from src.techniques import ner

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
_WORD_RE = re.compile(r"\b\w{3,}\b")
_NUMBER_RE = re.compile(r"\b\d+(?:[.,]\d+)?\b")
_OVERCONFIDENT_RE = re.compile(
    r"\b(definitely|certainly|guaranteed|always|never|absolutely|"
    r"undoubtedly|without\s+(?:a\s+)?doubt|clearly|obviously)\b",
    re.IGNORECASE,
)
_HEDGING_RE = re.compile(
    r"\b(might|may|could|possibly|perhaps|likely|probably|"
    r"approximately|around|about|seems?|appears?|suggests?)\b",
    re.IGNORECASE,
)

_CLAIM_GROUNDED_THRESHOLD = 0.4
_FAITHFULNESS_PASS_RATIO = 0.6

_ACCEPT_THRESHOLD = 0.75
_FALLBACK_THRESHOLD = 0.50
_DISCARD_THRESHOLD = 0.20


@dataclass
class CheckResult:
    passed: bool
    score: float
    issues: list[str] = field(default_factory=list)


@dataclass
class GroundingResult:
    answer: str
    route: Literal["accept", "healed_accept", "fallback", "discard"]
    score: float
    issues: list[str]


class GroundingCheck(Protocol):
    def check(self, answer: str, context: str) -> CheckResult: ...


class HealingStrategy(Protocol):
    def heal(self, answer: str, context: str) -> str: ...


def _split_claims(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_RE.split(text) if len(s.strip()) > 15]


def _keyword_overlap(text: str, reference: str) -> float:
    words = set(_WORD_RE.findall(text.lower()))
    ref_words = set(_WORD_RE.findall(reference.lower()))
    if not words:
        return 1.0
    return len(words & ref_words) / len(words)


class ConfidenceCheck:
    def check(self, answer: str, context: str) -> CheckResult:
        overconfident = len(_OVERCONFIDENT_RE.findall(answer))
        hedging = len(_HEDGING_RE.findall(answer))
        total = overconfident + hedging
        if total == 0:
            return CheckResult(passed=True, score=1.0)
        confidence_ratio = overconfident / total
        score = 1.0 - confidence_ratio
        passed = confidence_ratio < 0.5
        issues = (
            [f"overconfident: {overconfident} assertive markers, {hedging} hedges"]
            if not passed
            else []
        )
        return CheckResult(passed=passed, score=score, issues=issues)


class FaithfulnessCheck:
    def check(self, answer: str, context: str) -> CheckResult:
        if not context:
            return CheckResult(passed=True, score=1.0)
        claims = _split_claims(answer)
        if not claims:
            return CheckResult(passed=True, score=1.0)
        grounded = sum(
            1 for c in claims if _keyword_overlap(c, context) >= _CLAIM_GROUNDED_THRESHOLD
        )
        score = grounded / len(claims)
        passed = score >= _FAITHFULNESS_PASS_RATIO
        issues = (
            []
            if passed
            else [
                f"faithfulness {score:.2f}: "
                f"{len(claims) - grounded}/{len(claims)} claims ungrounded"
            ]
        )
        return CheckResult(passed=passed, score=score, issues=issues)


class ContradictionCheck:
    def check(self, answer: str, context: str) -> CheckResult:
        if not context:
            return CheckResult(passed=True, score=1.0)
        ctx_numbers = set(_NUMBER_RE.findall(context))
        ans_numbers = set(_NUMBER_RE.findall(answer))
        if not ctx_numbers or not ans_numbers:
            return CheckResult(passed=True, score=1.0)
        if ans_numbers & ctx_numbers:
            return CheckResult(passed=True, score=1.0)
        issues = [
            f"numeric mismatch: answer has {sorted(ans_numbers)}, context has {sorted(ctx_numbers)}"
        ]
        return CheckResult(passed=False, score=0.0, issues=issues)


_SCRUB_LABELS = frozenset({"PER", "ORG", "LOC", "GPE", "PRODUCT"})

_ABSTRACT_CONCEPT_SUFFIXES = frozenset(
    {
        "principle",
        "principles",
        "pattern",
        "patterns",
        "theorem",
        "theorems",
        "law",
        "laws",
        "paradigm",
        "methodology",
        "hypothesis",
    }
)


def _is_abstract_concept(entity_text: str) -> bool:
    parts = entity_text.lower().split()
    return bool(parts) and parts[-1] in _ABSTRACT_CONCEPT_SUFFIXES


class EntityScrubber:
    def heal(self, answer: str, context: str) -> str:
        answer_entities = [
            e
            for e in ner.extract(answer)
            if e.label in _SCRUB_LABELS and not _is_abstract_concept(e.text)
        ]
        context_lower = context.lower()
        hallucinated = {
            e.text.lower() for e in answer_entities if e.text.lower() not in context_lower
        }
        if not hallucinated:
            return answer
        claims = _split_claims(answer)
        clean = [s for s in claims if not any(h in s.lower() for h in hallucinated)]
        if not clean:
            return ""
        return " ".join(clean) + " (Some references could not be verified in the source.)"


class GroundingRewrite:
    def heal(self, answer: str, context: str) -> str:
        rewritten = ctx.compress(context, query=answer, max_sentences=4)
        prefix = (
            "According to the provided data, "
            if _NUMBER_RE.search(rewritten)
            else "Based on the available information, "
        )
        return prefix + rewritten


class DefaultHealer:
    def __init__(self) -> None:
        self._scrubber = EntityScrubber()
        self._rewriter = GroundingRewrite()

    def heal(self, answer: str, context: str) -> str:
        scrubbed = self._scrubber.heal(answer, context)
        if len(scrubbed) < 20:
            return self._rewriter.heal(answer, context)
        return scrubbed


class GroundingLayer:
    def __init__(
        self,
        checks: list[tuple[GroundingCheck, float]],
        healer: HealingStrategy,
        accept_threshold: float = _ACCEPT_THRESHOLD,
        fallback_threshold: float = _FALLBACK_THRESHOLD,
        discard_threshold: float = _DISCARD_THRESHOLD,
    ) -> None:
        self._checks = checks
        self._healer = healer
        self._accept_threshold = accept_threshold
        self._fallback_threshold = fallback_threshold
        self._discard_threshold = discard_threshold

    def evaluate(self, answer: str, context: str) -> GroundingResult:
        all_issues: list[str] = []
        total_weight = sum(w for _, w in self._checks)
        composite = 0.0

        for check, weight in self._checks:
            result = check.check(answer, context)
            composite += result.score * (weight / total_weight)
            all_issues.extend(result.issues)
            trace.grounding_check(type(check).__name__, result.passed, result.score)

        if composite >= self._accept_threshold:
            gr = GroundingResult(answer=answer, route="accept", score=composite, issues=[])
            trace.grounding_result(answer, gr.route, gr.score)
            return gr

        if composite < self._discard_threshold:
            gr = GroundingResult(answer=answer, route="discard", score=composite, issues=all_issues)
            trace.grounding_result(answer, gr.route, gr.score)
            return gr

        if composite < self._fallback_threshold:
            gr = GroundingResult(
                answer=answer, route="fallback", score=composite, issues=all_issues
            )
            trace.grounding_result(answer, gr.route, gr.score)
            return gr

        healed = self._healer.heal(answer, context)
        gr = GroundingResult(
            answer=healed, route="healed_accept", score=composite, issues=all_issues
        )
        trace.grounding_result(healed, gr.route, gr.score)
        return gr


_DEFAULT_LAYER = GroundingLayer(
    checks=[
        (ConfidenceCheck(), 0.22),
        (FaithfulnessCheck(), 0.45),
        (ContradictionCheck(), 0.33),
    ],
    healer=DefaultHealer(),
)


def evaluate(answer: str, context: str) -> GroundingResult:
    return _DEFAULT_LAYER.evaluate(answer, context)
