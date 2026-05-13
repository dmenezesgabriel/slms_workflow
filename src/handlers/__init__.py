from __future__ import annotations

from src.nodes.agent_node import AgentNode
from src.nodes.base import NodeRegistry
from src.nodes.classification_node import ClassificationNode
from src.nodes.function_calling_node import FunctionCallingNode
from src.nodes.general_node import GeneralNode
from src.nodes.image_understanding_node import ImageUnderstandingNode
from src.nodes.question_answering_node import QuestionAnsweringNode
from src.nodes.summarization_node import SummarizationNode
from src.rag import create_default_rag
from src.retrievers.default import create_default_retriever
from src.techniques.grounding import _DEFAULT_LAYER as _grounding_layer

_rag_store = create_default_rag()
_default_retriever = create_default_retriever()


def _store_retrieval_results(contents: list[str], sources: list[str]) -> None:
    _rag_store.add_text(contents=contents, sources=sources)


# NodeRegistry: the pluggable technique registry.
# Every technique is a WorkflowNode that can be added, removed, or replaced
# without modifying the DAG executor or the registry itself.
# Plugin-backed nodes are composed in src.bootstrap.DEFAULT_REGISTRY.
NODE_REGISTRY = NodeRegistry(
    [
        SummarizationNode(),
        QuestionAnsweringNode(
            retriever=_default_retriever,
            grounding_layer=_grounding_layer,
            rag_store=_store_retrieval_results,
        ),
        FunctionCallingNode(),
        ClassificationNode(),
        ImageUnderstandingNode(),
        GeneralNode(),
        AgentNode(),
    ]
)
