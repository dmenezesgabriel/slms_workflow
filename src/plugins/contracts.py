from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class PluginSpec:
    name: str
    kind: str
    version: str
    description: str = ""


@dataclass(frozen=True)
class PluginInput:
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PluginOutput:
    data: dict[str, Any] = field(default_factory=dict)


class Plugin(Protocol):
    spec: PluginSpec

    def execute(self, input: PluginInput) -> PluginOutput: ...
