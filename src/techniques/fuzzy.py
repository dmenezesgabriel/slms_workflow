"""
Fuzzy string matching utilities — rapidfuzz, zero ML models, negligible RAM.

Used for:
  - Workflow name resolution from CLI ("research_summarize" → "research_and_summarize")
  - Entity query normalisation before Wikipedia / web_search lookups
"""

from __future__ import annotations

from typing import Any

from rapidfuzz import fuzz, process

from src.text_normalization import normalize_lookup_query

# Minimum similarity score (0–100) to accept a fuzzy workflow match.
_WORKFLOW_THRESHOLD = 72


def match_workflow(name: str, registry: dict[str, Any]) -> str | None:
    """Return the closest workflow name from *registry*, or None if below threshold.

    Accepts exact names, underscore/hyphen variants, and reasonable misspellings.
    """
    if name in registry:
        return name

    result = process.extractOne(
        name,
        registry.keys(),
        scorer=fuzz.WRatio,
        score_cutoff=_WORKFLOW_THRESHOLD,
    )
    return result[0] if result else None


def normalize_query(text: str) -> str:
    """Strip leading articles and trailing punctuation for cleaner lookup queries."""
    return normalize_lookup_query(text)
