from __future__ import annotations

from pydantic import BaseModel

from app.handlers import HANDLER_REGISTRY
from app.llm_client import LLMClient, LLMRequest
from app.model_registry import MODEL_REGISTRY
from app.schemas import AgentStep, FinalAnswer
from app import trace

_MAX_CONTEXT_STEPS = 2  # how many past steps to feed back — keeps prompts small for SLMs


def _build_prompt(user_input: str, steps: list[tuple[AgentStep, str]]) -> str:
    lines = [f"Task: {user_input}"]

    if steps:
        lines.append("\nPrevious steps:")
        for i, (step, result) in enumerate(steps[-_MAX_CONTEXT_STEPS:], 1):
            truncated = result[:200] + "..." if len(result) > 200 else result
            lines.append(f"  {i}. {step.action}({step.action_input!r}) → {truncated}")

    lines.append("\nDecide the next action.")
    return "\n".join(lines)


def run_agent(user_input: str, llm: LLMClient, max_steps: int = 4) -> BaseModel:
    steps: list[tuple[AgentStep, str]] = []
    profile = MODEL_REGISTRY["agent"]

    for step_n in range(max_steps):
        step = llm.structured(
            LLMRequest(
                model=profile.model,
                system=profile.system,
                user=_build_prompt(user_input, steps),
                max_tokens=profile.max_tokens,
                temperature=profile.temperature,
            ),
            AgentStep,
        )
        trace.agent_step(step_n + 1, step.thought, step.action, step.action_input)

        if step.is_final:
            trace.agent_final(step_n + 1)
            return FinalAnswer(answer=step.action_input)

        handler = HANDLER_REGISTRY.get(step.action, HANDLER_REGISTRY["general"])
        result = handler(step.action_input, llm)
        steps.append((step, result.model_dump_json()))

    trace.agent_final(len(steps))
    if steps:
        return FinalAnswer(answer=steps[-1][1])

    return FinalAnswer(answer="Agent could not complete the task.")
