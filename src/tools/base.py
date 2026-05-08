from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Tool(Protocol):
    name: str
    description: str
    parameters: dict[str, str]

    def execute(self, arguments: dict[str, Any]) -> str: ...

    def prompt_line(self) -> str: ...


class ToolBase:
    name: str
    description: str
    parameters: dict[str, str]

    def prompt_line(self) -> str:
        params = ", ".join(f"{k}: {v}" for k, v in self.parameters.items())
        return f"- {self.name}: {self.description}. Parameters: {{{params}}}"
