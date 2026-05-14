from __future__ import annotations

import re

# Detects @file.ext image references; the named group 'path' allows extraction.
IMAGE_REF_RE = re.compile(r"@(?P<path>\S+\.(?:png|jpg|jpeg|webp|bmp|gif))", re.IGNORECASE)

RECOMMENDATION_RE = re.compile(
    r"\b(?:should\s+i|recommend(?:ed|ation)?|best|which\s+.+\s+first|"
    r"what\s+.+\s+first|play\s+first|"
    r"devo|recomenda(?:r|ção|cao)?|melhor|qual\s+.+\s+primeir[oa])\b",
    re.IGNORECASE,
)

URL_RE = re.compile(r"https?://\S+")

# Negative lookahead keeps "what is the capital of X" from triggering entity lookup.
WHAT_IS_RE = re.compile(
    r"\b(what\s+is(?!\s+(?:the\s+)?capital\s+of)|what\s+are|what's|"
    r"o\s+que\s+[eé]|o\s+que\s+s[aã]o)\b",
    re.IGNORECASE,
)

PROPER_NOUN_RE = re.compile(
    r"\b([A-Za-z]*[A-Z][A-Za-z]*[A-Z][A-Za-z]*|[a-z]+[A-Z][a-zA-Z]+|[A-Z][a-z]{2,})\b"
)

RETRIEVAL_SIGNALS_RE = re.compile(
    r"\b(latest|current|recent|today|news|price|weather|stock|score|"
    r"winner|elected|update|version|"
    r"últimas?|atual|recente|hoje|notícias?|preço|clima|tempo|"
    r"vencedor|eleito|atualização|versão)\b",
    re.IGNORECASE,
)
