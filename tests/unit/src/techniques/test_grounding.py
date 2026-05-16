from __future__ import annotations

from src.techniques.grounding import (
    ConfidenceCheck,
    ContradictionCheck,
    FaithfulnessCheck,
    evaluate,
)


class TestFaithfulnessCheck:
    def test_accepts_supported_paraphrase_claim(self) -> None:
        result = FaithfulnessCheck().check(
            "OpenAI released a new model this week.",
            "OpenAI introduced a fresh model update this week.",
        )

        assert result.passed is True
        assert result.score >= 1.0

    def test_rejects_ungrounded_claim(self) -> None:
        result = FaithfulnessCheck().check(
            "OpenAI launched a robotics platform.",
            "The source says OpenAI released a new model update this week.",
        )

        assert result.passed is False
        assert any(issue.startswith("faithfulness") for issue in result.issues)


class TestContradictionCheck:
    def test_detects_normalized_numeric_mismatch(self) -> None:
        result = ContradictionCheck().check(
            "Python was first released in 1,989.",
            "Python was first released in 1991.",
        )

        assert result.passed is False
        assert any(issue.startswith("numeric mismatch") for issue in result.issues)

    def test_accepts_equivalent_numeric_formats(self) -> None:
        result = ContradictionCheck().check(
            "Python was first released in 1,991.",
            "Python was first released in 1991.",
        )

        assert result.passed is True


class TestGroundingEvaluate:
    def test_accepts_supported_numeric_answer(self) -> None:
        result = evaluate(
            "Python was first released in 1991 and Guido van Rossum created it.",
            "Python was first released in 1991. Guido van Rossum created it.",
        )

        assert result.route == "accept"

    def test_accepts_supported_paraphrase_with_entity_overlap(self) -> None:
        result = evaluate(
            "Ada Lovelace wrote one of the earliest computer algorithms.",
            "Ada Lovelace is credited with creating one of the first algorithms for a computer.",
        )

        assert result.route == "accept"

    def test_falls_back_for_overconfident_unsupported_answer(self) -> None:
        result = evaluate(
            "OpenAI definitely launched a robotics platform and always planned it this way.",
            "The source says OpenAI released a new model update this week.",
        )

        assert result.route in {"fallback", "discard", "healed_accept"}
        assert any(
            issue.startswith("faithfulness") or issue.startswith("numeric mismatch")
            for issue in result.issues
        )

    def test_confidence_check_flags_overconfidence_without_hedges(self) -> None:
        result = ConfidenceCheck().check("This definitely always happened.", "")

        assert result.passed is False
        assert result.score == 0.0
