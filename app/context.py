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


def compress(text: str, query: str, max_sentences: int = 6) -> str:
    """Return the most query-relevant sentences using TF-IDF cosine scoring.

    Keeps sentence order so the compressed passage reads naturally.
    Falls back to head-truncation when the corpus is too small to vectorize.
    """
    sentences = _sentences(text)

    if not sentences:
        return text[:800]

    if len(sentences) <= max_sentences:
        return " ".join(sentences)

    try:
        vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words="english", min_df=1)
        matrix = vectorizer.fit_transform(sentences + [query])
        scores = cosine_similarity(matrix[-1], matrix[:-1])[0]
        top = sorted(np.argsort(scores)[-max_sentences:])
        return " ".join(sentences[i] for i in top)
    except ValueError:
        return " ".join(sentences[:max_sentences])


def extract_text(result: BaseModel) -> str:
    """Pull the primary text field from any result schema."""
    data: dict[str, Any] = result.model_dump()
    for key in ("answer", "summary", "label", "description"):
        value = data.get(key)
        if isinstance(value, str):
            return value
    return result.model_dump_json()
