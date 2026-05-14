from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from pydantic import BaseModel

CompressFn = Callable[[str, str], str]  # (text, query) -> compressed_str
ExtractFn = Callable[[BaseModel], str]  # (result) -> text
ConditionEvaluator = Callable[[str, str], bool]  # (condition_name, user_input) -> bool


@dataclass
class ExecutionContext:
    query: str
    _compress: CompressFn = field(repr=False)
    _extract: ExtractFn = field(repr=False)
    outputs: dict[str, str] = field(default_factory=dict)
    results: dict[str, BaseModel] = field(default_factory=dict)
    _current: str = field(init=False)

    def __post_init__(self) -> None:
        self._current = self.query

    def record(self, node_id: str, result: BaseModel) -> None:
        text = self._extract(result)
        self.results[node_id] = result
        self.outputs[node_id] = text
        self._current = self._compress(text, self.query)

    def render(self, input_format: str) -> str:
        """Render a node input_format string with {query}, {input}, and {node_id} placeholders."""
        values = _FormatValues({"query": self.query, "input": self._current})
        values.update(self.outputs)
        return input_format.format_map(values)

    @property
    def current(self) -> str:
        return self._current

    def last_result(self) -> BaseModel | None:
        if not self.results:
            return None
        return next(reversed(self.results.values()))


class _FormatValues(dict[str, str]):
    def __missing__(self, key: str) -> str:
        return ""
