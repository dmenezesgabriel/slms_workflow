"""
Lightweight quality signals for routing, tool results, and agent steps.

No new dependencies — pure Python + regex.
All functions are pure (no side effects) and deterministic.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Anchored to line-starts so that technical terms like "quantum error correction"
# in the body of a long web-search result don't trigger false positives.
_ERROR_RE = re.compile(
    r"(?:^|\n)\s*(error|failed|not found|no results?|exception|traceback|"
    r"unable|could not|timed out|connection refused|404|503|"
    r"tool execution failed|tool call failed|"
    r"erro|falhou|não encontrado|sem resultados?|tempo esgotado)\b",
    re.IGNORECASE | re.MULTILINE,
)

# Patterns that indicate a result is likely a model echo / hallucination
_ECHO_RE = re.compile(
    r"\b(the user (is asking|wants)|as an AI|I cannot|I don't have access|"
    r"I'm sorry|unfortunately I|this can be found in)\b",
    re.IGNORECASE,
)

# Pure-numeric pattern — calculator always returns a number; never penalise length.
_NUMERIC_RE = re.compile(r"^-?\d+(\.\d+)?$")

_MIN_USABLE_LEN = 5  # short factual answers ("Tokyo", labels) are valid
_FULL_QUALITY_LEN = 300  # chars; above this length contributes full quality score


@dataclass(frozen=True)
class ResultScore:
    quality: float  # 0.0 – 1.0
    is_usable: bool
    reason: str  # human-readable diagnosis


def score_result(text: str) -> ResultScore:
    """Score the quality of a tool result or handler output.

    Returns a ResultScore with a quality in [0, 1] and a usability flag.
    Callers can decide whether to retry, escalate, or pass the result through.
    """
    stripped = text.strip()

    # Pure numeric strings (e.g. calculator output "12", "3.14") are always valid.
    # Check before the length gate so "12" is never flagged as too short.
    if stripped and _NUMERIC_RE.match(stripped):
        return ResultScore(quality=1.0, is_usable=True, reason="ok")

    if not stripped or len(stripped) < _MIN_USABLE_LEN:
        return ResultScore(quality=0.0, is_usable=False, reason="empty_or_too_short")

    if _ERROR_RE.search(stripped):
        return ResultScore(quality=0.1, is_usable=False, reason="error_signal")

    if _ECHO_RE.search(stripped):
        return ResultScore(quality=0.2, is_usable=False, reason="model_echo")

    quality = min(1.0, len(stripped) / _FULL_QUALITY_LEN)
    return ResultScore(quality=quality, is_usable=True, reason="ok")


def score_route(confidence: float, threshold: float = 0.35) -> bool:
    """True when the routing confidence is high enough to trust without LLM verification."""
    return confidence >= threshold
