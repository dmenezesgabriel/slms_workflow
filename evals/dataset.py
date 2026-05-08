"""
Ground truth dataset for offline (no-LLM) evaluation.

Covers: intent routing, deterministic tool selection, NER entity extraction.
Languages: en_US, pt_BR.

Each case is a plain tuple so it serialises to JSON and stays easy to read.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Routing ground truth
# (prompt, expected_intent, language)
# These must be handled by the TF-IDF fast path (score >= threshold)
# so the LLM is never called.  Add only unambiguous, representative cases.
# ---------------------------------------------------------------------------

ROUTING_CASES: list[tuple[str, str, str]] = [
    # summarization — en
    ("summarize this text for me", "summarization", "en"),
    ("give me a summary of this article", "summarization", "en"),
    ("tl;dr this content", "summarization", "en"),
    ("can you summarize this?", "summarization", "en"),
    ("brief summary please", "summarization", "en"),
    # summarization — pt
    ("resume este texto", "summarization", "pt"),
    ("me dá um resumo disso", "summarization", "pt"),
    ("resumo disso", "summarization", "pt"),
    # question answering — en
    ("what is the capital of France", "question_answering", "en"),
    ("how does photosynthesis work", "question_answering", "en"),
    ("explain quantum computing to me", "question_answering", "en"),
    ("can you tell me about Python", "question_answering", "en"),
    ("I want to know about machine learning", "question_answering", "en"),
    # question answering — pt
    ("qual é a capital do Brasil", "question_answering", "pt"),
    ("como funciona a fotossíntese", "question_answering", "pt"),
    ("o que é machine learning", "question_answering", "pt"),
    # function calling — en
    ("search for Python tutorials", "function_calling", "en"),
    ("search the web for climate change", "function_calling", "en"),
    ("look up Python on Wikipedia", "function_calling", "en"),
    ("calculate 15 + 7", "function_calling", "en"),
    ("multiply 12 by 9", "function_calling", "en"),
    ("divide 144 by 12", "function_calling", "en"),
    # function calling — pt
    ("calcule 15 mais 7", "function_calling", "pt"),
    ("resultado de 144 dividido por 12", "function_calling", "pt"),
    # classification — en
    ("classify this text as positive or negative", "classification", "en"),
    ("determine the sentiment of this review", "classification", "en"),
    ("what type of text is this", "classification", "en"),
    ("is this positive or negative", "classification", "en"),
    # general — en
    ("hello there", "general", "en"),
    ("hi", "general", "en"),
    ("how are you", "general", "en"),
    ("thanks", "general", "en"),
    # general — pt
    ("olá", "general", "pt"),
    ("oi", "general", "pt"),
    # N04 regression: temporal news queries must route to function_calling, not general
    ("What are the latest news about OpenAI?", "function_calling", "en"),
    ("recent news on Python 3.13", "function_calling", "en"),
    ("current news about artificial intelligence", "function_calling", "en"),
    ("últimas notícias sobre inteligência artificial", "function_calling", "pt"),
    ("notícias recentes sobre Python", "function_calling", "pt"),
]

# ---------------------------------------------------------------------------
# Tool selection ground truth
# (prompt, expected_tool, arg_key, arg_value_substring)
# Tests ONLY the deterministic paths in function_calling.py — no LLM needed.
# ---------------------------------------------------------------------------

TOOL_CASES: list[tuple[str, str, str, str]] = [
    # web_search
    ("search for Python tutorials", "web_search", "query", "Python tutorials"),
    ("search for llama.cpp", "web_search", "query", "llama.cpp"),
    ("search the web for climate change", "web_search", "query", "climate change"),
    ("search about Rust programming", "web_search", "query", "Rust"),
    # wikipedia
    ("look up Python on Wikipedia", "wikipedia", "query", "Python"),
    ("find the Wikipedia article about machine learning", "wikipedia", "query", "machine learning"),
    ("look up the Wikipedia article about Brazil", "wikipedia", "query", "Brazil"),
    ("Wikipedia article about the Python programming language", "wikipedia", "query", "Python"),
    # web_fetch
    ("fetch https://example.com", "web_fetch", "url", "https://example.com"),
    ("fetch https://docs.python.org/3/", "web_fetch", "url", "https://docs.python.org"),
    # calculator — symbol expressions
    ("15 + 7", "calculator", "expression", "15"),
    ("144 / 12", "calculator", "expression", "144"),
    # calculator — natural language
    ("what is 3 times 5", "calculator", "expression", "3"),
    ("144 divided by 12", "calculator", "expression", "144"),
]

# ---------------------------------------------------------------------------
# NER entity ground truth
# (prompt, expected_entities) where each entity is (text_fragment, label)
# text_fragment: case-insensitive substring that must appear in the entity text
# label: spaCy label (PER, ORG, LOC, MISC, GPE)
# ---------------------------------------------------------------------------

NER_CASES: list[tuple[str, list[tuple[str, str]]]] = [
    # English
    ("Tell me about OpenAI", [("OpenAI", "ORG")]),
    ("Who is Sam Altman?", [("Sam Altman", "PER")]),
    ("Where is Rio de Janeiro located?", [("Rio de Janeiro", "LOC")]),
    ("What is the history of Brazil?", [("Brazil", "LOC")]),
    ("Tell me about Linus Torvalds", [("Linus Torvalds", "PER")]),
    ("Look up Microsoft on Wikipedia", [("Microsoft", "ORG")]),
    # Portuguese
    ("O que é a Petrobras?", [("Petrobras", "ORG")]),
    ("Me fale sobre o Rio de Janeiro", [("Rio de Janeiro", "LOC")]),
    ("Quem é Guido van Rossum?", [("Guido", "PER")]),
    ("Me conta sobre a Amazônia", [("Amazônia", "LOC")]),
]

# ---------------------------------------------------------------------------
# Temporal signal ground truth — used to score is_temporal() accuracy.
# (text, is_temporal: bool)
# ---------------------------------------------------------------------------

TEMPORAL_CASES: list[tuple[str, bool]] = [
    # True — should be detected as temporal
    ("What are the latest news about OpenAI?", True),
    ("recent news on Python 3.13", True),
    ("current news about artificial intelligence", True),
    ("últimas notícias sobre inteligência artificial", True),
    ("notícias recentes sobre Python", True),
    ("what is happening today in AI?", True),
    ("atualização mais recente do Python", True),
    # False — should NOT be detected as temporal
    ("what is the capital of France", False),
    ("explain quantum computing", False),
    ("how does photosynthesis work", False),
    ("what is machine learning", False),
    ("hello there", False),
    ("o que é Python?", False),
    ("quem é Linus Torvalds?", False),
]

# ---------------------------------------------------------------------------
# Summarization guard cases — used to score the content guard in handler.
# (prompt, should_guard_block: bool)
# If True, the guard must stop before calling the LLM.
# ---------------------------------------------------------------------------

SUMMARIZATION_GUARD_CASES: list[tuple[str, bool]] = [
    # Should be blocked — no actual text to summarize
    ("summarize this text for me", True),
    ("summarize", True),
    ("tl;dr", True),
    ("give me a summary", True),
    ("summary", True),
    ("resuma", True),
    # Should NOT be blocked — enough content after stripping the trigger
    ("summarize this: " + "important word " * 10, False),
    ("tl;dr: " + "some content here " * 5, False),
]

# ---------------------------------------------------------------------------
# QA proper-noun extraction cases — used to score the N09 fallback.
# (prompt, expected_extracted_entity or None if no extraction expected)
# ---------------------------------------------------------------------------

QA_PROPER_NOUN_CASES: list[tuple[str, str | None]] = [
    # Should extract entity
    ("What is spaCy?", "spaCy"),
    ("What is FastAPI?", "FastAPI"),
    ("What is LangChain?", "LangChain"),
    ("What is Docker?", "Docker"),
    ("o que é LangChain?", "LangChain"),
    ("What is GitHub?", "GitHub"),
    ("What is OpenAI?", "OpenAI"),
    # Should NOT extract (no "what is" pattern or no proper noun)
    ("how does Python work?", None),
    ("what is the capital of France", None),
]

# ---------------------------------------------------------------------------
# Unified orchestration / DAG planning ground truth
# (prompt, expected_strategy, expected_plan_name)
# These are offline checks for the agentic deterministic planner. Keep direct
# cases obvious enough that the TF-IDF router handles them without an LLM.
# ---------------------------------------------------------------------------

ORCHESTRATION_CASES: list[tuple[str, str, str]] = [
    ("hello there", "direct", "general"),
    ("what is the capital of France", "direct", "question_answering"),
    ("calculate 15 + 7", "direct", "function_calling"),
    (
        "search for llama.cpp and summarize the findings",
        "dag",
        "on_demand_web_search_to_summarization",
    ),
    (
        "search for Python tutorials and classify the results",
        "dag",
        "on_demand_web_search_to_classification",
    ),
    (
        "calculate 7 times 8 and tell me if the result is even or odd",
        "dag",
        "on_demand_calculator_to_question_answering",
    ),
    (
        "fetch https://example.com and summarize it",
        "dag",
        "on_demand_web_fetch_to_summarization",
    ),
    (
        "look up the Wikipedia article about Brazil and tell me what it is",
        "dag",
        "on_demand_wikipedia_to_question_answering",
    ),
]

# ---------------------------------------------------------------------------
# Smoke prompts: run end-to-end against the live LLM.
# These are NOT evaluated automatically — they require human review.
# ---------------------------------------------------------------------------

SMOKE_PROMPTS: list[tuple[str, str, str]] = [
    # (prompt, expected_tool_or_intent, language)
    ("Summarise the concept of entropy in thermodynamics", "summarization", "en"),
    ("search for the latest news about Python 3.13", "web_search", "en"),
    ("what is 256 divided by 16", "calculator", "en"),
    ("look up spaCy on Wikipedia", "wikipedia", "en"),
    ("Qual é a capital do Japão?", "question_answering", "pt"),
    ("resume o conceito de entropia", "summarization", "pt"),
    ("pesquise sobre inteligência artificial", "web_search", "pt"),
]
