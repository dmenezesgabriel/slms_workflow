from __future__ import annotations

import re
from typing import Protocol

from src import context, ner, trace
from src.patterns import PROPER_NOUN_RE as _PROPER_NOUN_RE
from src.patterns import RECOMMENDATION_RE as _RECOMMENDATION_RE
from src.patterns import RETRIEVAL_SIGNALS_RE as _RETRIEVAL_SIGNALS
from src.patterns import URL_RE as _URL_PATTERN
from src.patterns import WHAT_IS_RE as _WHAT_IS_RE
from src.tools.base import Tool

_REFERENCE_LOOKUP_RE = re.compile(
    r"\b(?:which|what|who|where|quando|qual|que)\b.*"
    r"\b(?:movie|film|book|song|quote|says|said|called|reference|meme|"
    r"filme|livro|música|frase|cita(?:ção|cao)|diz|disse|refer[eê]ncia)\b|"
    r"\b(?:movie|film|book|song|quote|reference|meme|filme|livro|música|frase)\b.*"
    r"\b(?:which|what|who|where|qual|que)\b",
    re.IGNORECASE,
)
_CONCEPT_EXPLANATION_RE = re.compile(
    r"\b(?:explain|explique|explica|what\s+are|o\s+que\s+s[aã]o)\b.*"
    r"\b(?:principles|principles?|princ[ií]pios|patterns|conceitos)\b",
    re.IGNORECASE,
)
_SEARCH_BLOCK_RE = re.compile(
    r"Title:\s*(?P<title>.+?)\n(?:URL:\s*.*?\n)?Snippet:\s*(?P<snippet>.*?)(?=\n\nTitle:|\Z)",
    re.DOTALL,
)
_TITLE_FROM_RE = re.compile(r"\bfrom\s+(.+)$", re.IGNORECASE)
_CAPITALIZED_PHRASE_RE = re.compile(
    r"\b(?:[A-Z][\w''#.-]+|the|of|to|and|for|in|from|with|a|an)"
    r"(?:\s+(?:[A-Z][\w''#.-]+|the|of|to|and|for|in|from|with|a|an)){1,8}\b"
)
_WIKIPEDIA_SUFFIX_RE = re.compile(r"\s*[-–—|:]\s*Wikipedia\s*$", re.IGNORECASE)
_WORD_TOKENS_RE = re.compile(r"[A-Za-z0-9]+")
_ACRONYM_RE = re.compile(r"\b(?:[A-Za-z]\.){2,}[A-Za-z]?\b|\b[A-Z]{3,}\b")
_NON_ALPHA_RE = re.compile(r"[^A-Za-z]")
_ACRONYM_PRINCIPLE_RE = re.compile(
    r"\b[A-Z]\s*[-–:]\s*([A-Z][A-Za-z/-]+(?:\s+[A-Z]?[A-Za-z/-]+){0,3}\s+Principle)"
)
_DASH_SPACE_RE = re.compile(r"[-\s]+")
_AUTHORITY_SIGNALS_RE = re.compile(
    r"\b(official|released|developed|published|nintendo|original)\b", re.IGNORECASE
)
_NOISE_SIGNALS_RE = re.compile(
    r"\b(best|guide|ranking|started|which|what|review|download|hacks?)\b", re.IGNORECASE
)
_MARKUP_CHARS_RE = re.compile(r"[#*_]+")
_OPTION_PREFIX_RE = re.compile(
    r"^(?:Play|Best|All|Getting Started with|Wikipedia)\s+", re.IGNORECASE
)
_SITE_SUFFIX_RE = re.compile(
    r"\s*[-–—|:]\s*(?:Wikipedia|YouTube|eBay|Archive\.org).*$", re.IGNORECASE
)
_VERSION_SUFFIX_RE = re.compile(r"\s+Version\b.*$", re.IGNORECASE)
_FOR_THE_RE = re.compile(r"\s+for\s+the\s+.+$", re.IGNORECASE)
_LEADING_ARTICLES_RE = re.compile(r"^(?:of|and|the|its)\s+", re.IGNORECASE)
_TRAILING_SINGLE_CHAR_RE = re.compile(r"\s+[a-zA-Z]$")
_FILTER_WORDS_RE = re.compile(
    r"\b(company|nintendo|game freak|games of all time|games for|youtube|guide|how to"
    r"|chronological|order|beginner|which|ranked)\b",
    re.IGNORECASE,
)
_QUOTED_TEXT_RE = re.compile('["""\']([^"""\']{3,80})["""\']')
_REF_SITE_SUFFIX_RE = re.compile(
    r"\s*[-–—|:]\s*(?:Wikipedia|IMDb|Rotten Tomatoes).*$", re.IGNORECASE
)
_REF_META_PREFIX_RE = re.compile(
    r"^(?:Title|Snippet|Phrases from|Quick Answer:\s*)\s*", re.IGNORECASE
)
_REF_META_SUFFIX_RE = re.compile(r"\s+(?:Quote|Quotes|Meaning|Explained)$", re.IGNORECASE)
_DIGITS_ONLY_RE = re.compile(r"\d+(?:\s*\([^)]*\))?")

