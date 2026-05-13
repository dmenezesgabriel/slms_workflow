from __future__ import annotations

import re
from typing import Any

import numpy as np
from pydantic import BaseModel
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_WHITESPACE = re.compile(r"\s+")
_MIN_LEN = 20
_MAX_LEN = 400


def _sentences(text: str) -> list[str]:
    return [
        s
        for s in _SENTENCE_SPLIT.split(_WHITESPACE.sub(" ", text).strip())
        if _MIN_LEN <= len(s) <= _MAX_LEN
    ]


def compress(text: str, query: str, max_sentences: int = 6, max_chars: int | None = None) -> str:
    """Return the most query-relevant sentences using TF-IDF cosine scoring.

    Keeps sentence order so the compressed passage reads naturally.
    Falls back to head-truncation when the corpus is too small to vectorize.
    max_chars enforces a character budget (4 chars ≈ 1 token) after sentence selection.
    """
    sentences = _sentences(text)

    if not sentences:
        return text[:800]

    if len(sentences) <= max_sentences:
        result = " ".join(sentences)
        return (
            result
            if max_chars is None
            else _apply_char_budget(sentences, list(range(len(sentences))), max_chars)
        )

    try:
        vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words="english", min_df=1)
        matrix = vectorizer.fit_transform(sentences + [query])
        scores = cosine_similarity(matrix[-1], matrix[:-1])[0]
        top = sorted(np.argsort(scores)[-max_sentences:])
        if max_chars is not None:
            top = _apply_char_budget_indices(sentences, top, max_chars)
        return " ".join(sentences[i] for i in top)
    except ValueError:
        top = list(range(min(max_sentences, len(sentences))))
        if max_chars is not None:
            top = _apply_char_budget_indices(sentences, top, max_chars)
        return " ".join(sentences[i] for i in top)


def _apply_char_budget(sentences: list[str], indices: list[int], max_chars: int) -> str:
    return " ".join(sentences[i] for i in _apply_char_budget_indices(sentences, indices, max_chars))


def _apply_char_budget_indices(
    sentences: list[str], indices: list[int], max_chars: int
) -> list[int]:
    selected: list[int] = []
    budget = max_chars
    for i in indices:
        cost = len(sentences[i]) + (1 if selected else 0)
        if cost > budget:
            continue
        selected.append(i)
        budget -= cost
    return selected


def extract_text(result: BaseModel) -> str:
    """Pull useful user-facing text from any result schema.

    Classification results need more than the raw label; returning the reason
    too keeps workflow outputs interpretable and preserves topic/evidence terms
    for downstream nodes and acceptance checks.
    """
    data: dict[str, Any] = result.model_dump()

    label = data.get("label")
    reason = data.get("reason")
    if isinstance(label, str):
        return f"{label}: {reason}" if isinstance(reason, str) and reason else label

    for key in ("answer", "summary", "description"):
        value = data.get(key)
        if isinstance(value, str):
            return value
    return result.model_dump_json()
