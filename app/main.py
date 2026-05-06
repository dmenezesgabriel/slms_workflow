from __future__ import annotations

from app.llm_client import LLMRequest
from app.model_registry import MODEL_REGISTRY
from app.providers.openai_local import OpenAILocalClient
from app.router import route_task
from app.schemas import (
    ClassificationResult,
    FinalAnswer,
    SummaryResult,
    ToolDecision,
)
from app.tools import execute_tool_decision


def run(user_input: str, llm: OpenAILocalClient | None = None):
    llm = llm or OpenAILocalClient()

    intent = route_task(user_input, llm)

    if intent.intent == "summarization":
        profile = MODEL_REGISTRY["summarization"]
        return llm.structured(
            LLMRequest(
                model=profile.model,
                system=profile.system,
                user=(
                    "Summarize the article between <article> and </article>.\n\n"
                    f"<article>\n{user_input}\n</article>"
                ),
                max_tokens=profile.max_tokens,
                temperature=profile.temperature,
            ),
            SummaryResult,
        )

    if intent.intent == "function_calling":
        profile = MODEL_REGISTRY["function_calling"]

        decision = llm.structured(
            LLMRequest(
                model=profile.model,
                system=profile.system,
                user=user_input,
                max_tokens=profile.max_tokens,
                temperature=profile.temperature,
            ),
            ToolDecision,
        )

        if not decision.needs_tool:
            return FinalAnswer(answer=decision.reason)

        tool_result = execute_tool_decision(decision)

        if tool_result.success:
            return FinalAnswer(
                answer=f"{tool_result.tool_name} result: {tool_result.result}"
            )

        return FinalAnswer(
            answer=(
                f"Tool execution failed for {tool_result.tool_name}: "
                f"{tool_result.error}"
            )
        )

    if intent.intent == "classification":
        profile = MODEL_REGISTRY["classification"]
        return llm.structured(
            LLMRequest(
                model=profile.model,
                system=profile.system,
                user=user_input,
                max_tokens=profile.max_tokens,
                temperature=profile.temperature,
            ),
            ClassificationResult,
        )

    if intent.intent == "image_understanding":
        return FinalAnswer(
            answer=(
                "Image understanding was detected, but image input support "
                "has not been implemented in LLMRequest yet."
            )
        )

    if intent.intent == "question_answering":
        profile = MODEL_REGISTRY["question_answering"]
        return llm.structured(
            LLMRequest(
                model=profile.model,
                system=profile.system,
                user=user_input,
                max_tokens=profile.max_tokens,
                temperature=profile.temperature,
            ),
            FinalAnswer,
        )

    if intent.intent == "unclassified":
        return FinalAnswer(answer="I could not classify this request.")

    profile = MODEL_REGISTRY["general"]
    return llm.structured(
        LLMRequest(
            model=profile.model,
            system=profile.system,
            user=user_input,
            max_tokens=profile.max_tokens,
            temperature=profile.temperature,
        ),
        FinalAnswer,
    )


if __name__ == "__main__":
    client = OpenAILocalClient()

    while True:
        user_input = input("\n> ").strip()

        if user_input in {"exit", "quit"}:
            break

        result = run(user_input, client)
        print(result.model_dump_json(indent=2))