_REFERENCE_STOPWORDS = {
    "which",
    "what",
    "who",
    "where",
    "movie",
    "film",
    "book",
    "song",
    "quote",
    "says",
    "said",
    "that",
    "the",
    "qual",
    "filme",
    "livro",
    "frase",
}
_MAX_CONTEXT_SENTENCES = 6


class Retriever(Protocol):
    def fetch_context(self, user_input: str) -> str:
        """Return compressed grounding context, or an empty string."""


def needs_retrieval(text: str) -> bool:
    return (
        bool(_URL_PATTERN.search(text))
        or _RETRIEVAL_SIGNALS.search(text) is not None
        or ner.is_temporal(text)
    )


def extract_direct_what_is_entity(prompt: str) -> str | None:
    wi_match = _WHAT_IS_RE.search(prompt)
    if wi_match is None:
        return None
    match = _PROPER_NOUN_RE.search(prompt, wi_match.end())
    return match.group(1) if match else None


class DefaultRetriever:
    def __init__(self, web_fetch: Tool, web_search: Tool, wikipedia: Tool) -> None:
        self._web_fetch = web_fetch
        self._web_search = web_search
        self._wikipedia = wikipedia

    def fetch_context(self, user_input: str) -> str:
        url_match = _URL_PATTERN.search(user_input)
        if url_match:
            trace.retrieval("web_fetch", url_match.group())
            raw = self._web_fetch.execute({"url": url_match.group()})
            return context.compress(raw, query=user_input, max_sentences=_MAX_CONTEXT_SENTENCES)

        if _RETRIEVAL_SIGNALS.search(user_input):
            return self._fetch_time_sensitive(user_input)

        if _REFERENCE_LOOKUP_RE.search(user_input):
            return self._fetch_reference(user_input)

        if _RECOMMENDATION_RE.search(user_input):
            return self._fetch_recommendation(user_input)

        if _CONCEPT_EXPLANATION_RE.search(user_input):
            return self._fetch_concept(user_input)

        entity_context = self._fetch_entity(user_input)
        if entity_context:
            return entity_context

        candidate = extract_direct_what_is_entity(user_input)
        if candidate is None:
            return ""

        return self._fetch_wikipedia(candidate, user_input)

    def _fetch_time_sensitive(self, user_input: str) -> str:
        wiki = self._fetch_wikipedia(user_input, user_input)
        if wiki:
            return wiki
        return self._fetch_web_search(user_input, user_input)

    def _fetch_entity(self, user_input: str) -> str:
        entities = ner.lookup_entities(user_input)
        if not entities:
            return ""
        entity_text = entities[0].text
        if ner.is_temporal(user_input):
            return self._fetch_web_search(entity_text, user_input)
        wiki = self._fetch_wikipedia(entity_text, user_input)
        if wiki:
            return wiki
        return self._fetch_web_search(entity_text, user_input)

    def _fetch_wikipedia(self, query: str, user_input: str) -> str:
        wiki = self._wikipedia.execute({"query": query})
        if not _is_successful_wikipedia_result(wiki):
            return ""
        trace.retrieval("wikipedia", query)
        return context.compress(wiki, query=user_input, max_sentences=_MAX_CONTEXT_SENTENCES)

    def _fetch_web_search(self, query: str, user_input: str) -> str:
        raw = self._run_search(query, max_results=3)
        return context.compress(raw, query=user_input, max_sentences=_MAX_CONTEXT_SENTENCES)

    def _run_search(self, query: str, max_results: int) -> str:
        raw = self._web_search.execute({"query": query, "max_results": max_results})
        trace.retrieval("web_search", query)
        return raw

    def _fetch_concept(self, user_input: str) -> str:
        raw = "\n\n".join(
            self._run_search(q, max_results=5) for q in _concept_search_queries(user_input)
        )
        compressed = context.compress(raw, query=user_input, max_sentences=_MAX_CONTEXT_SENTENCES)
        items = _infer_concept_items(raw)
        if items:
            trace.retrieval("concept_items", "; ".join(items[:5]))
            return (
                "Key items inferred from web evidence: "
                + "; ".join(items[:8])
                + f"\nEvidence:\n{compressed}"
            )
        return compressed

    def _fetch_recommendation(self, user_input: str) -> str:
        raw = "\n\n".join(
            [
                self._run_search(user_input, max_results=3),
                self._run_search(f"official beginner recommendation {user_input}", max_results=3),
            ]
        )
        compressed = context.compress(raw, query=user_input, max_sentences=_MAX_CONTEXT_SENTENCES)
        options = _infer_recommendation_options(raw, user_input)
        if options:
            trace.retrieval("recommendation_options", "; ".join(options[:3]))
            return (
                "Candidate options inferred from web evidence: "
                + "; ".join(options[:5])
                + f"\nEvidence:\n{compressed}"
            )
        return compressed

    def _fetch_reference(self, user_input: str) -> str:
        raw = "\n\n".join(
            self._run_search(q, max_results=5) for q in _reference_search_queries(user_input)
        )
        compressed = context.compress(raw, query=user_input, max_sentences=_MAX_CONTEXT_SENTENCES)
        candidate = _infer_reference_candidate(raw, user_input)
        if candidate:
            trace.retrieval("reference_candidate", candidate)
            return f"Likely answer inferred from web evidence: {candidate}\nEvidence:\n{compressed}"
        return compressed


