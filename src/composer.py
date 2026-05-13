"""On-demand DAG composition from deterministic signal extraction."""

from __future__ import annotations

import re

from src import trace
from src.dag import DagNode, DagWorkflow
from src.handlers import NODE_REGISTRY
from src.schemas import ToolDecision
from src.tool_selection import deterministic_tool, extract_math, ner_tool
from src.tools import TOOL_REGISTRY

_SUMMARIZE_RE = re.compile(r"\b(summar(?:y|ize|ise)|tl;dr|resum[aoe])\b", re.IGNORECASE)
_CLASSIFY_RE = re.compile(
    r"\b(classif(?:y|ique|icar)|categor(?:y|ize|ise)|label|sentiment|categoria)\b",
    re.IGNORECASE,
)
_ANSWER_RE = re.compile(
    r"\b(tell me|explain|answer|what|why|how|who|where|when|meaning|means|"
    r"me (?:diga|diz|fala|fale|conte|explica|explique)|o que|quem|onde|quando|por que)\b",
    re.IGNORECASE,
)
_ENTITY_LOOKUP_RE = re.compile(
    r"\b(tell me about|who is|who was|what is(?!\s+(?:the\s+)?capital\s+of)|"
    r"what are|about|latest|current|recent|news|quem é|quem foi|o que é|sobre)\b",
    re.IGNORECASE,
)
_FOLLOW_UP_RE = re.compile(
    r"\b(?:and|then|after that|also|,| e | então | depois )\b.*"
    r"\b(summar(?:y|ize|ise)|classif(?:y|ique|icar)|categor(?:y|ize|ise)|label|"
    r"sentiment|tell me|explain|answer|what|why|how|who|where|when|means|meaning|"
    r"resum[aoe]|categoria)\b",
    re.IGNORECASE,
)
_FOLLOW_UP_SPLIT_RE = re.compile(
    r"\s+(?:and|then|after that|also|,|e|então|depois)\s+"
    r"(?=(?:tell me|explain|answer|summar(?:y|ize|ise)|classif(?:y|ique|icar)|"
    r"categor(?:y|ize|ise)|label|what|why|how|who|where|when|resum[aoe]|categoria)\b)",
    re.IGNORECASE,
)
_TOOL_OR_WORK_RE = re.compile(
    r"\b(search|fetch|wikipedia|look up|calculate|compute|latest|news|url|https?://)\b",
    re.IGNORECASE,
)


class DAGComposer:
    def compose(self, user_input: str) -> DagWorkflow | None:
        """Return an on-demand DagWorkflow, or None if the input does not map to one."""
        decision = self._deterministic_decision(user_input)
        if decision is None or not decision.needs_tool or decision.tool_name == "none":
            trace.composition(False, "no deterministic tool decision")
            return None

        if decision.reason.startswith("NER") and not _ENTITY_LOOKUP_RE.search(user_input):
            trace.composition(False, "NER decision but no entity lookup signal")
            return None

        processing_intent = self._processing_intent(user_input, decision)
        if processing_intent is None:
            trace.composition(False, "no processing intent matched")
            return None

        tool_input = _tool_step_input(decision)
        if tool_input is None:
            trace.composition(False, f"no tool step input for {decision.tool_name}")
            return None

        tool_node = NODE_REGISTRY.get("function_calling")
        final_node = NODE_REGISTRY.get(processing_intent)
        if tool_node is None or final_node is None:
            trace.composition(False, "missing node(s) in registry")
            return None

        name = f"on_demand_{decision.tool_name}_to_{processing_intent}"
        trace.composition(True, name)
        return DagWorkflow(
            name=name,
            description="Composed from the user's prompt by the unified assistant.",
            nodes=(
                DagNode("tool", tool_node, _literal_format(tool_input)),
                DagNode(
                    "final",
                    final_node,
                    _processing_format(processing_intent, "tool"),
                    depends_on=("tool",),
                ),
            ),
            final_node="final",
        )

    def _deterministic_decision(self, user_input: str) -> ToolDecision | None:
        expression = extract_math(user_input)
        if expression is not None and "calculator" in TOOL_REGISTRY:
            return ToolDecision(
                needs_tool=True,
                tool_name="calculator",
                arguments={"expression": expression},
                reason="Deterministic math extraction.",
            )

        decision = deterministic_tool(user_input)
        if decision is not None:
            return decision

        return ner_tool(user_input) if _ENTITY_LOOKUP_RE.search(user_input) else None

    def _processing_intent(self, user_input: str, decision: ToolDecision) -> str | None:
        if _CLASSIFY_RE.search(user_input):
            return "classification"
        if _SUMMARIZE_RE.search(user_input):
            return "summarization"

        if decision.tool_name == "calculator":
            return "question_answering" if _FOLLOW_UP_RE.search(user_input) else None

        if _ANSWER_RE.search(user_input) or _FOLLOW_UP_RE.search(user_input):
            return "question_answering"

        return None


def _processing_format(intent: str, input_key: str) -> str:
    value = "{" + input_key + "}"
    if intent == "summarization":
        return f"summarize: {value}"
    if intent == "classification":
        return (
            f"Classify this content according to the user's request ({{query}}). "
            f"Return a concise label and mention the topic in the reason:\n{value}"
        )
    return f"Context:\n{value}\n\nQuestion: {{query}}"


def _tool_step_input(decision: ToolDecision) -> str | None:
    if decision.tool_name == "calculator":
        expression = decision.arguments.get("expression")
        return f"calculate {expression}" if isinstance(expression, str) else None
    if decision.tool_name == "web_search":
        query = _clean_follow_up(decision.arguments.get("query"))
        return f"search for {query}" if query else None
    if decision.tool_name == "wikipedia":
        query = _clean_follow_up(decision.arguments.get("query"))
        return f"look up the Wikipedia article about {query}" if query else None
    if decision.tool_name == "web_fetch":
        url = decision.arguments.get("url")
        return f"fetch {url}" if isinstance(url, str) else None
    return None


def _clean_follow_up(value: object) -> str:
    if not isinstance(value, str):
        return ""
    first = _FOLLOW_UP_SPLIT_RE.split(value.strip(), maxsplit=1)[0]
    return first.strip(" .?!")


def _literal_format(text: str) -> str:
    return text.replace("{", "{{").replace("}", "}}")


def _looks_like_ambiguous_multi_tool_task(user_input: str) -> bool:
    return bool(_TOOL_OR_WORK_RE.search(user_input) and _FOLLOW_UP_RE.search(user_input))


_composer = DAGComposer()


def compose_dag(user_input: str) -> DagWorkflow | None:
    return _composer.compose(user_input)
