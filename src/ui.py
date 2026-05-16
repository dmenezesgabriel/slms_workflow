from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel
from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text

from src import trace as trace_module
from src.text_utils import extract_text

T = TypeVar("T")


@dataclass(frozen=True)
class CommandHelp:
    flags: str
    description: str


class AssistantUI:
    """Small Rich-powered terminal adapter for the unified assistant.

    The UI deliberately stays at the boundary: it formats input, output, help,
    and progress, but it does not decide routes, run tools, or inspect plans.
    """

    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console()

    def header(self, mode: str) -> None:
        title = Text("SLM Assistant", style="bold cyan")
        subtitle = Text(
            "one engine · deterministic graphs · tools · small-model planner fallback",
            style="dim",
        )
        body = Align.center(Text.assemble(title, "\n", subtitle))
        self.console.print(Panel(body, border_style="cyan", padding=(1, 2)))
        self.footer(mode)

    def footer(self, mode: str) -> None:
        cwd = Path.cwd().name
        table = Table.grid(expand=True)
        table.add_column(ratio=1)
        table.add_row(f"[dim]mode:[/] {mode}  [dim]cwd:[/] {cwd}")
        table.add_row("[dim]commands:[/] /workflows /help /exit  [dim]trace:[/] SLM_TRACE=1")
        self.console.print(table)

    def ask(self) -> str:
        return Prompt.ask("\n[bold cyan]you[/]").strip()

    def user_message(self, message: str) -> None:
        self.console.print(Panel(message, title="you", border_style="blue", expand=True))

    def assistant_message(self, result: BaseModel, *, as_json: bool = False) -> str:
        answer = result.model_dump_json(indent=2) if as_json else extract_text(result)
        title = "assistant · json" if as_json else "assistant"
        self.console.print(Panel(answer, title=title, border_style="green", expand=True))
        return extract_text(result)

    def info(self, message: str) -> None:
        self.console.print(f"[dim]{message}[/]")

    def error(self, message: str) -> None:
        self.console.print(Panel(message, title="error", border_style="red"))

    def run_with_status(self, message: str, fn: Callable[[], T]) -> T:
        with self.console.status(f"[cyan]{message}[/]", spinner="dots"):
            return fn()

    def workflows(self, workflows: Mapping[str, object]) -> None:
        table = Table(title="Available workflow graphs", border_style="cyan")
        table.add_column("name", style="bold")
        table.add_column("description")
        for name, entry in workflows.items():
            table.add_row(name, str(getattr(entry, "description", "")))
        self.console.print(table)

    def help(self, commands: list[CommandHelp]) -> None:
        self.header("help")
        table = Table(title="Usage", border_style="cyan", show_lines=False)
        table.add_column("command", style="bold green", no_wrap=True)
        table.add_column("description")
        for command in commands:
            table.add_row(command.flags, command.description)
        self.console.print(table)
        self.console.print(
            Panel(
                "Interactive mode is the default with no arguments. "
                "Use -p/--prompt for one-shot execution. "
                "All paths enter the same assistant engine.",
                title="mental model",
                border_style="magenta",
            )
        )


def _sanitize_args(tool_name: str, args: dict[str, Any]) -> str:
    if not args:
        return ""
    if len(args) == 1 and "query" in args:
        val = str(args["query"])
        if len(val) > 60:
            val = val[:57] + "..."
        return f"({val})"
    parts: list[str] = []
    for k, v in args.items():
        s = str(v)
        if len(s) > 40:
            s = s[:37] + "..."
        parts.append(f"{k}={s!r}")
    return f"({', '.join(parts)})"


_HANDLER_SPANS = frozenset(
    {
        "question_answering",
        "summarization",
        "classification",
        "general",
        "image_understanding",
    }
)


class StatusCollector:
    def __init__(self, console: Console) -> None:
        self._console = console
        self._run_id = ""
        self._subscribed = False

    def subscribe(self) -> None:
        if not self._subscribed:
            trace_module.subscribe(self._on_event)
            self._subscribed = True

    def unsubscribe(self) -> None:
        if self._subscribed:
            trace_module.unsubscribe(self._on_event)
            self._subscribed = False

    def trace_hint(self) -> str:
        if not self._run_id:
            return ""
        path = Path(f"artifacts/trace_{self._run_id}.json")
        if path.exists():
            return str(path)
        return ""

    def _on_event(self, event: str, fields: dict[str, Any]) -> None:
        if fields.get("run_id"):
            self._run_id = fields["run_id"]

        if event == "route":
            self._on_route(fields)
        elif event == "plan":
            self._on_plan(fields)
        elif event == "plan.step":
            self._on_plan_step(fields)
        elif event == "dag.exec":
            self._on_dag_exec(fields)
        elif event == "tool.call":
            self._on_tool_call(fields)
        elif event == "tool.result":
            self._on_tool_result(fields)
        elif event == "span.enter":
            self._on_span_enter(fields)

    def _render(self, message: str) -> None:
        self._console.print(f"[dim]{message}[/]")

    def _on_route(self, fields: dict[str, Any]) -> None:
        intent = fields.get("intent", "")
        reason = fields.get("reason", "")
        label = intent
        if reason:
            label += f" ({reason})"
        self._render(f"route → {label}")

    def _on_plan(self, fields: dict[str, Any]) -> None:
        name = fields.get("name", "")
        self._render(f"workflow → {name}")

    def _on_plan_step(self, fields: dict[str, Any]) -> None:
        strategy = fields.get("strategy", "")
        detail = fields.get("detail", "")
        if strategy in ("single", "composed_dag", "agent"):
            self._render(f"workflow → {detail}")

    def _on_dag_exec(self, fields: dict[str, Any]) -> None:
        node = fields.get("node", "")
        self._render(f"node → {node}")

    def _on_tool_call(self, fields: dict[str, Any]) -> None:
        tool = fields.get("tool", "")
        args = fields.get("args", {})
        summary = _sanitize_args(tool, args)
        self._render(f"calling tool: {tool}{summary}")

    def _on_tool_result(self, fields: dict[str, Any]) -> None:
        success = fields.get("success", False)
        status = "ok" if success else "failed"
        self._render(f"  tool returned ({status})")

    def _on_span_enter(self, fields: dict[str, Any]) -> None:
        name = fields.get("name", "")
        if name in _HANDLER_SPANS:
            self._render(f"synthesizing → {name}")
