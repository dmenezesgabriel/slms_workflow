from __future__ import annotations

from src.lexical_scoring import (
    CHAR_NGRAM_RANGE,
    LexicalMatch,
    best_lexical_match,
    combined_lexical_score,
    fuzzy_similarity,
    tfidf_similarity,
    token_overlap_score,
)


def test_token_overlap_score_handles_token_reordering() -> None:
    assert (
        token_overlap_score("search web python decorators", "python decorators search web") == 1.0
    )


def test_token_overlap_score_returns_zero_for_disjoint_inputs() -> None:
    assert token_overlap_score("python", "weather") == 0.0


def test_fuzzy_similarity_tolerates_typos() -> None:
    assert fuzzy_similarity("summarize", "sumarize") > 0.9


def test_tfidf_similarity_handles_portuguese_without_diacritics() -> None:
    score = tfidf_similarity("resuma este texto", "resume este texto")
    assert score > 0.6


def test_combined_lexical_score_exposes_component_scores() -> None:
    match = combined_lexical_score("make this shorter", "make it shorter")

    assert isinstance(match, LexicalMatch)
    assert 0.0 <= match.token_overlap <= 1.0
    assert 0.0 <= match.fuzzy <= 1.0
    assert 0.0 <= match.char_ngram <= 1.0
    assert match.score > 0.6


def test_best_lexical_match_prefers_closest_candidate() -> None:
    match = best_lexical_match(
        "could you make this shorter?",
        ["tell me about docker", "make it shorter", "latest ai news"],
    )

    assert match is not None
    assert match.value == "make it shorter"
    assert match.score > 0.5


def test_best_lexical_match_returns_none_for_empty_candidates() -> None:
    assert best_lexical_match("hello", []) is None


def test_word_level_tfidf_similarity_supports_reordered_tokens() -> None:
    score = tfidf_similarity(
        "python decorators search web",
        "search web for python decorators",
        analyzer="word",
        ngram_range=(1, 2),
    )
    assert score > 0.5


def test_char_ngram_range_constant_is_available() -> None:
    assert CHAR_NGRAM_RANGE == (3, 5)
