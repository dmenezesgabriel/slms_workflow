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


def run(
    user_input: str,
    llm: LLMClient | None = None,
    conversation_context: str | None = None,
) -> BaseModel:
    """Unified public entrypoint used by CLI, tests, integrations, and chat."""

    llm = llm or OpenAILocalClient()
    return run_assistant(user_input, llm, conversation_context=conversation_context)


def _print_result(result: BaseModel, as_json: bool) -> None:
    print(result.model_dump_json(indent=2) if as_json else extract_text(result))


def _conversation_context(turns: list[tuple[str, str]], max_turns: int = 4) -> str:
    return "\n".join(f"User: {u}\nAssistant: {a}" for u, a in turns[-max_turns:])


def _repl(dispatch: Dispatch, llm: LLMClient, as_json: bool, use_conversation: bool) -> None:
    print("SLM assistant session. Type /exit to quit, /workflows to inspect DAG workflows.")
    turns: list[tuple[str, str]] = []
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
        context = _conversation_context(turns) if use_conversation else None
        result = (
            run(user_input, llm, conversation_context=context)
            if use_conversation
            else dispatch(user_input, llm)
        )
        answer = extract_text(result)
        print("assistant> ", end="")
        _print_result(result, as_json)
        if use_conversation:
            turns.append((user_input, answer))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Unified local SLM assistant: one prompt engine for CLI and chat"
    )
    parser.add_argument(
        "-p",
        "--prompt",
        metavar="PROMPT",
        help="Run one prompt through the unified assistant and exit",
    )
    parser.add_argument("--chat", action="store_true", help="Continue interactively after --prompt")
    parser.add_argument("--json", action="store_true", help="Print raw JSON result objects")
    parser.add_argument("--direct", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--agent", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--workflow", metavar="NAME", help=argparse.SUPPRESS)
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

    use_conversation = dispatch is run

    if args.prompt is not None:
        result = dispatch(args.prompt, llm)
        _print_result(result, args.json)
        if not args.chat:
            return

    _repl(dispatch, llm, args.json, use_conversation=use_conversation)


if __name__ == "__main__":
    main()
