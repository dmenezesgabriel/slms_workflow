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
        system=("You answer questions concisely and directly. " "If you are uncertain, say so."),
        max_tokens=256,
        temperature=0.1,
    ),
    "function_calling": ModelProfile(
        model=QWEN35_08B_TEXT,
        # Tool list is injected dynamically by the handler via tool_prompt()
        system="You select and invoke a tool to fulfill the user's request.",
        max_tokens=192,
        temperature=0.0,
    ),
    "classification": ModelProfile(
        model=QWEN35_08B_TEXT,
        system=(
            "You classify user input into a concise label. "
            "Return only valid JSON matching the requested schema."
        ),
        max_tokens=192,
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
            "You are a task planner. Choose one action per step.\n"
            "Actions:\n"
            "  web_search — action_input = the search query (words only)\n"
            "  web_fetch  — action_input = https:// URL\n"
            "  wikipedia  — action_input = topic name\n"
            "  calculator — action_input = math expression like '3+4*2'\n"
            "  summarize  — action_input = 'key findings' (uses previous result)\n"
            "  classify   — action_input = category type (uses previous result)\n"
            "  answer     — action_input = the question (uses previous result)\n"
            "  final_answer — action_input = your complete answer; set is_final=true\n"
            "Once you have tool results, use final_answer immediately.\n"
            "Return only valid JSON matching the schema."
        ),
        max_tokens=256,
        temperature=0.0,
    ),
}
