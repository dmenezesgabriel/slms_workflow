"""Predefined multi-node DAG workflows and the runtime to execute them.

The node registry is configured externally (by the composition root) before
workflows are accessed. Importing this module does NOT trigger infrastructure
construction.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel

from src.graph.base import NodeRegistry, WorkflowNode
from src.graph.dag import DagNode, DagWorkflow, run_dag_workflow
from src.llm_client import LLMClient

Workflow = DagWorkflow


@dataclass(frozen=True)
class WorkflowNodeTemplate:
    id: str
    intent: str
    input_format: str = "{input}"
    depends_on: tuple[str, ...] = ()
    condition: str = "always"


@dataclass(frozen=True)
class WorkflowTemplate:
    name: str
    description: str
    nodes: tuple[WorkflowNodeTemplate, ...]
    final_node: str | None = None


@dataclass
class _WorkflowCatalogState:
    """Internal workflow catalog state.

    Keeps compatibility with the historical module-level API while narrowing
    mutable state ownership to one object.
    """

    node_registry: NodeRegistry | None = None
    workflow_registry: dict[str, DagWorkflow] | None = None

    def set_node_registry(self, registry: NodeRegistry) -> None:
        self.node_registry = registry
        self.workflow_registry = None

    def get_workflow_registry(self) -> dict[str, DagWorkflow]:
        if self.workflow_registry is None:
            self.workflow_registry = _build_workflows(self.require_node_registry())
        return self.workflow_registry

    def require_node_registry(self) -> NodeRegistry:
        if self.node_registry is None:
            raise RuntimeError("set_node_registry() must be called before building workflows")
        return self.node_registry


_STATE = _WorkflowCatalogState()


def set_node_registry(registry: NodeRegistry) -> None:
    _STATE.set_node_registry(registry)


def get_workflow_registry() -> dict[str, DagWorkflow]:
    return _STATE.get_workflow_registry()


WORKFLOW_REGISTRY = get_workflow_registry


WORKFLOW_TEMPLATES: tuple[WorkflowTemplate, ...] = (
    WorkflowTemplate(
        name="research_and_summarize",
        description="Search the web for a topic and summarize the findings",
        nodes=(
            WorkflowNodeTemplate("search", "function_calling", "search for {query}"),
            WorkflowNodeTemplate(
                "summarize",
                "summarization",
                "summarize: {search}",
                depends_on=("search",),
            ),
        ),
        final_node="summarize",
    ),
    WorkflowTemplate(
        name="fetch_and_summarize",
        description="Fetch a URL and summarize its content",
        nodes=(
            WorkflowNodeTemplate("fetch", "function_calling", "fetch {query}"),
            WorkflowNodeTemplate(
                "summarize",
                "summarization",
                "summarize: {fetch}",
                depends_on=("fetch",),
            ),
        ),
        final_node="summarize",
    ),
    WorkflowTemplate(
        name="research_and_classify",
        description="Search for information and classify the category or sentiment",
        nodes=(
            WorkflowNodeTemplate("search", "function_calling", "search for {query}"),
            WorkflowNodeTemplate(
                "classify",
                "classification",
                "Classify this retrieved content for the user topic/request ({query}). "
                "Return a concise label and mention the topic in the reason:\n{search}",
                depends_on=("search",),
            ),
        ),
        final_node="classify",
    ),
    WorkflowTemplate(
        name="plugin_demo",
        description="Demonstrate plugin-backed node execution: extract entities then score",
        nodes=(
            WorkflowNodeTemplate(
                "extract",
                "plugin_ner.default",
                "Extract named entities from: {query}",
            ),
            WorkflowNodeTemplate(
                "score",
                "plugin_scoring.default",
                "{extract}",
                depends_on=("extract",),
            ),
        ),
        final_node="score",
    ),
    WorkflowTemplate(
        name="wiki_and_answer",
        description="Look up a topic on Wikipedia then answer a question about it",
        nodes=(
            WorkflowNodeTemplate(
                "wiki",
                "function_calling",
                "look up the Wikipedia article about {query}",
            ),
            WorkflowNodeTemplate(
                "answer",
                "question_answering",
                "Context:\n{wiki}\n\nQuestion: {query}",
                depends_on=("wiki",),
            ),
        ),
        final_node="answer",
    ),
)


def _build_workflows(nr: NodeRegistry) -> dict[str, DagWorkflow]:
    return {template.name: _resolve_template(template, nr) for template in WORKFLOW_TEMPLATES}


def _resolve_template(template: WorkflowTemplate, nr: NodeRegistry) -> DagWorkflow:
    return DagWorkflow(
        name=template.name,
        description=template.description,
        nodes=tuple(_resolve_template_node(node, nr) for node in template.nodes),
        final_node=template.final_node,
    )


def _resolve_template_node(node: WorkflowNodeTemplate, nr: NodeRegistry) -> DagNode:
    return DagNode(
        id=node.id,
        node=_resolve_node(node.intent, nr),
        input_format=node.input_format,
        depends_on=node.depends_on,
        condition=node.condition,
    )


def _resolve_node(intent: str, nr: NodeRegistry) -> WorkflowNode:
    node = nr.get(intent)
    if node is None:
        raise KeyError(f"No node registered for intent {intent!r}")
    return node


def run_workflow(workflow: DagWorkflow, user_input: str, llm: LLMClient) -> BaseModel:
    """Run a named workflow.

    This compatibility wrapper keeps the public CLI/eval/features API stable
    while using the DAG executor as the single workflow runtime.
    """

    result, _trace = run_dag_workflow(workflow, user_input, llm)
    if result is None:
        from src.schemas import FinalAnswer

        return FinalAnswer(answer="No DAG node was executed for this request.")
    return result
