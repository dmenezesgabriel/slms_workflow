from __future__ import annotations

from pydantic import BaseModel

from src import trace
from src.context import compress, extract_text
from src.handlers import HANDLER_REGISTRY
from src.llm_client import LLMClient, LLMRequest
from src.model_registry import MODEL_REGISTRY
from src.schemas import AgentStep, FinalAnswer, ToolDecision
from src.tool_selection import extract_math
from src.tools import TOOL_ACTIONS, execute, execute_action, is_tool_action

_MAX_CONTEXT_STEPS = 2


def _execute_step(
    step: AgentStep,
    history: list[tuple[AgentStep, str]],
    llm: LLMClient,
) -> str:
    action = step.action
    inp = step.action_input

    # Direct tool dispatch — no LLM needed for these. The shared adapter keeps
    # agent orchestration independent from concrete tool argument names.
    r = execute_action(action, inp)

    if r is not None:
        from src.scoring import score_result

        if r.success:
            s = score_result(r.result)
            if not s.is_usable:
                trace.agent_step(0, f"low quality result ({s.reason})", action, inp)
            return r.result
        return f"Error: {r.error}"

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


_TOOL_ACTIONS = TOOL_ACTIONS


def _build_prompt(user_input: str, steps: list[tuple[AgentStep, str]]) -> str:
    lines = [f"Task: {user_input}"]

    if steps:
        lines.append("\nPrevious steps:")
        for i, (step, result) in enumerate(steps[-_MAX_CONTEXT_STEPS:], 1):
            truncated = result[:200] + "..." if len(result) > 200 else result
            lines.append(f"  {i}. {step.action}({step.action_input!r}) → {truncated}")

        if any(is_tool_action(s.action) for s, _ in steps):
            lines.append("\nYou have tool results. Use final_answer with your complete answer now.")

    lines.append("\nNext action:")
    return "\n".join(lines)


def _force_answer(user_input: str, steps: list[tuple[AgentStep, str]], llm: LLMClient) -> BaseModel:
    """Synthesize a final answer from accumulated step results using the QA handler."""
    ctx = compress(" ".join(r for _, r in steps), query=user_input, max_sentences=6)
    result = HANDLER_REGISTRY["question_answering"](f"{user_input}\n\nContext: {ctx}", llm)
    return FinalAnswer(answer=extract_text(result))


def run_agent(user_input: str, llm: LLMClient, max_steps: int = 5) -> BaseModel:
    # Fast path: deterministic math — avoids the model mis-routing arithmetic to web_search
    from src.tools import TOOL_REGISTRY

    expression = extract_math(user_input)
    if expression is not None and "calculator" in TOOL_REGISTRY:
        calc_result = execute(
            ToolDecision(
                needs_tool=True,
                tool_name="calculator",
                arguments={"expression": expression},
                reason="Deterministic math extraction.",
            )
        )
        if calc_result.success:
            seed = AgentStep(
                thought="Computed from math expression.",
                action="calculator",
                action_input=expression,
                is_final=False,
            )
            return _force_answer(user_input, [(seed, calc_result.result)], llm)

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

        if step.action == "final_answer":
            trace.agent_final(step_n + 1)
            return FinalAnswer(answer=step.action_input)

        # Deterministic escape: if we already have tool results and the model
        # keeps calling tools instead of synthesizing, force a QA synthesis step.
        has_tool_results = any(is_tool_action(s.action) for s, _ in steps)
        if has_tool_results and is_tool_action(step.action):
            trace.agent_final(step_n + 1)
            return _force_answer(user_input, steps, llm)

        result = _execute_step(step, steps, llm)
        steps.append((step, result))

    trace.agent_final(len(steps))
    if steps:
        return _force_answer(user_input, steps, llm)
    return FinalAnswer(answer="Agent could not complete the task.")
