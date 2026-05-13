from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class NodeTrace:
    node_id: str
    intent: str
    input_: str
    output: str
    elapsed_ms: float
    error: str | None = None


@dataclass
class ExecutionTrace:
    workflow_name: str
    nodes: dict[str, NodeTrace] = field(default_factory=dict)
