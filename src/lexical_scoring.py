"""Reusable lexical scoring primitives for deterministic matching."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeVar

from rapidfuzz import fuzz
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from src.text_normalization import normalize_text, normalized_unique_tokens

DEFAULT_FUZZY_THRESHOLD = 75.0
DEFAULT_COMBINED_THRESHOLD = 0.55
CHAR_NGRAM_RANGE = (3, 5)
WORD_NGRAM_RANGE = (1, 2)

T = TypeVar("T")


@dataclass(frozen=True)
class LexicalMatch:
    value: str
    score: float
    token_overlap: float
    fuzzy: float
    char_ngram: float


def token_overlap_score(left: str, right: str) -> float:
    """Return Jaccard overlap of normalized token sets."""
    left_tokens = normalized_unique_tokens(left)
    right_tokens = normalized_unique_tokens(right)
    if not left_tokens and not right_tokens:
        return 1.0
    if not left_tokens or not right_tokens:
        return 0.0
    intersection = len(left_tokens & right_tokens)
    union = len(left_tokens | right_tokens)
    return intersection / union


def fuzzy_similarity(left: str, right: str) -> float:
    """Return a 0-1 RapidFuzz similarity on normalized text."""
    normalized_left = normalize_text(left, strip_punctuation=True)
    normalized_right = normalize_text(right, strip_punctuation=True)
    return fuzz.WRatio(normalized_left, normalized_right) / 100.0


def tfidf_similarity(
    left: str,
    right: str,
    *,
    analyzer: str = "char_wb",
    ngram_range: tuple[int, int] = CHAR_NGRAM_RANGE,
) -> float:
    """Return cosine similarity of a 2-document TF-IDF fit."""
    normalized_left = normalize_text(left, strip_punctuation=analyzer != "char_wb")
    normalized_right = normalize_text(right, strip_punctuation=analyzer != "char_wb")
    vectorizer = TfidfVectorizer(analyzer=analyzer, ngram_range=ngram_range, min_df=1)
    matrix = vectorizer.fit_transform([normalized_left, normalized_right])
    return float(cosine_similarity(matrix[0], matrix[1])[0][0])


def combined_lexical_score(left: str, right: str) -> LexicalMatch:
    """Blend overlap, fuzzy, and char n-gram similarity into one score."""
    overlap = token_overlap_score(left, right)
    fuzzy = fuzzy_similarity(left, right)
    char_ngram = tfidf_similarity(left, right)
    score = (0.35 * overlap) + (0.30 * fuzzy) + (0.35 * char_ngram)
    return LexicalMatch(
        value=right,
        score=min(1.0, score),
        token_overlap=overlap,
        fuzzy=fuzzy,
        char_ngram=char_ngram,
    )


def best_lexical_match(query: str, candidates: list[str]) -> LexicalMatch | None:
    """Return the best lexical match for *query* from *candidates*."""
    if not candidates:
        return None
    matches = [combined_lexical_score(query, candidate) for candidate in candidates]
    return max(matches, key=lambda match: match.score)
