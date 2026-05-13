from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel
from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text

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
            "one engine · deterministic DAGs · tools · small-model planner fallback",
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
        table = Table(title="Available DAG workflows", border_style="cyan")
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
