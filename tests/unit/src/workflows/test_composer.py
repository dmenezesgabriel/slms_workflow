from __future__ import annotations

from typing import Any

from src.graph.base import NodeRegistry
from src.tools import ToolRegistry
from src.workflows.composer import DAGComposer


class _StubNode:
    def __init__(self, node_id: str) -> None:
        self.id = node_id

    def execute(self, input: str, llm: object) -> None:
        return None


class _StubTool:
    def __init__(self, name: str) -> None:
        self.name = name
        self.description = name
        self.parameters: dict[str, object] = {}

    def prompt_line(self) -> str:
        return self.name

    def execute(self, arguments: dict[str, object]) -> str:
        return ""


def _composer() -> DAGComposer:
    nodes: list[Any] = [
        _StubNode("function_calling"),
        _StubNode("question_answering"),
        _StubNode("summarization"),
        _StubNode("classification"),
        _StubNode("general"),
    ]
    tools: list[Any] = [
        _StubTool("calculator"),
        _StubTool("web_search"),
        _StubTool("wikipedia"),
        _StubTool("web_fetch"),
    ]
    node_registry = NodeRegistry(nodes)
    tool_registry = ToolRegistry(tools)
    return DAGComposer(node_registry=node_registry, tool_registry=tool_registry)


class TestProtectedBaselineComposerBehavior:
    def test_compose_builds_search_to_summarization_graph_for_follow_up_prompt(self) -> None:
        graph = _composer().compose("search for Python and summarize it")

        assert graph is not None
        assert graph.name == "on_demand_web_search_to_summarization"
        assert graph.nodes[0].input_format == "search for Python"
        assert graph.nodes[1].input_format == "summarize: {tool}"

    def test_compose_builds_wikipedia_to_question_answering_graph(self) -> None:
        graph = _composer().compose(
            "look up Ada Lovelace on Wikipedia and explain her achievements"
        )

        assert graph is not None
        assert graph.name == "on_demand_wikipedia_to_question_answering"
        assert graph.nodes[0].input_format == "look up the Wikipedia article about Ada Lovelace"
        assert graph.nodes[1].input_format == "Context:\n{tool}\n\nQuestion: {query}"
        assert graph.nodes[1].depends_on == ("tool",)

    def test_compose_builds_search_to_question_answering_graph(self) -> None:
        graph = _composer().compose("search for llama.cpp and tell me what it is")

        assert graph is not None
        assert graph.name == "on_demand_web_search_to_question_answering"
        assert graph.nodes[0].node.id == "function_calling"
        assert graph.nodes[0].input_format == "search for llama.cpp"
        assert graph.nodes[1].node.id == "question_answering"
        assert graph.nodes[1].input_format == "Context:\n{tool}\n\nQuestion: {query}"
        assert graph.nodes[1].depends_on == ("tool",)


class TestTargetImprovementComposerBehavior:
    def test_multi_clause_prompt_trims_connector_punctuation_from_tool_query(self) -> None:
        graph = _composer().compose("search for Python, then summarize it")

        assert graph is not None
        assert graph.nodes[0].input_format == "search for Python"

    def test_multi_clause_prompt_keeps_follow_up_question_answering_intent(self) -> None:
        graph = _composer().compose(
            "look up Ada Lovelace on Wikipedia, then explain her achievements"
        )

        assert graph is not None
        assert graph.name == "on_demand_wikipedia_to_question_answering"
        assert graph.nodes[0].input_format == "look up the Wikipedia article about Ada Lovelace"

    def test_search_without_processing_intent_does_not_compose_graph(self) -> None:
        graph = _composer().compose("search for python decorators")

        assert graph is None
