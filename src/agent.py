from __future__ import annotations

from pydantic import BaseModel

from src import trace
from src.graph.base import WorkflowNode
from src.llm_client import LLMClient, LLMRequest
from src.model_registry import MODEL_REGISTRY, ModelProfile
from src.schemas import AgentStep, FinalAnswer, ToolDecision
from src.text_utils import compress, extract_text
from src.tool_selection import extract_math
from src.tools import ToolRegistry

_MAX_CONTEXT_STEPS = 2


class Agent:
    def __init__(
        self,
        tool_registry: ToolRegistry,
        max_steps: int = 5,
        action_nodes: dict[str, WorkflowNode] | None = None,
        profile: ModelProfile | None = None,
    ) -> None:
        self._max_steps = max_steps
        self._tool_registry = tool_registry
        self._action_nodes = action_nodes or {}
        self._profile = profile or MODEL_REGISTRY["agent"]

    def run(self, user_input: str, llm: LLMClient) -> BaseModel:
        trace.handler("agent", user_input)

        expression = extract_math(user_input)
        if expression is not None and "calculator" in self._tool_registry:
            calc_result = self._tool_registry.execute(
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
                return self._force_answer(user_input, [(seed, calc_result.result)], llm)

        steps: list[tuple[AgentStep, str]] = []

        for step_n in range(self._max_steps):
            step = llm.structured(
                LLMRequest(
                    model=self._profile.model,
                    system=self._profile.system,
                    user=self._build_prompt(user_input, steps),
                    max_tokens=self._profile.max_tokens,
                    temperature=self._profile.temperature,
                ),
                AgentStep,
            )
            trace.agent_step(step_n + 1, step.thought, step.action, step.action_input)

            if step.action == "final_answer":
                trace.agent_final(step_n + 1)
                return FinalAnswer(answer=step.action_input)

            has_tool_results = any(self._tool_registry.is_action(s.action) for s, _ in steps)
            if has_tool_results and self._tool_registry.is_action(step.action):
                trace.agent_final(step_n + 1)
                return self._force_answer(user_input, steps, llm)

            result = self._execute_step(step, steps, llm)
            steps.append((step, result))

        trace.agent_final(len(steps))
        if steps:
            return self._force_answer(user_input, steps, llm)
        return FinalAnswer(answer="Agent could not complete the task.")

    def _execute_step(
        self,
        step: AgentStep,
        history: list[tuple[AgentStep, str]],
        llm: LLMClient,
    ) -> str:
        from src.techniques.scoring import score_result

        action = step.action
        inp = step.action_input

        r = self._tool_registry.execute_action(action, inp)

        if r is not None:
            if r.success:
                s = score_result(r.result)
                if not s.is_usable:
                    trace.agent_step(0, f"low quality result ({s.reason})", action, inp)
                return r.result
            return f"Error: {r.error}"

        node = self._action_nodes.get(action)
        if node is not None:
            prev = history[-1][1] if history else ""
            ctx = compress(prev, query=inp, max_sentences=5) if prev else ""
            node_input = _format_action_input(action, inp, ctx)
            result = node.execute(node_input, llm)
            return extract_text(result)

        return history[-1][1] if history else ""

    def _build_prompt(self, user_input: str, steps: list[tuple[AgentStep, str]]) -> str:
        lines = [f"Task: {user_input}"]

        if steps:
            lines.append("\nPrevious steps:")
            for i, (step, result) in enumerate(steps[-_MAX_CONTEXT_STEPS:], 1):
                truncated = result[:200] + "..." if len(result) > 200 else result
                lines.append(f"  {i}. {step.action}({step.action_input!r}) → {truncated}")

            if any(self._tool_registry.is_action(s.action) for s, _ in steps):
                lines.append(
                    "\nYou have tool results. Use final_answer with your complete answer now."
                )

        lines.append("\nNext action:")
        return "\n".join(lines)

    def _force_answer(
        self, user_input: str, steps: list[tuple[AgentStep, str]], llm: LLMClient
    ) -> BaseModel:
        node = self._action_nodes.get("answer")
        if node is not None:
            ctx = compress(" ".join(r for _, r in steps), query=user_input, max_sentences=6)
            result = node.execute(f"{user_input}\n\nContext: {ctx}", llm)
            return FinalAnswer(answer=extract_text(result))
        return FinalAnswer(answer="")


def _format_action_input(action: str, inp: str, ctx: str) -> str:
    if action == "summarize":
        return f"summarize:\n\n{ctx}"
    if action == "answer" and ctx:
        return f"{inp}\n\nContext: {ctx}"
    return inp


def run_agent(
    user_input: str,
    llm: LLMClient,
    tool_registry: ToolRegistry,
    max_steps: int = 5,
    action_nodes: dict[str, WorkflowNode] | None = None,
    profile: ModelProfile | None = None,
) -> BaseModel:
    return Agent(
        tool_registry=tool_registry,
        max_steps=max_steps,
        action_nodes=action_nodes,
        profile=profile,
    ).run(user_input, llm)
