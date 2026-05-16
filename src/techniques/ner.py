"""
Named-entity extraction with a spaCy multilingual model (xx_ent_wiki_sm).

Design
------
EntityExtractor   - Protocol (target interface for callers)
SpacyExtractor    - Adapter that wraps spaCy's pipeline
_extractor        - Module-level singleton, lazy-loaded on first use

Memory note: xx_ent_wiki_sm adds ~420 MB RSS.  Set SLM_NER=0 to disable.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from src import trace
from src.lexical_scoring import combined_lexical_score
from src.text_normalization import normalize_text

_ENABLED = os.getenv("SLM_NER", "1") == "1"

_LOOKUP_LABELS = frozenset({"PER", "ORG", "LOC", "GPE", "MISC", "PRODUCT"})

_TEMPORAL_RE = re.compile(
    r"\b(latest|current|recent|today|news|now|" r"últimas?|atual|recente|hoje|agora|notícias?)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Entity:
    text: str
    label: str


@runtime_checkable
class EntityExtractor(Protocol):
    def extract(self, text: str) -> list[Entity]: ...


class SpacyExtractor:
    _MODEL = "xx_ent_wiki_sm"

    def __init__(self) -> None:
        self._nlp: Any = None

    def _load(self) -> None:
        if self._nlp is not None:
            return
        try:
            import spacy

            self._nlp = spacy.load(self._MODEL)
        except OSError:
            raise RuntimeError(
                f"spaCy model '{self._MODEL}' not found. "
                f"Run: uv run python -m spacy download {self._MODEL}"
            )

    def extract(self, text: str) -> list[Entity]:
        self._load()
        doc = self._nlp(text)
        return [Entity(text=ent.text, label=ent.label_) for ent in doc.ents]


class _DisabledExtractor:
    def extract(self, text: str) -> list[Entity]:
        return []


_extractor: EntityExtractor = SpacyExtractor() if _ENABLED else _DisabledExtractor()


def extract(text: str) -> list[Entity]:
    entities = _extractor.extract(text)
    if entities:
        trace.ner(text[:60], [(e.text, e.label) for e in entities])
    return entities


def lookup_entities(text: str) -> list[Entity]:
    return [e for e in extract(text) if e.label in _LOOKUP_LABELS]


def best_lookup_entity(text: str, entities: list[Entity] | None = None) -> Entity | None:
    candidates = (
        lookup_entities(text)
        if entities is None
        else [e for e in entities if e.label in _LOOKUP_LABELS]
    )
    if not candidates:
        return None

    normalized_text = normalize_text(text, strip_punctuation=True)

    def score(entity: Entity) -> tuple[float, int, int]:
        similarity = combined_lexical_score(normalized_text, entity.text).score
        return (similarity, len(entity.text), -candidates.index(entity))

    return max(candidates, key=score)


def is_temporal(text: str) -> bool:
    return bool(_TEMPORAL_RE.search(text))
