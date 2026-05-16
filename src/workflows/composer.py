"""On-demand DAG composition from deterministic signal extraction."""

from __future__ import annotations

import re

from src import trace
from src.graph.base import NodeRegistry
from src.graph.dag import GraphNode, WorkflowGraph
from src.lexical_scoring import best_lexical_match
from src.schemas import ToolDecision
from src.text_normalization import normalize_text
from src.tool_selection import deterministic_tool, extract_math, ner_tool
from src.tools import ToolRegistry

_ENTITY_LOOKUP_RE = re.compile(
    r"\b(tell me about|who is|who was|what is(?!\s+(?:the\s+)?capital\s+of)|"
    r"what are|about|latest|current|recent|news|quem é|quem foi|o que é|sobre)\b",
    re.IGNORECASE,
)
_TOOL_OR_WORK_RE = re.compile(
    r"\b(search|fetch|wikipedia|look up|calculate|compute|latest|news|url|https?://)\b",
    re.IGNORECASE,
)
_CLAUSE_SPLIT_RE = re.compile(
    r"\s*(?:,\s*then\s+|\b(?:and then|then|after that|also|and|e|então|depois)\b\s+)", re.IGNORECASE
)
_PROCESSING_PROTOTYPES: dict[str, tuple[str, ...]] = {
    "summarization": (
        "summarize it",
        "summarize this",
        "make this shorter",
        "shorten this",
        "resuma isso",
        "resuma este texto",
    ),
    "classification": (
        "classify this",
        "classify this sentiment",
        "categorize this",
        "label this",
        "detect sentiment",
    ),
    "question_answering": (
        "tell me about it",
        "tell me if the result is even or odd",
        "tell me if it is even or odd",
        "explain it",
        "answer this",
        "what does this mean",
        "why is that",
        "how does it work",
        "explain her achievements",
        "me explique",
    ),
}
_PROCESSING_THRESHOLD = 0.48


class DAGComposer:
    def __init__(
        self,
        node_registry: NodeRegistry,
        tool_registry: ToolRegistry,
    ) -> None:
        self._node_registry = node_registry
        self._tool_registry = tool_registry

    def compose(self, user_input: str) -> WorkflowGraph | None:
        """Return an on-demand WorkflowGraph, or None if the input does not map to one."""
        tool_clause, follow_up_clause = _split_tool_and_processing_clauses(user_input)
        decision = self._deterministic_decision(tool_clause)
        if decision is None or not decision.needs_tool or decision.tool_name == "none":
            trace.composition(False, "no deterministic tool decision")
            return None

        if decision.reason.startswith("NER") and not _ENTITY_LOOKUP_RE.search(tool_clause):
            trace.composition(False, "NER decision but no entity lookup signal")
            return None

        processing_intent = self._processing_intent(
            user_input, tool_clause, follow_up_clause, decision
        )
        if processing_intent is None:
            trace.composition(False, "no processing intent matched")
            return None

        tool_input = _tool_step_input(decision, tool_clause=tool_clause)
        if tool_input is None:
            trace.composition(False, f"no tool step input for {decision.tool_name}")
            return None

        tool_node = self._node_registry.get("function_calling")
        final_node = self._node_registry.get(processing_intent)
        if tool_node is None or final_node is None:
            trace.composition(False, "missing node(s) in registry")
            return None

        name = f"on_demand_{decision.tool_name}_to_{processing_intent}"
        trace.composition(True, name)
        return WorkflowGraph(
            name=name,
            description="Composed from the user's prompt by the unified assistant.",
            nodes=(
                GraphNode("tool", tool_node, _literal_format(tool_input)),
                GraphNode(
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
        if expression is not None and "calculator" in self._tool_registry:
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

    def _processing_intent(
        self,
        user_input: str,
        tool_clause: str,
        follow_up_clause: str | None,
        decision: ToolDecision,
    ) -> str | None:
        candidate_text = follow_up_clause or user_input
        intent = _best_processing_intent(candidate_text)
        if intent is not None:
            return intent
        if decision.tool_name == "calculator" and follow_up_clause is not None:
            return "question_answering"
        if follow_up_clause is None and tool_clause == user_input:
            return None
        return _best_processing_intent(user_input)


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


def _tool_step_input(decision: ToolDecision, *, tool_clause: str | None = None) -> str | None:
    if decision.tool_name == "calculator":
        expression = decision.arguments.get("expression")
        return f"calculate {expression}" if isinstance(expression, str) else None
    if decision.tool_name == "web_search":
        query = _clean_tool_query(decision.arguments.get("query"), tool_clause=tool_clause)
        return f"search for {query}" if query else None
    if decision.tool_name == "wikipedia":
        query = _clean_tool_query(decision.arguments.get("query"), tool_clause=tool_clause)
        return f"look up the Wikipedia article about {query}" if query else None
    if decision.tool_name == "web_fetch":
        url = decision.arguments.get("url")
        return f"fetch {url}" if isinstance(url, str) else None
    return None


def _clean_tool_query(value: object, *, tool_clause: str | None = None) -> str:
    if isinstance(value, str):
        cleaned = value.strip(" .,?!")
        if cleaned:
            return cleaned
    if tool_clause is None:
        return ""
    return tool_clause.strip(" .,?!")


def _best_processing_intent(text: str) -> str | None:
    normalized = normalize_text(text, strip_punctuation=True)
    best_intent: str | None = None
    best_score = 0.0
    for intent, prototypes in _PROCESSING_PROTOTYPES.items():
        match = best_lexical_match(normalized, list(prototypes))
        if match is not None and match.score > best_score:
            best_intent = intent
            best_score = match.score
    return best_intent if best_score >= _PROCESSING_THRESHOLD else None


def _split_tool_and_processing_clauses(user_input: str) -> tuple[str, str | None]:
    text = user_input.strip()
    for match in _CLAUSE_SPLIT_RE.finditer(text):
        tool_clause = text[: match.start()].strip()
        follow_up_clause = text[match.end() :].strip()
        if not tool_clause or not follow_up_clause:
            continue
        if not _TOOL_OR_WORK_RE.search(tool_clause):
            continue
        if _best_processing_intent(follow_up_clause) is None:
            continue
        return tool_clause, follow_up_clause
    return text, None


def _literal_format(text: str) -> str:
    return text.replace("{", "{{").replace("}", "}}")


def _looks_like_ambiguous_multi_tool_task(user_input: str) -> bool:
    tool_clause, follow_up_clause = _split_tool_and_processing_clauses(user_input)
    return bool(_TOOL_OR_WORK_RE.search(tool_clause) and follow_up_clause)
