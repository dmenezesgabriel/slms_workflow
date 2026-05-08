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
from src.router import route_task
from src.schemas import IntentName, ToolDecision
from src.tool_selection import deterministic_tool, extract_math, ner_tool
from src.tools import TOOL_REGISTRY

Strategy = Literal["direct", "dag", "agent"]


@dataclass(frozen=True)
class AssistantPlan:
    """Execution plan selected by the unified assistant front door."""

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


def run_direct(user_input: str, llm: LLMClient) -> BaseModel:
    """Run the classic one-shot router + handler path."""

    intent = route_task(user_input, llm)
    handler = HANDLER_REGISTRY.get(intent.intent, HANDLER_REGISTRY["general"])
    return handler(user_input, llm)


def run_assistant(
    user_input: str,
    llm: LLMClient,
    conversation_context: str | None = None,
) -> BaseModel:
    """Unified entrypoint: plan, compose, and run the best controlled path.

    The public UX is agent-like (one prompt in, one answer out), while this
    function keeps the backstage deterministic and composable: simple prompts go
    through the classic router, obvious compound requests become on-demand DAGs,
    and ambiguous tool-heavy tasks fall back to the small planner agent.

    Planning is always based on the current user turn so conversation history
    does not dilute deterministic routing. When the selected path is a pure
    language task, the recent conversation is appended as context for synthesis.
    """

    plan = plan_assistant(user_input, llm)
    trace.plan(plan.strategy, plan.name, plan.reason)

    if plan.strategy == "dag" and plan.graph is not None:
        return run_dag_workflow(plan.graph, user_input, llm)
    if plan.strategy == "agent":
        return run_agent(user_input, llm)
    return run_direct_with_intent(
        _contextualize(user_input, conversation_context, plan.intent), llm, plan.intent
    )


def run_direct_with_intent(
    user_input: str, llm: LLMClient, intent: IntentName | None = None
) -> BaseModel:
    if intent is None:
        return run_direct(user_input, llm)
    handler = HANDLER_REGISTRY.get(intent, HANDLER_REGISTRY["general"])
    return handler(user_input, llm)


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


def plan_assistant(user_input: str, llm: LLMClient) -> AssistantPlan:
    """Select a controlled execution strategy for a prompt."""

    stripped = user_input.strip()
    if not stripped:
        return AssistantPlan("direct", "empty", "Empty prompt.", intent="unclassified")

    graph = compose_dag_workflow(stripped)
    if graph is not None:
        return AssistantPlan(
            "dag",
            graph.name,
            "Deterministic DAG composed from tool request and answer-processing follow-up.",
            graph=graph,
        )

    if _looks_like_ambiguous_multi_tool_task(stripped):
        return AssistantPlan("agent", "agent", "Ambiguous multi-step tool task.")

    intent = route_task(stripped, llm)
    return AssistantPlan("direct", intent.intent, intent.reason, intent=intent.intent)


def compose_dag_workflow(user_input: str) -> DagWorkflow | None:
    """Build a deterministic on-demand DAG from a single user prompt."""

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


def compose_workflow(user_input: str) -> DagWorkflow | None:
    """Deprecated compatibility alias for DAG composition."""

    return compose_dag_workflow(user_input)


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

    # NER can lazy-load a large spaCy model; only pay that cost for prompts that
    # look entity-centric enough to benefit from a retrieval workflow.
    return ner_tool(user_input) if _ENTITY_LOOKUP_RE.search(user_input) else None


def _processing_intent(user_input: str, decision: ToolDecision) -> str | None:
    if _CLASSIFY_RE.search(user_input):
        return "classification"
    if _SUMMARIZE_RE.search(user_input):
        return "summarization"

    if decision.tool_name == "calculator":
        # Plain math should stay a fast direct tool call. Math plus follow-up
        # ("is it even?", "what does it mean?", "explain") needs synthesis.
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
    """Make arbitrary tool text safe for str.format used by DAG nodes."""

    return text.replace("{", "{{").replace("}", "}}")


def _looks_like_ambiguous_multi_tool_task(user_input: str) -> bool:
    # If the deterministic composer cannot isolate a safe workflow but the user
    # clearly asks for tool work plus another operation, let the agent planner try.
    return bool(_TOOL_OR_WORK_RE.search(user_input) and _FOLLOW_UP_RE.search(user_input))


Dispatch = Callable[[str, LLMClient], BaseModel]