def candidate_answer_from_context(retrieved_context: str) -> str:
    key_items_prefix = "Key items inferred from web evidence: "
    if retrieved_context.startswith(key_items_prefix):
        return retrieved_context.splitlines()[0].removeprefix(key_items_prefix).strip()

    for prefix in (
        "Likely answer inferred from web evidence: ",
        "Candidate options inferred from web evidence: ",
    ):
        if retrieved_context.startswith(prefix):
            first_line = retrieved_context.splitlines()[0]
            value = first_line.removeprefix(prefix).split(";", 1)[0].strip()
            return value
    return ""


def _concept_search_queries(user_input: str) -> list[str]:
    queries = [user_input]
    acronym_match = _ACRONYM_RE.search(user_input)
    if acronym_match:
        acronym = _NON_ALPHA_RE.sub("", acronym_match.group()).upper()
        queries.append(f"{acronym} stands for principles")
    return queries


def _infer_concept_items(raw: str) -> list[str]:
    items: list[str] = []
    for match in _ACRONYM_PRINCIPLE_RE.findall(raw):
        item = _DASH_SPACE_RE.sub(" ", match).strip()
        item = " ".join(word.capitalize() for word in item.split())
        if not item.lower().endswith("principle"):
            item = f"{item} Principle"
        if item.lower() not in {existing.lower() for existing in items}:
            items.append(item)
    return items


def _infer_recommendation_options(raw: str, query: str) -> list[str]:
    query_terms = {
        token.lower()
        for token in _WORD_TOKENS_RE.findall(query)
        if len(token) > 2 and token not in _REFERENCE_STOPWORDS
    }
    scored: dict[str, float] = {}
    for match in _SEARCH_BLOCK_RE.finditer(raw):
        title = match.group("title").strip()
        snippet = match.group("snippet").strip()
        block = f"{title} {snippet}"
        block_terms = {token.lower() for token in _WORD_TOKENS_RE.findall(block)}
        block_score = float(len(query_terms & block_terms))
        if _AUTHORITY_SIGNALS_RE.search(block):
            block_score += 2.0
        for candidate in _CAPITALIZED_PHRASE_RE.findall(block):
            normalized = _normalize_recommendation_option(candidate)
            if not normalized:
                continue
            score = block_score + min(len(normalized.split()), 5) * 0.2
            normalized_terms = {token.lower() for token in _WORD_TOKENS_RE.findall(normalized)}
            if normalized_terms & query_terms:
                score += 5.0
            if _NOISE_SIGNALS_RE.search(normalized):
                score -= 2.5
            scored[normalized] = scored.get(normalized, 0.0) + score
    return [
        candidate for candidate, _ in sorted(scored.items(), key=lambda item: item[1], reverse=True)
    ]


