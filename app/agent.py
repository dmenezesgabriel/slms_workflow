from __future__ import annotations

from pydantic import BaseModel

from app import trace
from app.context import compress, extract_text
from app.handlers import HANDLER_REGISTRY
from app.llm_client import LLMClient, LLMRequest
from app.model_registry import MODEL_REGISTRY
from app.schemas import AgentStep, FinalAnswer, ToolDecision
from app.tools import execute

_MAX_CONTEXT_STEPS = 2


def _execute_step(
    step: AgentStep,
    history: list[tuple[AgentStep, str]],
    llm: LLMClient,
) -> str:
    action = step.action
    inp = step.action_input

    # Direct tool dispatch — no LLM needed for these
    if action == "web_search":
        r = execute(
            ToolDecision(
                needs_tool=True, tool_name="web_search", arguments={"query": inp}, reason=""
            )
        )
    elif action == "web_fetch":
        r = execute(
            ToolDecision(needs_tool=True, tool_name="web_fetch", arguments={"url": inp}, reason="")
        )
    elif action == "wikipedia":
        r = execute(
            ToolDecision(
                needs_tool=True, tool_name="wikipedia", arguments={"query": inp}, reason=""
            )
        )
    elif action == "calculator":
        r = execute(
            ToolDecision(
                needs_tool=True, tool_name="calculator", arguments={"expression": inp}, reason=""
            )
        )
    else:
        r = None

    if r is not None:
        return r.result if r.success else f"Error: {r.error}"

    # Processing actions consume the previous step's result as context
    prev = history[-1][1] if history else ""
    ctx = compress(prev, query=inp, max_sentences=5) if prev else ""

    if action == "summarize":
        result = HANDLER_REGISTRY["summarization"](f"summarize:\n\n{ctx}", llm)
        return extract_text(result)
    if action == "classify":
        result = HANDLER_REGISTRY["classification"](ctx, llm)
        return extract_text(result)
    if action == "answer":
        query = f"{inp}\n\nContext: {ctx}" if ctx else inp
        result = HANDLER_REGISTRY["question_answering"](query, llm)
        return extract_text(result)

    return prev


_TOOL_ACTIONS = {"web_search", "web_fetch", "wikipedia", "calculator"}


def _build_prompt(user_input: str, steps: list[tuple[AgentStep, str]]) -> str:
    lines = [f"Task: {user_input}"]

    if steps:
        lines.append("\nPrevious steps:")
        for i, (step, result) in enumerate(steps[-_MAX_CONTEXT_STEPS:], 1):
            truncated = result[:200] + "..." if len(result) > 200 else result
            lines.append(f"  {i}. {step.action}({step.action_input!r}) → {truncated}")

        if any(s.action in _TOOL_ACTIONS for s, _ in steps):
            lines.append("\nYou have tool results. Use final_answer with your complete answer now.")

    lines.append("\nNext action:")
    return "\n".join(lines)


def _force_answer(user_input: str, steps: list[tuple[AgentStep, str]], llm: LLMClient) -> BaseModel:
    """Synthesize a final answer from accumulated step results using the QA handler."""
    ctx = compress(" ".join(r for _, r in steps), query=user_input, max_sentences=6)
    result = HANDLER_REGISTRY["question_answering"](f"{user_input}\n\nContext: {ctx}", llm)
    return FinalAnswer(answer=extract_text(result))


def run_agent(user_input: str, llm: LLMClient, max_steps: int = 5) -> BaseModel:
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

        if step.is_final or step.action == "final_answer":
            trace.agent_final(step_n + 1)
            return FinalAnswer(answer=step.action_input)

        # Deterministic escape: if we already have tool results and the model
        # keeps calling tools instead of synthesizing, force a QA synthesis step.
        has_tool_results = any(s.action in _TOOL_ACTIONS for s, _ in steps)
        if has_tool_results and step.action in _TOOL_ACTIONS:
            trace.agent_final(step_n + 1)
            return _force_answer(user_input, steps, llm)

        result = _execute_step(step, steps, llm)
        steps.append((step, result))

    trace.agent_final(len(steps))
    if steps:
        return _force_answer(user_input, steps, llm)
    return FinalAnswer(answer="Agent could not complete the task.")
