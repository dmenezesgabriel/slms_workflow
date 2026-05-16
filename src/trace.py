from __future__ import annotations

import os
import sys
import time
import uuid
from collections.abc import Callable
from typing import Any

from src.graph.trace_types import ExecutionTrace, ToolCallTrace

_ENABLED = os.getenv("SLM_TRACE", "0") == "1"
_request_id: str = ""
_run_id: str = ""
_t0: float = 0.0
_span_stack: list[str] = []
_subscribers: list[Callable[[str, dict[str, Any]], None]] = []
_current_exec_trace: ExecutionTrace | None = None
_tool_call_data: dict[str, tuple[float, dict[str, Any]]] = {}


def init() -> None:
    global _request_id, _run_id, _t0, _current_exec_trace
    _request_id = uuid.uuid4().hex[:12]
    _run_id = uuid.uuid4().hex[:12]
    _t0 = time.monotonic()
    _span_stack.clear()
    _tool_call_data.clear()
    _current_exec_trace = None


def subscribe(callback: Callable[[str, dict[str, Any]], None]) -> None:
    _subscribers.append(callback)


def unsubscribe(callback: Callable[[str, dict[str, Any]], None]) -> None:
    try:
        _subscribers.remove(callback)
    except ValueError:
        pass


def set_exec_trace(exec_trace: ExecutionTrace | None) -> None:
    global _current_exec_trace
    _current_exec_trace = exec_trace


def set_run_id(run_id: str) -> None:
    global _run_id
    _run_id = run_id


def get_run_id() -> str:
    return _run_id


def _emit(event: str, **fields: Any) -> None:
    elapsed = (time.monotonic() - _t0) * 1000

    enriched = dict(fields, run_id=_run_id)
    for cb in _subscribers:
        try:
            cb(event, dict(enriched))
        except Exception:
            pass

    if not _ENABLED:
        return
    parts = " ".join(f"{k}={v!r}" for k, v in fields.items())
    print(
        f"[trace] {event} {parts} rid={_request_id} elapsed={elapsed:.1f}ms",
        file=sys.stderr,
        flush=True,
    )


def span_enter(name: str) -> None:
    _span_stack.append(name)
    _emit("span.enter", name=name, depth=len(_span_stack))


def span_exit(name: str) -> None:
    if _span_stack and _span_stack[-1] == name:
        _span_stack.pop()
    _emit("span.exit", name=name, depth=len(_span_stack))


def route(intent: str, confidence: float, reason: str) -> None:
    _emit("route", intent=intent, confidence=round(confidence, 4), reason=reason)


def retrieval(source: str, query: str) -> None:
    _emit("retrieval", source=source, query=query[:80])


def tool_call(tool_name: str, arguments: dict[str, Any]) -> None:
    _tool_call_data[tool_name] = (time.monotonic(), arguments)
    _emit("tool.call", tool=tool_name, args=arguments)


def tool_result(tool_name: str, success: bool, result: str) -> None:
    elapsed_ms = 0.0
    args: dict[str, Any] = {}
    data = _tool_call_data.pop(tool_name, None)
    if data is not None:
        start_time, args = data
        elapsed_ms = (time.monotonic() - start_time) * 1000

    _emit("tool.result", tool=tool_name, success=success, result=result[:120])

    if _current_exec_trace is not None:
        _current_exec_trace.add_tool_call(
            ToolCallTrace(
                tool_name=tool_name,
                arguments=args,
                result_summary=result[:120],
                success=success,
                elapsed_ms=round(elapsed_ms, 1),
                error=None if success else result[:120],
            )
        )


def plan(strategy: str, name: str, reason: str) -> None:
    _emit("plan", strategy=strategy, name=name, reason=reason[:80])


def agent_step(step_n: int, thought: str, action: str, action_input: str) -> None:
    _emit("agent.step", n=step_n, action=action, thought=thought[:80], input=action_input[:80])


def agent_final(steps_taken: int) -> None:
    _emit("agent.final", steps=steps_taken)


def ner(text: str, entities: list[tuple[str, str]]) -> None:
    _emit("ner", text=text, entities=entities)


def fast_path(kind: str, detail: str) -> None:
    _emit("fast_path", kind=kind, detail=detail[:80])


def handler(intent: str, user_input: str) -> None:
    _emit("handler", intent=intent, input=user_input[:80])


def llm_request(model: str, max_tokens: int) -> None:
    _emit("llm.request", model=model, max_tokens=max_tokens)


def llm_response(model: str, success: bool, error: str | None = None) -> None:
    if error:
        _emit("llm.response", model=model, success=success, error=error[:80])
    else:
        _emit("llm.response", model=model, success=success)


def grounding_check(check_name: str, passed: bool, score: float) -> None:
    _emit("grounding.check", check=check_name, passed=passed, score=round(score, 4))


def grounding_result(answer: str, route: str, score: float) -> None:
    _emit("grounding.result", answer=answer[:60], route=route, score=round(score, 4))


def plan_step(strategy: str, detail: str) -> None:
    _emit("plan.step", strategy=strategy, detail=detail[:80])


def composition(composed: bool, reason: str) -> None:
    _emit("composition", composed=composed, reason=reason[:80])


def dag_exec_node(node: str, intent: str) -> None:
    _emit("dag.exec", node=node, intent=intent)


def dag_skip_node(node: str, condition: str) -> None:
    _emit("dag.skip", node=node, condition=condition)
