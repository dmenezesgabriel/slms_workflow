from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Literal

from pydantic import BaseModel

from src import trace
from src.agent import run_agent
from src.dag import DagNode, DagWorkflow, run_dag_workflow
from src.handlers import HANDLER_REGISTRY
from src.llm_client import LLMClient
from src.patterns import RECOMMENDATION_RE as _RECOMMENDATION_RE
from src.router import route_task
from src.schemas import IntentName, ToolDecision
from src.tool_selection import deterministic_tool, extract_math, ner_tool
from src.tools import TOOL_REGISTRY

Strategy = Literal["direct", "dag", "agent"]


@dataclass(frozen=True)
class AssistantPlan:
    strategy: Strategy
    name: str
    reason: str
    intent: IntentName | None = None
    graph: DagWorkflow | None = None


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


class Orchestrator:
    def run(
        self,
        user_input: str,
        llm: LLMClient,
        conversation_context: str | None = None,
    ) -> BaseModel:
        plan = self.plan(user_input, llm)
        trace.plan(plan.strategy, plan.name, plan.reason)

        if plan.strategy == "dag" and plan.graph is not None:
            return run_dag_workflow(plan.graph, user_input, llm)
        if plan.strategy == "agent":
            return run_agent(user_input, llm)
        return self.run_direct_with_intent(
            _contextualize(user_input, conversation_context, plan.intent), llm, plan.intent
        )

    def plan(self, user_input: str, llm: LLMClient) -> AssistantPlan:
        stripped = user_input.strip()
        if not stripped:
            return AssistantPlan("direct", "empty", "Empty prompt.", intent="unclassified")

        graph = self.compose_dag(stripped)
        if graph is not None:
            return AssistantPlan(
                "dag",
                graph.name,
                "Deterministic DAG composed from tool request and answer-processing follow-up.",
                graph=graph,
            )

        if _looks_like_ambiguous_multi_tool_task(stripped):
            return AssistantPlan("agent", "agent", "Ambiguous multi-step tool task.")

        if _RECOMMENDATION_RE.search(stripped):
            return AssistantPlan(
                "direct",
                "question_answering",
                "Deterministic recommendation/question pattern.",
                intent="question_answering",
            )

        intent = route_task(stripped, llm)
        return AssistantPlan("direct", intent.intent, intent.reason, intent=intent.intent)

    def run_direct(self, user_input: str, llm: LLMClient) -> BaseModel:
        intent = route_task(user_input, llm)
        return HANDLER_REGISTRY.dispatch(intent.intent, user_input, llm)

    def run_direct_with_intent(
        self, user_input: str, llm: LLMClient, intent: IntentName | None = None
    ) -> BaseModel:
        if intent is None:
            return self.run_direct(user_input, llm)
        return HANDLER_REGISTRY.dispatch(intent, user_input, llm)

    def compose_dag(self, user_input: str) -> DagWorkflow | None:
        decision = _deterministic_decision_for_planning(user_input)
        if decision is None or not decision.needs_tool or decision.tool_name == "none":
            return None

        if decision.reason.startswith("NER") and not _ENTITY_LOOKUP_RE.search(user_input):
            return None

        processing_intent = _processing_intent(user_input, decision)
        if processing_intent is None:
            return None

        tool_input = _tool_step_input(decision)
        if tool_input is None:
            return None

        return DagWorkflow(
            name=f"on_demand_{decision.tool_name}_to_{processing_intent}",
            description="Composed from the user's prompt by the unified assistant.",
            nodes=(
                DagNode("tool", "function_calling", _literal_format(tool_input)),
                DagNode(
                    "final",
                    processing_intent,
                    _processing_format_for_dag(processing_intent, "tool"),
                    depends_on=("tool",),
                ),
            ),
            final_node="final",
        )


_orchestrator = Orchestrator()


def run_assistant(
    user_input: str,
    llm: LLMClient,
    conversation_context: str | None = None,
) -> BaseModel:
    return _orchestrator.run(user_input, llm, conversation_context)


def run_direct(user_input: str, llm: LLMClient) -> BaseModel:
    return _orchestrator.run_direct(user_input, llm)


def run_direct_with_intent(
    user_input: str, llm: LLMClient, intent: IntentName | None = None
) -> BaseModel:
    return _orchestrator.run_direct_with_intent(user_input, llm, intent)


def plan_assistant(user_input: str, llm: LLMClient) -> AssistantPlan:
    return _orchestrator.plan(user_input, llm)


def compose_dag_workflow(user_input: str) -> DagWorkflow | None:
    return _orchestrator.compose_dag(user_input)


def compose_workflow(user_input: str) -> DagWorkflow | None:
    return compose_dag_workflow(user_input)


def _contextualize(
    user_input: str,
    conversation_context: str | None,
    intent: IntentName | None,
) -> str:
    if not conversation_context:
        return user_input
    if intent not in {"question_answering", "general", "classification", "summarization"}:
        return user_input
    return (
        "Recent conversation context:\n"
        f"{conversation_context}\n\n"
        f"Current user request: {user_input}"
    )


def _deterministic_decision_for_planning(user_input: str) -> ToolDecision | None:
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


def _processing_intent(user_input: str, decision: ToolDecision) -> str | None:
    if _CLASSIFY_RE.search(user_input):
        return "classification"
    if _SUMMARIZE_RE.search(user_input):
        return "summarization"

    if decision.tool_name == "calculator":
        return "question_answering" if _FOLLOW_UP_RE.search(user_input) else None

    if _ANSWER_RE.search(user_input) or _FOLLOW_UP_RE.search(user_input):
        return "question_answering"

    return None


def _processing_format_for_dag(intent: str, dependency_id: str) -> str:
    return _processing_format_with_input(intent, dependency_id)


def _processing_format_with_input(intent: str, input_key: str) -> str:
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


Dispatch = Callable[[str, LLMClient], BaseModel]
