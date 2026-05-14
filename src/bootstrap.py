"""Composition root: builds ToolRegistry and NodeRegistry with all dependencies wired.

This module is the single point where concrete infrastructure is instantiated.
Importing it only loads class/functions — no infrastructure is constructed until
build_tool_registry() or build_node_registry() is called.
"""

from __future__ import annotations

from typing import Mapping

from src.graph.base import NodeRegistry
from src.handlers.classification import ClassificationHandler
from src.handlers.function_calling import FunctionCallingHandler
from src.handlers.general import GeneralHandler
from src.handlers.image_understanding import ImageUnderstandingHandler
from src.handlers.summarization import SummarizationHandler
from src.llm_client import LLMClient
from src.model_registry import MODEL_REGISTRY, ModelProfile
from src.nodes.agent_node import AgentNode
from src.nodes.plugin_node import PluginNode
from src.nodes.question_answering_node import QuestionAnsweringNode
from src.plugins.manifest import build_plugin_registry
from src.providers.openai_local import OpenAILocalClient
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


def build_llm_client() -> LLMClient:
    return OpenAILocalClient()


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
    model_profiles: Mapping[str, ModelProfile] | None = None,
) -> NodeRegistry:
    tool_registry = tool_registry or build_tool_registry()
    retriever = retriever or create_default_retriever()
    assert tool_registry is not None
    assert retriever is not None
    plugin_registry = build_plugin_registry()
    profiles = model_profiles or MODEL_REGISTRY

    rag_store = HybridRAG()

    summarization_node = SummarizationHandler(profile=profiles["summarization"])
    classification_node = ClassificationHandler(profile=profiles["classification"])
    qa_node = QuestionAnsweringNode(
        retriever=retriever,
        grounding_layer=grounding_layer,
        rag_store=rag_store,
        profile=profiles["question_answering"],
    )

    agent_node = AgentNode(
        tool_registry=tool_registry,
        action_nodes={
            "summarize": summarization_node,
            "classify": classification_node,
            "answer": qa_node,
        },
        profile=profiles["agent"],
    )

    return NodeRegistry(
        [
            summarization_node,
            qa_node,
            FunctionCallingHandler(
                tool_registry=tool_registry,
                profile=profiles["function_calling"],
            ),
            classification_node,
            ImageUnderstandingHandler(profile=profiles["image_understanding"]),
            GeneralHandler(profile=profiles["general"]),
            agent_node,
            PluginNode("ner.default", plugin_registry),
            PluginNode("scoring.default", plugin_registry),
            PluginNode("retrieval.default", plugin_registry),
            PluginNode("tool.calculator", plugin_registry),
        ]
    )
