"""Composition root: builds ToolRegistry and NodeRegistry with all dependencies wired.

This module is the single point where concrete infrastructure is instantiated.
Importing it only loads class/functions — no infrastructure is constructed until
build_tool_registry() or build_node_registry() is called.
"""

from __future__ import annotations

from src.nodes.agent_node import AgentNode
from src.nodes.base import NodeRegistry
from src.nodes.classification_node import ClassificationNode
from src.nodes.function_calling_node import FunctionCallingNode
from src.nodes.general_node import GeneralNode
from src.nodes.image_understanding_node import ImageUnderstandingNode
from src.nodes.plugin_node import PluginNode
from src.nodes.question_answering_node import QuestionAnsweringNode
from src.nodes.summarization_node import SummarizationNode
from src.plugins.manifest import build_plugin_registry
from src.rag import HybridRAG
from src.retrievers.default import create_default_retriever
from src.techniques.grounding import _DEFAULT_LAYER as grounding_layer
from src.techniques.retrieval import Retriever
from src.tools import (
    Calculator,
    DuckDBTool,
    PlaywrightTool,
    ToolRegistry,
    WebFetch,
    WebSearch,
    Wikipedia,
)


def build_tool_registry() -> ToolRegistry:
    return ToolRegistry(
        [
            Calculator(),
            WebSearch(),
            WebFetch(),
            Wikipedia(),
            PlaywrightTool(),
            DuckDBTool(),
        ]
    )


def build_node_registry(
    tool_registry: ToolRegistry | None = None,
    retriever: Retriever | None = None,
) -> NodeRegistry:
    tool_registry = tool_registry or build_tool_registry()
    retriever = retriever or create_default_retriever()
    assert tool_registry is not None
    assert retriever is not None
    plugin_registry = build_plugin_registry()

    rag_store = HybridRAG()

    def store_retrieval_results(contents: list[str], sources: list[str]) -> None:
        rag_store.add_text(contents=contents, sources=sources)

    summarization_node = SummarizationNode()
    classification_node = ClassificationNode()
    qa_node = QuestionAnsweringNode(
        retriever=retriever,
        grounding_layer=grounding_layer,
        rag_store=store_retrieval_results,
    )

    agent_node = AgentNode(
        tool_registry=tool_registry,
        action_nodes={
            "summarize": summarization_node,
            "classify": classification_node,
            "answer": qa_node,
        },
    )

    return NodeRegistry(
        [
            summarization_node,
            qa_node,
            FunctionCallingNode(tool_registry=tool_registry),
            classification_node,
            ImageUnderstandingNode(),
            GeneralNode(),
            agent_node,
            PluginNode("ner.default", plugin_registry),
            PluginNode("scoring.default", plugin_registry),
            PluginNode("retrieval.default", plugin_registry),
            PluginNode("tool.calculator", plugin_registry),
        ]
    )
