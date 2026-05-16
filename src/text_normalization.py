"""Shared text normalization helpers for lightweight lexical matching.

These helpers are intentionally deterministic and dependency-light so later
routing, tool-selection, retrieval, and grounding code can share one internal
normalization layer.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

WHITESPACE_RE = re.compile(r"\s+")
PUNCTUATION_RE = re.compile(r"[^\w\s]")
TOKEN_RE = re.compile(r"\b\w+\b")
LEADING_ARTICLE_RE = re.compile(
    r"^(?:the|a|an|o|os|as|um|uma|uns|umas)\s+",
    re.IGNORECASE,
)


def strip_diacritics(text: str) -> str:
    """Return *text* with accent marks removed but characters otherwise preserved."""
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def normalize_whitespace(text: str) -> str:
    """Collapse repeated whitespace and trim the result."""
    return WHITESPACE_RE.sub(" ", text).strip()


def normalize_text(
    text: str,
    *,
    lowercase: bool = True,
    fold_diacritics: bool = True,
    strip_punctuation: bool = False,
) -> str:
    """Normalize text for lexical comparison.

    By default this casefolds, removes diacritics, and collapses whitespace.
    Punctuation stripping is optional so callers can keep URL- or symbol-rich
    text intact when needed.
    """
    value = text.casefold() if lowercase else text
    if fold_diacritics:
        value = strip_diacritics(value)
    if strip_punctuation:
        value = PUNCTUATION_RE.sub(" ", value)
    return normalize_whitespace(value)


def tokenize(text: str) -> list[str]:
    """Tokenize normalized text into word-like units."""
    normalized = normalize_text(text, strip_punctuation=True)
    return TOKEN_RE.findall(normalized)


def normalize_lookup_query(text: str) -> str:
    """Normalize entity/topic lookup text while preserving internal spacing."""
    value = normalize_whitespace(text.strip(" .,!?;:\n\t"))
    return LEADING_ARTICLE_RE.sub("", value).strip()


def normalized_unique_tokens(text: str) -> set[str]:
    """Return a set of normalized tokens for overlap-style scoring."""
    return set(tokenize(text))


def join_normalized_tokens(tokens: Iterable[str]) -> str:
    """Join already-normalized tokens into a stable single string."""
    return " ".join(token for token in tokens if token)
