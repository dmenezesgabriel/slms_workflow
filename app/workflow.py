from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel

from app import trace
from app.context import compress, extract_text
from app.handlers import HANDLER_REGISTRY
from app.llm_client import LLMClient
from app.schemas import FinalAnswer


@dataclass(frozen=True)
class Step:
    intent: str
    # {input} is substituted with the current pipeline value before calling the handler.
    # Useful for the first step when the user query needs to be framed as a tool command.
    input_format: str = "{input}"


@dataclass(frozen=True)
class Workflow:
    name: str
    description: str
    steps: tuple[Step, ...]


_MAX_STEP_INPUT_CHARS = 600


def run_workflow(workflow: Workflow, user_input: str, llm: LLMClient) -> BaseModel:
    current = user_input
    result: BaseModel = FinalAnswer(answer="")

    for i, step in enumerate(workflow.steps):
        step_input = step.input_format.format(input=current)
        # Keep the model's context window safe for processing steps.
        if i > 0 and len(step_input) > _MAX_STEP_INPUT_CHARS:
            step_input = step_input[:_MAX_STEP_INPUT_CHARS]
        trace.workflow_step(workflow.name, i + 1, step.intent, step_input)

        handler = HANDLER_REGISTRY.get(step.intent, HANDLER_REGISTRY["general"])
        result = handler(step_input, llm)

        if i < len(workflow.steps) - 1:
            raw = extract_text(result)
            current = compress(raw, query=user_input, max_sentences=5)

    return result


WORKFLOW_REGISTRY: dict[str, Workflow] = {
    "research_and_summarize": Workflow(
        name="research_and_summarize",
        description="Search the web for a topic and summarize the findings",
        steps=(
            Step("function_calling", "search for {input}"),
            Step("summarization", "summarize: {input}"),
        ),
    ),
    "fetch_and_summarize": Workflow(
        name="fetch_and_summarize",
        description="Fetch a URL and summarize its content",
        steps=(
            Step("function_calling", "fetch {input}"),
            Step("summarization", "summarize: {input}"),
        ),
    ),
    "research_and_classify": Workflow(
        name="research_and_classify",
        description="Search for information and classify the category or sentiment",
        steps=(
            Step("function_calling", "search for {input}"),
            Step("classification", "Classify the category or sentiment of this content: {input}"),
        ),
    ),
    "wiki_and_answer": Workflow(
        name="wiki_and_answer",
        description="Look up a topic on Wikipedia then answer a question about it",
        steps=(
            Step("function_calling", "look up the Wikipedia article about {input}"),
            Step("question_answering", "{input}"),
        ),
    ),
}
