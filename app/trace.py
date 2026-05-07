from __future__ import annotations

import os
import sys
import time
from typing import Any

_ENABLED = os.getenv("SLM_TRACE", "0") == "1"


def _emit(event: str, **fields: Any) -> None:
    if not _ENABLED:
        return
    parts = " ".join(f"{k}={v!r}" for k, v in fields.items())
    print(f"[trace] {event} {parts}", file=sys.stderr, flush=True)


def route(intent: str, confidence: float, reason: str) -> None:
    _emit("route", intent=intent, confidence=round(confidence, 4), reason=reason)


def handler_start(intent: str) -> float:
    _emit("handler.start", intent=intent)
    return time.monotonic()


def handler_end(intent: str, t0: float) -> None:
    _emit("handler.end", intent=intent, elapsed_ms=round((time.monotonic() - t0) * 1000))


def tool_call(tool_name: str, arguments: dict) -> None:
    _emit("tool.call", tool=tool_name, args=arguments)


def tool_result(tool_name: str, success: bool, result: str) -> None:
    _emit("tool.result", tool=tool_name, success=success, result=result[:120])


def agent_step(step_n: int, thought: str, action: str, action_input: str) -> None:
    _emit("agent.step", n=step_n, action=action, thought=thought[:80], input=action_input[:80])


def agent_final(steps_taken: int) -> None:
    _emit("agent.final", steps=steps_taken)
