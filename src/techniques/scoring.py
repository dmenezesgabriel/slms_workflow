"""
Lightweight quality signals for routing, tool results, and agent steps.

No new dependencies - pure Python + regex.
All functions are pure (no side effects) and deterministic.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_ERROR_RE = re.compile(
    r"(?:^|\n)\s*(error|failed|not found|no results?|exception|traceback|"
    r"unable|could not|timed out|connection refused|404|503|"
    r"tool execution failed|tool call failed|"
    r"erro|falhou|não encontrado|sem resultados?|tempo esgotado)\b",
    re.IGNORECASE | re.MULTILINE,
)

_ECHO_RE = re.compile(
    r"\b(the user (is asking|wants)|as an AI|I cannot|I don't have access|"
    r"I'm sorry|unfortunately I|this can be found in)\b",
    re.IGNORECASE,
)

_NUMERIC_RE = re.compile(r"^-?\d+(\.\d+)?$")

_MIN_USABLE_LEN = 5
_FULL_QUALITY_LEN = 300


@dataclass(frozen=True)
class ResultScore:
    quality: float
    is_usable: bool
    reason: str


def score_result(text: str) -> ResultScore:
    stripped = text.strip()

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
    return confidence >= threshold
