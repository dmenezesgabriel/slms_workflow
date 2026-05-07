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
