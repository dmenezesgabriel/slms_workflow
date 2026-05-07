from __future__ import annotations

import argparse

from app.agent import run_agent
from app.handlers import HANDLER_REGISTRY
from app.llm_client import LLMClient
from app.providers.openai_local import OpenAILocalClient
from app.router import route_task


def run(user_input: str, llm: LLMClient | None = None):
    llm = llm or OpenAILocalClient()
    intent = route_task(user_input, llm)
    handler = HANDLER_REGISTRY.get(intent.intent, HANDLER_REGISTRY["general"])
    return handler(user_input, llm)


def _repl(llm: LLMClient, *, agent: bool) -> None:
    dispatch = run_agent if agent else run
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
    args = parser.parse_args()

    llm = OpenAILocalClient()
    dispatch = run_agent if args.agent else run

    if args.prompt:
        print(dispatch(args.prompt, llm).model_dump_json(indent=2))
        return

    _repl(llm, agent=args.agent)


if __name__ == "__main__":
    main()
