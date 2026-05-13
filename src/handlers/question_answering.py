from __future__ import annotations

from typing import Callable

from pydantic import BaseModel

from src import tool_selection, trace
from src.llm_client import LLMClient, LLMRequest
from src.model_registry import MODEL_REGISTRY
from src.schemas import FinalAnswer
from src.techniques.grounding import GroundingLayer
from src.techniques.retrieval import Retriever

RagStoreCallback = Callable[[list[str], list[str]], None]


class QuestionAnsweringHandler:
    intent = "question_answering"

    def __init__(
        self,
        retriever: Retriever,
        grounding_layer: GroundingLayer | None = None,
        rag_store: RagStoreCallback | None = None,
    ) -> None:
        self._retriever = retriever
        self._grounding = grounding_layer
        self._rag_store = rag_store

    def handle(self, user_input: str, llm: LLMClient) -> BaseModel:
        trace.handler("question_answering", user_input)
        trace.span_enter("question_answering")
        retrieved = self._retriever.fetch_context(user_input)

        if retrieved and self._rag_store and not tool_selection.is_math_expression(user_input):
            self._rag_store([retrieved], ["retrieval_cache"])

        user_message = (
            f"Context:\n{retrieved}\n\nQuestion: {user_input}" if retrieved else user_input
        )

        profile = MODEL_REGISTRY["question_answering"]
        result = llm.structured(
            LLMRequest(
                model=profile.model,
                system=profile.system,
                user=user_message,
                max_tokens=profile.max_tokens,
                temperature=profile.temperature,
            ),
            FinalAnswer,
        )

        if retrieved and self._grounding:
            gr = self._grounding.evaluate(result.answer, retrieved)
            answer = gr.answer if gr.route in ("accept", "healed_accept") else result.answer
            trace.span_exit("question_answering")
            return FinalAnswer(answer=answer)

        trace.span_exit("question_answering")
        return result