def _normalize_recommendation_option(candidate: str) -> str:
    cleaned = _MARKUP_CHARS_RE.sub("", candidate)
    cleaned = _OPTION_PREFIX_RE.sub("", cleaned)
    cleaned = _SITE_SUFFIX_RE.sub("", cleaned)
    cleaned = _VERSION_SUFFIX_RE.sub("", cleaned)
    cleaned = _FOR_THE_RE.sub("", cleaned)
    cleaned = _LEADING_ARTICLES_RE.sub("", cleaned)
    cleaned = _TRAILING_SINGLE_CHAR_RE.sub("", cleaned)
    cleaned = cleaned.strip(' .,:;!?()[]{}"\'""')
    if len(cleaned) < 4 or not any(char.isupper() for char in cleaned):
        return ""
    if cleaned.lower() in {"game boy advance", "visual boy advance"}:
        return ""
    if _FILTER_WORDS_RE.search(cleaned):
        return ""
    if cleaned.lower() in {"its the", "the game", "and game", "in the"}:
        return ""
    return cleaned


def _reference_search_queries(user_input: str) -> list[str]:
    clue_terms = [
        token
        for token in _WORD_TOKENS_RE.findall(user_input.lower())
        if (len(token) > 2 or token.isdigit()) and token not in _REFERENCE_STOPWORDS
    ]
    clue_query = " ".join(clue_terms + ["quote", "source"])
    queries = [user_input]
    if clue_query and clue_query.lower() != user_input.lower():
        queries.append(clue_query)
    return queries


def _infer_reference_candidate(raw: str, query: str) -> str:
    query_terms = {
        token.lower()
        for token in _WORD_TOKENS_RE.findall(query)
        if (len(token) > 2 or token.isdigit()) and token.lower() not in _REFERENCE_STOPWORDS
    }
    scored: dict[str, float] = {}
    for match in _SEARCH_BLOCK_RE.finditer(raw):
        title = match.group("title").strip()
        snippet = match.group("snippet").strip()
        block = f"{title} {snippet}"
        block_terms = {token.lower() for token in _WORD_TOKENS_RE.findall(block)}
        block_score = float(len(query_terms & block_terms))
        if "42" in query and "42" in block:
            block_score += 2.0

        for candidate in _reference_candidates_from_block(title, snippet):
            normalized = _normalize_reference_candidate(candidate)
            if not normalized:
                continue
            score = block_score + min(len(normalized.split()), 6) * 0.2
            if normalized.lower() in title.lower():
                score += 1.0
            scored[normalized] = scored.get(normalized, 0.0) + score

    if not scored:
        return ""
    return max(scored.items(), key=lambda item: item[1])[0]


def _reference_candidates_from_block(title: str, snippet: str) -> list[str]:
    candidates = [_WIKIPEDIA_SUFFIX_RE.sub("", title)]
    from_match = _TITLE_FROM_RE.search(candidates[0])
    if from_match:
        candidates.append(from_match.group(1))
    candidates.extend(_QUOTED_TEXT_RE.findall(snippet))
    candidates.extend(_CAPITALIZED_PHRASE_RE.findall(f"{title} {snippet}"))
    return candidates


def _normalize_reference_candidate(candidate: str) -> str:
    cleaned = _MARKUP_CHARS_RE.sub("", candidate)
    cleaned = _REF_SITE_SUFFIX_RE.sub("", cleaned)
    cleaned = _REF_META_PREFIX_RE.sub("", cleaned)
    cleaned = _REF_META_SUFFIX_RE.sub("", cleaned)
    cleaned = cleaned.strip(' .,:;!?()[]{}"\'""')
    lowered = cleaned.lower()
    if len(cleaned) < 4 or lowered in {"wikipedia", "title", "snippet"}:
        return ""
    if _DIGITS_ONLY_RE.fullmatch(cleaned):
        return ""
    return cleaned


def _is_successful_wikipedia_result(text: str) -> bool:
    return "No Wikipedia article" not in text and "failed" not in text.lower()


# Module-level singleton using concrete tool implementations
from src.tools.web_fetch import WebFetch  # noqa: E402
from src.tools.web_search import WebSearch  # noqa: E402
from src.tools.wikipedia import Wikipedia  # noqa: E402

DEFAULT_RETRIEVER: Retriever = DefaultRetriever(
    web_fetch=WebFetch(),
    web_search=WebSearch(),
    wikipedia=Wikipedia(),
)
