from __future__ import annotations

from pydantic import BaseModel

from src import grounding, retrieval, tool_selection
from src.llm_client import LLMClient, LLMRequest
from src.model_registry import MODEL_REGISTRY
from src.rag import store_retrieval_results
from src.schemas import FinalAnswer


def _needs_rag_context(text: str) -> bool:
    if tool_selection.is_math_expression(text):
        return False
    if tool_selection.is_calculator_intent(text):
        return False
    return True


def _fetch_context(user_input: str) -> str:
    return retrieval.DEFAULT_RETRIEVER.fetch_context(user_input)


class QuestionAnsweringHandler:
    intent = "question_answering"

    def handle(self, user_input: str, llm: LLMClient) -> BaseModel:
        retrieved = _fetch_context(user_input)

        if retrieved and _needs_rag_context(user_input):
            store_retrieval_results([retrieved], ["retrieval_cache"])

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

        if retrieved:
            gr = grounding.evaluate(result.answer, retrieved)
            answer = gr.answer if gr.route in ("accept", "healed_accept") else result.answer
            return FinalAnswer(answer=answer)

        return result


_handler = QuestionAnsweringHandler()
handle = _handler.handle
