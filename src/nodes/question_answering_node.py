from __future__ import annotations

from typing import Callable

from pydantic import BaseModel

from src.handlers.question_answering import QuestionAnsweringHandler
from src.llm_client import LLMClient
from src.techniques.grounding import GroundingLayer
from src.techniques.retrieval import Retriever

RagStoreCallback = Callable[[list[str], list[str]], None]


class QuestionAnsweringNode:
    id = "question_answering"

    def __init__(
        self,
        retriever: Retriever,
        grounding_layer: GroundingLayer | None = None,
        rag_store: RagStoreCallback | None = None,
    ) -> None:
        self._handler = QuestionAnsweringHandler(
            retriever=retriever,
            grounding_layer=grounding_layer,
            rag_store=rag_store,
        )

    def execute(self, input: str, llm: LLMClient) -> BaseModel:
        return self._handler.handle(input, llm)
