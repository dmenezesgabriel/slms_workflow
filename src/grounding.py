"""Post-generation grounding layer: detect and heal hallucinations before returning answers.

Checks (in pipeline order, matching article diagram):
  1. ConfidenceCheck  — flags overconfident assertions with no hedging
  2. FaithfulnessCheck — measures claim grounding against context
  3. ContradictionCheck — detects numeric contradictions with context

Entity hallucination detection runs inside the healing step (EntityScrubber), not as a
scored check — consistent with the article where entity scrubbing is a healing strategy.

Drift monitoring is intentionally omitted: this system is stateless across turns.

Routing (score thresholds from article diagram):
  accept       score >= 0.75  — answer is good as-is
  healed_accept             — answer needed healing, healing applied
  fallback     score < 0.50  — caller should use retrieval candidate
  discard      score < 0.20  — safe decline, answer is unreliable

Weights (article: faithfulness 0.40, consistency 0.30, confidence 0.20, latency 0.10):
  latency omitted → remaining weights normalized to 1.0.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal, Protocol

from src import context as ctx
from src import ner

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

_CLAIM_GROUNDED_THRESHOLD = 0.4  # min keyword overlap for a claim to count as grounded
_FAITHFULNESS_PASS_RATIO = 0.6  # fraction of claims that must be grounded to pass

_ACCEPT_THRESHOLD = 0.75
_FALLBACK_THRESHOLD = 0.50
_DISCARD_THRESHOLD = 0.20


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


@dataclass
class CheckResult:
    passed: bool
    score: float  # 0.0–1.0
    issues: list[str] = field(default_factory=list)


@dataclass
class GroundingResult:
    answer: str
    route: Literal["accept", "healed_accept", "fallback", "discard"]
    score: float
    issues: list[str]


# ---------------------------------------------------------------------------
# Protocols
# ---------------------------------------------------------------------------


class GroundingCheck(Protocol):
    def check(self, answer: str, context: str) -> CheckResult: ...


class HealingStrategy(Protocol):
    def heal(self, answer: str, context: str) -> str: ...


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _split_claims(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_RE.split(text) if len(s.strip()) > 15]


def _keyword_overlap(text: str, reference: str) -> float:
    words = set(_WORD_RE.findall(text.lower()))
    ref_words = set(_WORD_RE.findall(reference.lower()))
    if not words:
        return 1.0
    return len(words & ref_words) / len(words)


# ---------------------------------------------------------------------------
# Grounding checks
# ---------------------------------------------------------------------------


class ConfidenceCheck:
    """Penalizes overconfident assertions (many assertive markers, no hedging).

    A well-calibrated answer uses hedging language when uncertain. An answer
    that asserts strongly with no hedging while being poorly grounded is the
    critical failure pattern the article identifies.
    """

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
    """Measures what fraction of answer claims are grounded in the context."""

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
    """Flags answers whose numbers are entirely disjoint from numbers in the context."""

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


# ---------------------------------------------------------------------------
# Healing strategies
# ---------------------------------------------------------------------------


_SCRUB_LABELS = frozenset({"PER", "ORG", "LOC", "GPE", "PRODUCT"})

# Named concepts — principles, patterns, theorems — are not locations or persons even
# when NER mislabels them (e.g. spaCy tags "Liskov Substitution Principle" as LOC).
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
    """Removes sentences containing named entities absent from the context.

    Entity hallucination detection lives here, not in a scored check — entity
    scrubbing is a healing action, not a scoring signal.

    Only PER/ORG/LOC/GPE/PRODUCT labels are checked; MISC is excluded because
    spaCy tags compound noun phrases (e.g. "Responsibility Principle: A class")
    as MISC, producing false positives where valid explanatory text gets scrubbed.
    Abstract concept names (ending in Principle, Pattern, Theorem …) are also
    excluded: NER mislabels them as LOC/ORG but they cannot be hallucinated entities.
    """

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
    """Rebuilds the answer from the most relevant context sentences."""

    def heal(self, answer: str, context: str) -> str:
        rewritten = ctx.compress(context, query=answer, max_sentences=4)
        prefix = (
            "According to the provided data, "
            if _NUMBER_RE.search(rewritten)
            else "Based on the available information, "
        )
        return prefix + rewritten


class DefaultHealer:
    """Scrubs hallucinated entities first; falls back to a full grounding rewrite."""

    def __init__(self) -> None:
        self._scrubber = EntityScrubber()
        self._rewriter = GroundingRewrite()

    def heal(self, answer: str, context: str) -> str:
        scrubbed = self._scrubber.heal(answer, context)
        if len(scrubbed) < 20:
            return self._rewriter.heal(answer, context)
        return scrubbed


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


class GroundingLayer:
    """Runs checks, computes a weighted composite score, and routes to one of four lanes."""

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

        if composite >= self._accept_threshold:
            return GroundingResult(answer=answer, route="accept", score=composite, issues=[])

        if composite < self._discard_threshold:
            return GroundingResult(
                answer=answer, route="discard", score=composite, issues=all_issues
            )

        if composite < self._fallback_threshold:
            return GroundingResult(
                answer=answer, route="fallback", score=composite, issues=all_issues
            )

        healed = self._healer.heal(answer, context)
        return GroundingResult(
            answer=healed, route="healed_accept", score=composite, issues=all_issues
        )


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

# Weights normalized from article (0.40 / 0.30 / 0.20), latency omitted.
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
