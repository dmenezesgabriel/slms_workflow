from __future__ import annotations

import argparse
import sys

from pydantic import BaseModel

from src.agent import run_agent
from src.context import extract_text
from src.fuzzy import match_workflow
from src.llm_client import LLMClient
from src.orchestrator import Dispatch, run_assistant, run_direct
from src.providers.openai_local import OpenAILocalClient
from src.workflow import WORKFLOW_REGISTRY, run_workflow


def run(user_input: str, llm: LLMClient | None = None) -> BaseModel:
    """Unified public entrypoint used by CLI, tests, and integrations."""

    llm = llm or OpenAILocalClient()
    return run_assistant(user_input, llm)


def _print_result(result: BaseModel, as_json: bool) -> None:
    print(result.model_dump_json(indent=2) if as_json else extract_text(result))


def _repl(dispatch: Dispatch, llm: LLMClient, as_json: bool) -> None:
    print("SLM agent session. Type /exit to quit, /workflows to list workflows.")
    while True:
        try:
            user_input = input("\nyou> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not user_input or user_input in {"/exit", "exit", "quit"}:
            break
        if user_input == "/workflows":
            for name, entry in WORKFLOW_REGISTRY.items():
                print(f"  {name}: {entry.description}")
            continue
        print("assistant> ", end="")
        _print_result(dispatch(user_input, llm), as_json)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Unified local SLM agent with deterministic on-demand workflows"
    )
    parser.add_argument("prompt", nargs="?", help="Run a single prompt and exit")
    parser.add_argument("--json", action="store_true", help="Print raw JSON result objects")
    parser.add_argument(
        "--direct", action="store_true", help="Bypass orchestration and use router+handler"
    )
    parser.add_argument("--agent", action="store_true", help="Force the multi-step agentic loop")
    parser.add_argument("--workflow", metavar="NAME", help="Force a predefined workflow by name")
    parser.add_argument(
        "--list-workflows", action="store_true", help="List available workflows and exit"
    )
    args = parser.parse_args()

    if args.list_workflows:
        for name, entry in WORKFLOW_REGISTRY.items():
            print(f"  {name}: {entry.description}")
        sys.exit(0)

    llm = OpenAILocalClient()

    if args.workflow:
        resolved = match_workflow(args.workflow, WORKFLOW_REGISTRY)
        if resolved != args.workflow and resolved is not None:
            print(f"Resolved workflow {args.workflow!r} → {resolved!r}")
        selected = WORKFLOW_REGISTRY.get(resolved or "")
        if selected is None:
            print(f"Unknown workflow: {args.workflow!r}", file=sys.stderr)
            print(f"Available: {', '.join(WORKFLOW_REGISTRY)}", file=sys.stderr)
            sys.exit(1)
        dispatch: Dispatch = lambda inp, client: run_workflow(selected, inp, client)
    elif args.agent:
        dispatch = run_agent
    elif args.direct:
        dispatch = run_direct
    else:
        dispatch = run

    if args.prompt:
        _print_result(dispatch(args.prompt, llm), args.json)
        return

    _repl(dispatch, llm, args.json)


if __name__ == "__main__":
    main()
