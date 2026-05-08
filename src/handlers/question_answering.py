from __future__ import annotations

from pydantic import BaseModel

from src import retrieval
from src.llm_client import LLMClient, LLMRequest
from src.model_registry import MODEL_REGISTRY
from src.schemas import FinalAnswer


def _needs_retrieval(text: str) -> bool:
    return retrieval.needs_retrieval(text)


def _fetch_context(user_input: str) -> str:
    return retrieval.DEFAULT_RETRIEVER.fetch_context(user_input)


class QuestionAnsweringHandler:
    intent = "question_answering"

    def handle(self, user_input: str, llm: LLMClient) -> BaseModel:
        retrieved = _fetch_context(user_input)

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

        candidate = retrieval.candidate_answer_from_context(retrieved)
        if candidate and candidate.lower() not in result.answer.lower():
            return FinalAnswer(answer=candidate)
        return result


_handler = QuestionAnsweringHandler()
handle = _handler.handle
