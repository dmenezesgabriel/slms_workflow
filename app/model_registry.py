from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelProfile:
    model: str
    system: str
    max_tokens: int = 256
    temperature: float = 0.0


QWEN35_08B_TEXT = "qwen3.5-0.8b-text"
QWEN35_08B_VISION = "qwen3.5-0.8b-vision"


MODEL_REGISTRY = {
    "router": ModelProfile(
        model=QWEN35_08B_TEXT,
        system=(
            "You are a strict intent classifier. "
            "Return only valid JSON matching the requested schema."
        ),
        max_tokens=128,
        temperature=0.0,
    ),
    "summarization": ModelProfile(
        model=QWEN35_08B_TEXT,
        system=(
            "You summarize only the text provided by the user. "
            "Do not invent topics, titles, names, countries, companies, or claims. "
            "If the input is too short or incomplete, say that in the JSON. "
            "Preserve the original topic, names, numbers, dates, decisions, and action items."
        ),
        max_tokens=384,
        temperature=0.0,
    ),
    "question_answering": ModelProfile(
        model=QWEN35_08B_TEXT,
        system=(
            "You answer questions concisely and directly. "
            "If you are uncertain, say so."
        ),
        max_tokens=256,
        temperature=0.1,
    ),
    "function_calling": ModelProfile(
        model=QWEN35_08B_TEXT,
        system=(
            "You extract tool calls from user requests. "
            "Available tools: calculator. "
            "ALWAYS use the calculator tool for ANY arithmetic. "
            "Convert natural language math to a Python expression: "
            "'plus'->'+', 'minus'->'-', 'times'->'*', 'divided by'->'/', 'squared'->'**2'. "
            "Return needs_tool=true, tool_name='calculator', arguments={'expression': '<python expr>'}. "
            "Return needs_tool=false only if the request has no arithmetic at all. "
            "Return only valid JSON matching the requested schema."
        ),
        max_tokens=192,
        temperature=0.0,
    ),
    "classification": ModelProfile(
        model=QWEN35_08B_TEXT,
        system=(
            "You classify user input into a concise label. "
            "Return only valid JSON matching the requested schema."
        ),
        max_tokens=128,
        temperature=0.0,
    ),
    "image_understanding": ModelProfile(
        model=QWEN35_08B_VISION,
        system="You answer questions about images concisely and accurately.",
        max_tokens=256,
        temperature=0.0,
    ),
    "general": ModelProfile(
        model=QWEN35_08B_TEXT,
        system=(
            "You are a concise multilingual local assistant running on a small model. "
            "Answer clearly and avoid unnecessary verbosity."
        ),
        max_tokens=256,
        temperature=0.2,
    ),
    "agent": ModelProfile(
        model=QWEN35_08B_TEXT,
        system=(
            "You are a minimal task planner. Given a task and previous steps, "
            "decide the next action. "
            "Available actions: question_answering, summarization, function_calling, "
            "classification, final_answer. "
            "Use final_answer with a complete answer when the task is done. "
            "Return only valid JSON matching the schema."
        ),
        max_tokens=192,
        temperature=0.0,
    ),
}