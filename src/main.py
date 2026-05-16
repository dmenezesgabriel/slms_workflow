from __future__ import annotations

import argparse
import re
import sys

from pydantic import BaseModel

from src import trace
from src.agent import run_agent
from src.bootstrap import build_llm_client, build_node_registry, build_tool_registry
from src.lexical_scoring import best_lexical_match, token_overlap_score
from src.llm_client import LLMClient
from src.model_registry import apply_model_overrides, ensure_model_available, known_model_aliases
from src.router import Router
from src.techniques.fuzzy import match_workflow
from src.text_normalization import tokenize
from src.text_utils import extract_text
from src.ui import AssistantUI, CommandHelp, StatusCollector
from src.workflows.catalog import get_workflow_registry, run_workflow, set_node_registry
from src.workflows.orchestrator import Dispatch, Orchestrator

_orchestrator: Orchestrator | None = None


def _get_orchestrator() -> Orchestrator:
    global _orchestrator
    if _orchestrator is None:
        tool_registry = build_tool_registry()
        node_registry = build_node_registry(tool_registry=tool_registry)
        _orchestrator = Orchestrator(node_registry=node_registry, tool_registry=tool_registry)
    return _orchestrator


def run(
    user_input: str,
    llm: LLMClient | None = None,
    conversation_context: str | None = None,
) -> BaseModel:
    """Unified public entrypoint used by CLI, tests, integrations, and chat."""

    trace.init()
    trace.span_enter("request")
    llm = llm or build_llm_client()
    result = _get_orchestrator().run(user_input, llm, conversation_context=conversation_context)
    trace.span_exit("request")
    return result


def _print_result(result: BaseModel, as_json: bool, ui: AssistantUI | None = None) -> str:
    if as_json:
        print(result.model_dump_json(indent=2))
        return extract_text(result)
    if ui is not None:
        return ui.assistant_message(result)
    answer = extract_text(result)
    print(answer)
    return answer


_EXPLICIT_CONTEXT_RE = re.compile(
    r"\b(previous|earlier|above|last answer|you said|you mentioned|as you said|that you|"
    r"continue|tell me more|explain more|same topic)\b",
    re.IGNORECASE,
)
_PRONOUN_FOLLOW_UP_RE = re.compile(r"\b(it|its|they|them|that|this)\b", re.IGNORECASE)
_EXPLICIT_CONTEXT_PROTOTYPES = (
    "tell me more",
    "explain more",
    "continue",
    "same topic",
    "what about its history",
    "what about them",
)
_FOLLOW_UP_PRONOUNS = {"it", "its", "they", "them", "that", "this"}
_AMBIGUOUS_DEICTIC_PRONOUNS = {"that", "this"}
_FOLLOW_UP_STOPWORDS = {
    "what",
    "about",
    "tell",
    "me",
    "more",
    "explain",
    "continue",
    "please",
    "its",
    "it",
    "they",
    "them",
    "that",
    "this",
}


def _follow_up_content_tokens(user_input: str) -> set[str]:
    return {
        token
        for token in tokenize(user_input)
        if token not in _FOLLOW_UP_STOPWORDS and len(token) > 2
    }


def _follow_up_signal_score(user_input: str) -> float:
    match = best_lexical_match(user_input, list(_EXPLICIT_CONTEXT_PROTOTYPES))
    return 0.0 if match is None else match.score


def _should_use_conversation_context(user_input: str, turns: list[tuple[str, str]]) -> bool:
    if not turns:
        return False
    if _EXPLICIT_CONTEXT_RE.search(user_input) or _follow_up_signal_score(user_input) >= 0.72:
        return True

    tokens = tokenize(user_input)
    if len(tokens) > 8 or _PRONOUN_FOLLOW_UP_RE.search(user_input) is None:
        return False

    pronouns = {token for token in tokens if token in _FOLLOW_UP_PRONOUNS}
    content_tokens = _follow_up_content_tokens(user_input)
    if not content_tokens:
        return False
    if pronouns and pronouns.issubset(_AMBIGUOUS_DEICTIC_PRONOUNS):
        return False

    last_user, last_answer = turns[-1]
    topic_overlap = max(
        token_overlap_score(user_input, last_user),
        token_overlap_score(user_input, last_answer),
    )
    return bool(content_tokens) and (topic_overlap >= 0.05 or len(content_tokens) >= 1)


