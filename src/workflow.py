from __future__ import annotations

from pydantic import BaseModel

from src.bootstrap import DEFAULT_REGISTRY
from src.dag import DagNode, DagWorkflow, run_dag_workflow
from src.llm_client import LLMClient
from src.nodes.base import WorkflowNode

# Backwards-compatible names for callers that still import Workflow. Internally,
# predefined workflows are DAGs now; a linear workflow is just a DAG where each
# node depends on the previous one.
Workflow = DagWorkflow


def run_workflow(workflow: DagWorkflow, user_input: str, llm: LLMClient) -> BaseModel:
    """Run a named workflow.

    This compatibility wrapper keeps the public CLI/eval/features API stable
    while using the DAG executor as the single workflow runtime.
    """

    result, _trace = run_dag_workflow(workflow, user_input, llm)
    return result


def _node(intent: str) -> WorkflowNode:
    node = DEFAULT_REGISTRY.get(intent)
    if node is None:
        raise KeyError(f"No node registered for intent {intent!r}")
    return node


WORKFLOW_REGISTRY: dict[str, DagWorkflow] = {
    "research_and_summarize": DagWorkflow(
        name="research_and_summarize",
        description="Search the web for a topic and summarize the findings",
        nodes=(
            DagNode("search", _node("function_calling"), "search for {query}"),
            DagNode(
                "summarize", _node("summarization"), "summarize: {search}", depends_on=("search",)
            ),
        ),
        final_node="summarize",
    ),
    "fetch_and_summarize": DagWorkflow(
        name="fetch_and_summarize",
        description="Fetch a URL and summarize its content",
        nodes=(
            DagNode("fetch", _node("function_calling"), "fetch {query}"),
            DagNode(
                "summarize", _node("summarization"), "summarize: {fetch}", depends_on=("fetch",)
            ),
        ),
        final_node="summarize",
    ),
    "research_and_classify": DagWorkflow(
        name="research_and_classify",
        description="Search for information and classify the category or sentiment",
        nodes=(
            DagNode("search", _node("function_calling"), "search for {query}"),
            DagNode(
                "classify",
                _node("classification"),
                "Classify this retrieved content for the user topic/request ({query}). "
                "Return a concise label and mention the topic in the reason:\n{search}",
                depends_on=("search",),
            ),
        ),
        final_node="classify",
    ),
    "plugin_demo": DagWorkflow(
        name="plugin_demo",
        description="Demonstrate plugin-backed node execution: extract entities then score",
        nodes=(
            DagNode(
                "extract",
                _node("plugin_ner.default"),
                "Extract named entities from: {query}",
            ),
            DagNode(
                "score",
                _node("plugin_scoring.default"),
                "{extract}",
                depends_on=("extract",),
            ),
        ),
        final_node="score",
    ),
    "wiki_and_answer": DagWorkflow(
        name="wiki_and_answer",
        description="Look up a topic on Wikipedia then answer a question about it",
        nodes=(
            DagNode(
                "wiki", _node("function_calling"), "look up the Wikipedia article about {query}"
            ),
            DagNode(
                "answer",
                _node("question_answering"),
                "Context:\n{wiki}\n\nQuestion: {query}",
                depends_on=("wiki",),
            ),
        ),
        final_node="answer",
    ),
}
