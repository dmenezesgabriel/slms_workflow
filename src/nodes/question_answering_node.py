from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel

from src import tool_selection
from src.handlers.question_answering import QuestionAnsweringHandler
from src.llm_client import LLMClient
from src.model_registry import ModelProfile
from src.techniques.grounding import GroundingLayer
from src.techniques.retrieval import Retriever


class RagStore(Protocol):
    def add_text(self, contents: list[str], sources: list[str]) -> None: ...


class QuestionAnsweringNode:
    id = "question_answering"

    def __init__(
        self,
        retriever: Retriever,
        grounding_layer: GroundingLayer | None = None,
        rag_store: RagStore | None = None,
        profile: ModelProfile | None = None,
    ) -> None:
        self._handler = QuestionAnsweringHandler(
            retriever=retriever,
            grounding_layer=grounding_layer,
            profile=profile,
        )
        self._rag_store = rag_store

    def execute(self, input: str, llm: LLMClient) -> BaseModel:
        result = self._handler.handle(input, llm)

        if (
            result.retrieved_context
            and self._rag_store
            and not tool_selection.is_math_expression(input)
        ):
            self._rag_store.add_text(
                contents=[result.retrieved_context],
                sources=["retrieval_cache"],
            )

        return result.response
