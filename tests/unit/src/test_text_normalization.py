from __future__ import annotations

from src.text_normalization import (
    join_normalized_tokens,
    normalize_lookup_query,
    normalize_text,
    normalize_whitespace,
    normalized_unique_tokens,
    strip_diacritics,
    tokenize,
)


def test_strip_diacritics_handles_portuguese_text() -> None:
    assert strip_diacritics("ação, órgãos, útil") == "acao, orgaos, util"


def test_normalize_text_casefolds_folds_diacritics_and_whitespace() -> None:
    assert normalize_text("  OlÁ   MÚNDO  ") == "ola mundo"


def test_normalize_text_can_strip_punctuation() -> None:
    assert normalize_text("Hello, world!", strip_punctuation=True) == "hello world"


def test_tokenize_normalizes_case_punctuation_and_diacritics() -> None:
    assert tokenize("Olá, mundo! Python-3 é útil.") == ["ola", "mundo", "python", "3", "e", "util"]


def test_normalize_lookup_query_strips_articles_and_trailing_punctuation() -> None:
    assert normalize_lookup_query("  the Ada Lovelace!!! ") == "Ada Lovelace"
    assert normalize_lookup_query("uma linguagem de programação.") == "linguagem de programação"


def test_normalized_unique_tokens_deduplicates_tokens() -> None:
    assert normalized_unique_tokens("Python python PYTHON") == {"python"}


def test_join_normalized_tokens_joins_non_empty_tokens() -> None:
    assert join_normalized_tokens(["ola", "", "mundo"]) == "ola mundo"


def test_normalize_whitespace_collapses_internal_runs() -> None:
    assert normalize_whitespace("a\n\t b   c") == "a b c"
