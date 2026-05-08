from __future__ import annotations

from typing import Sequence

from pydantic import BaseModel

from src.handlers.base import Handler
from src.handlers.classification import ClassificationHandler
from src.handlers.function_calling import FunctionCallingHandler
from src.handlers.general import GeneralHandler
from src.handlers.image_understanding import ImageUnderstandingHandler
from src.handlers.question_answering import QuestionAnsweringHandler
from src.handlers.summarization import SummarizationHandler
from src.llm_client import LLMClient


class HandlerRegistry:
    def __init__(self, handlers: Sequence[Handler]) -> None:
        self._handlers: dict[str, Handler] = {h.intent: h for h in handlers}

    def get(self, intent: str) -> Handler:
        return self._handlers.get(intent, self._handlers["general"])

    def dispatch(self, intent: str, user_input: str, llm: LLMClient) -> BaseModel:
        return self.get(intent).handle(user_input, llm)


HANDLER_REGISTRY = HandlerRegistry(
    [
        SummarizationHandler(),
        QuestionAnsweringHandler(),
        FunctionCallingHandler(),
        ClassificationHandler(),
        ImageUnderstandingHandler(),
        GeneralHandler(),
    ]
)
