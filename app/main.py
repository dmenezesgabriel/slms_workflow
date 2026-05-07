from __future__ import annotations

import argparse
import sys
from typing import Callable

from pydantic import BaseModel

from app.agent import run_agent
from app.fuzzy import match_workflow
from app.handlers import HANDLER_REGISTRY
from app.llm_client import LLMClient
from app.providers.openai_local import OpenAILocalClient
from app.router import route_task
from app.workflow import WORKFLOW_REGISTRY, run_workflow


def run(user_input: str, llm: LLMClient | None = None) -> BaseModel:
    llm = llm or OpenAILocalClient()
    intent = route_task(user_input, llm)
    handler = HANDLER_REGISTRY.get(intent.intent, HANDLER_REGISTRY["general"])
    return handler(user_input, llm)


def _repl(dispatch: Callable[[str, LLMClient], BaseModel], llm: LLMClient) -> None:
    while True:
        try:
            user_input = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not user_input or user_input in {"exit", "quit"}:
            break
        print(dispatch(user_input, llm).model_dump_json(indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="SLM workflow")
    parser.add_argument("prompt", nargs="?", help="Run a single prompt and exit")
    parser.add_argument("--agent", action="store_true", help="Use multi-step agentic loop")
    parser.add_argument("--workflow", metavar="NAME", help="Run a predefined workflow by name")
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
        dispatch: Callable[[str, LLMClient], BaseModel] = lambda inp, client: run_workflow(
            selected, inp, client
        )
    elif args.agent:
        dispatch = run_agent
    else:
        dispatch = run

    if args.prompt:
        print(dispatch(args.prompt, llm).model_dump_json(indent=2))
        return

    _repl(dispatch, llm)


if __name__ == "__main__":
    main()
