from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel

from src import trace
from src.llm_client import LLMClient, LLMRequest
from src.model_registry import MODEL_REGISTRY, ModelProfile
from src.schemas import FinalAnswer
from src.techniques.grounding import GroundingLayer
from src.techniques.retrieval import Retriever


@dataclass(frozen=True)
class QuestionAnsweringResult:
    response: BaseModel
    retrieved_context: str = ""


class QuestionAnsweringHandler:
    intent = "question_answering"

    def __init__(
        self,
        retriever: Retriever,
        grounding_layer: GroundingLayer | None = None,
        profile: ModelProfile | None = None,
    ) -> None:
        self._retriever = retriever
        self._grounding = grounding_layer
        self._profile = profile or MODEL_REGISTRY["question_answering"]

    def handle(self, user_input: str, llm: LLMClient) -> QuestionAnsweringResult:
        trace.handler("question_answering", user_input)
        trace.span_enter("question_answering")
        retrieved = self._retriever.fetch_context(user_input)

        user_message = (
            f"Context:\n{retrieved}\n\nQuestion: {user_input}" if retrieved else user_input
        )

        result = llm.structured(
            LLMRequest(
                model=self._profile.model,
                system=self._profile.system,
                user=user_message,
                max_tokens=self._profile.max_tokens,
                temperature=self._profile.temperature,
            ),
            FinalAnswer,
        )

        if retrieved and self._grounding:
            gr = self._grounding.evaluate(result.answer, retrieved)
            answer = gr.answer if gr.route in ("accept", "healed_accept") else result.answer
            trace.span_exit("question_answering")
            return QuestionAnsweringResult(
                response=FinalAnswer(answer=answer),
                retrieved_context=retrieved,
            )

        trace.span_exit("question_answering")
        return QuestionAnsweringResult(response=result, retrieved_context=retrieved)