def _conversation_context(
    user_input: str,
    turns: list[tuple[str, str]],
    max_turns: int = 4,
) -> str | None:
    if not _should_use_conversation_context(user_input, turns):
        return None
    return "\n".join(f"User: {u}\nAssistant: {a}" for u, a in turns[-max_turns:])


def _repl(
    dispatch: Dispatch,
    llm: LLMClient,
    as_json: bool,
    use_conversation: bool,
    ui: AssistantUI,
    show_header: bool = True,
    initial_turns: list[tuple[str, str]] | None = None,
) -> None:
    if show_header and not as_json:
        ui.header("interactive")

    turns: list[tuple[str, str]] = list(initial_turns or [])
    while True:
        try:
            user_input = input("\n") if as_json else ui.ask()
        except (EOFError, KeyboardInterrupt):
            break

        user_input = user_input.strip()
        if not user_input or user_input in {"/exit", "exit", "quit"}:
            break
        if user_input == "/help":
            ui.help(_help_commands())
            continue
        if user_input == "/workflows":
            ui.workflows(get_workflow_registry())
            continue

        context = _conversation_context(user_input, turns) if use_conversation else None

        def execute() -> BaseModel:
            return (
                run(user_input, llm, conversation_context=context)
                if use_conversation
                else dispatch(user_input, llm)
            )

        if as_json:
            result = execute()
        else:
            status = StatusCollector(ui.console)
            status.subscribe()
            try:
                result = execute()
            finally:
                trace_path = status.trace_hint()
                if trace_path:
                    ui.info(f"trace: {trace_path}")
                status.unsubscribe()

        answer = _print_result(result, as_json, None if as_json else ui)
        if use_conversation:
            turns.append((user_input, answer))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Unified local SLM assistant: one prompt engine for CLI and chat",
        add_help=False,
    )
    parser.add_argument(
        "-p",
        "--prompt",
        metavar="PROMPT",
        help="Run one prompt through the unified assistant and exit",
    )
    parser.add_argument("--chat", action="store_true", help="Continue interactively after --prompt")
    parser.add_argument("--json", action="store_true", help="Print raw JSON result objects")
    parser.add_argument(
        "--model",
        metavar="ALIAS",
        help="Override all text specialist roles with a llama.cpp model alias",
    )
    parser.add_argument("--router-model", metavar="ALIAS", help="Override only the router model")
    parser.add_argument("--qa-model", metavar="ALIAS", help="Override only the QA model")
    parser.add_argument(
        "--summarization-model", metavar="ALIAS", help="Override only the summarization model"
    )
    parser.add_argument(
        "--classification-model", metavar="ALIAS", help="Override only the classification model"
    )
    parser.add_argument(
        "--function-model", metavar="ALIAS", help="Override only the tool-selection model"
    )
    parser.add_argument(
        "--agent-model", metavar="ALIAS", help="Override only the planner-agent model"
    )
    parser.add_argument(
        "--no-model-download",
        action="store_true",
        help="Do not auto-download known missing model artifacts from Hugging Face",
    )
    parser.add_argument("--direct", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--agent", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--workflow", metavar="NAME", help=argparse.SUPPRESS)
    parser.add_argument(
        "--list-workflows",
        action="store_true",
        help="List available predefined workflow graphs and exit",
    )
    return parser


def _help_commands() -> list[CommandHelp]:
    return [
        CommandHelp("src.main", "Start interactive chat using the unified assistant engine."),
        CommandHelp("-p, --prompt TEXT", "Run one prompt and exit."),
        CommandHelp("--chat -p TEXT", "Run an initial prompt, then continue interactively."),
        CommandHelp("--json -p TEXT", "Print the raw result object as JSON for scripts."),
        CommandHelp("--model ALIAS", "Experiment with a different local llama.cpp model alias."),
        CommandHelp(
            "--qa-model/--router-model/... ALIAS",
            "Override one specialist role while keeping the rest unchanged.",
        ),
        CommandHelp("--list-workflows", "Inspect predefined workflow graphs."),
        CommandHelp("/workflows", "Show workflow graphs inside interactive chat."),
        CommandHelp("/help", "Show this help inside interactive chat."),
        CommandHelp("/exit", "Leave interactive chat."),
    ]


def _select_dispatch(
    args: argparse.Namespace, orchestrator: Orchestrator | None = None
) -> Dispatch:
    if args.workflow:
        wf_registry = get_workflow_registry()
        resolved = match_workflow(args.workflow, wf_registry)
        selected = wf_registry.get(resolved or "")
        if selected is None:
            raise ValueError(
                f"Unknown workflow: {args.workflow!r}. Available: {', '.join(wf_registry)}"
            )
        return lambda inp, client: run_workflow(selected, inp, client)
    if args.agent:
        assert orchestrator is not None
        summarization = orchestrator.node_registry.get("summarization")
        classification = orchestrator.node_registry.get("classification")
        answer = orchestrator.node_registry.get("question_answering")
        assert summarization is not None
        assert classification is not None
        assert answer is not None
        agent_node = orchestrator.node_registry.get("agent")
        agent_profile = getattr(agent_node, "_profile", None)
        return lambda inp, client: run_agent(
            inp,
            client,
            tool_registry=orchestrator.tool_registry,
            action_nodes={
                "summarize": summarization,
                "classify": classification,
                "answer": answer,
            },
            profile=agent_profile,
        )
    if args.direct:
        assert orchestrator is not None
        return lambda inp, client: orchestrator.run_direct(inp, client)
    return run


def _model_overrides_from_args(args: argparse.Namespace) -> dict[str, str | None]:
    return {
        "router": args.router_model,
        "question_answering": args.qa_model,
        "summarization": args.summarization_model,
        "classification": args.classification_model,
        "function_calling": args.function_model,
        "agent": args.agent_model,
    }


def _ensure_requested_models(args: argparse.Namespace) -> None:
    requested = [args.model, *_model_overrides_from_args(args).values()]
    for model in {m for m in requested if m}:
        ensure_model_available(model, auto_download=not args.no_model_download)


def main() -> None:
    ui = AssistantUI()
    if any(arg in {"-h", "--help"} for arg in sys.argv[1:]):
        ui.help(_help_commands())
        return

    parser = _build_parser()
    args = parser.parse_args()

    if args.list_workflows:
        tool_registry = build_tool_registry()
        node_registry = build_node_registry(tool_registry=tool_registry)
        set_node_registry(node_registry)
        ui.workflows(get_workflow_registry())
        return

    try:
        _ensure_requested_models(args)
        model_profiles = apply_model_overrides(
            default_model=args.model,
            role_models=_model_overrides_from_args(args),
        )
        tool_registry = build_tool_registry()
        node_registry = build_node_registry(
            tool_registry=tool_registry,
            model_profiles=model_profiles,
        )
        set_node_registry(node_registry)
        orchestrator = Orchestrator(
            node_registry=node_registry,
            tool_registry=tool_registry,
            router=Router(profile=model_profiles["router"]),
        )
        dispatch = _select_dispatch(args, orchestrator)
    except (FileNotFoundError, ValueError) as exc:
        ui.error(str(exc))
        ui.info(f"Known auto-download aliases: {', '.join(known_model_aliases())}")
        sys.exit(1)

    llm = build_llm_client()
    use_conversation = dispatch is run
    rich_output = not args.json

    if args.prompt is not None:
        if rich_output:
            ui.header("one-shot" if not args.chat else "chat bootstrap")
            ui.user_message(args.prompt)

        def execute() -> BaseModel:
            return dispatch(args.prompt, llm)

        if args.json:
            result = execute()
        else:
            status = StatusCollector(ui.console)
            status.subscribe()
            try:
                result = execute()
            finally:
                trace_path = status.trace_hint()
                if trace_path:
                    ui.info(f"trace: {trace_path}")
                status.unsubscribe()

        answer = _print_result(result, args.json, ui if rich_output else None)
        if not args.chat:
            return
        initial_turns = [(args.prompt, answer)] if use_conversation else None
    else:
        initial_turns = None

    _repl(
        dispatch,
        llm,
        args.json,
        use_conversation=use_conversation,
        ui=ui,
        show_header=args.prompt is None,
        initial_turns=initial_turns,
    )


if __name__ == "__main__":
    main()
