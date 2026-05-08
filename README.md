# Small Language Models Workflow

A unified local SLM assistant. Call it with one prompt or start an interactive chat; the
assistant decides whether to use a direct prompt, a deterministic on-demand DAG workflow,
or the planner agent behind the scenes. The goal is an agentic feel with controlled
routing, branches, tool nodes, and small-model specialist nodes.

```sh
# Download models
uv run python -m src.download_models

# Start the inference server (keep running in a separate terminal)
uv run python -m llama_cpp.server --config_file server_config.json

# Single prompt: auto-routes, composes workflows, or falls back to the agent as needed
uv run python -m src.main "what is 3 plus 5"
uv run python -m src.main "search for llama.cpp and tell me what it is"
uv run python -m src.main "calculate 144 divided by 12 and tell me if it is even or odd"

# Interactive chat-like session
uv run python -m src.main

# Optional controls for debugging / evaluation
uv run python -m src.main --json "summarize: the quick brown fox..."
uv run python -m src.main --direct "what is the capital of France?"
uv run python -m src.main --agent "calculate 7 times 8 and explain the result"
uv run python -m src.main --workflow research_and_summarize "quantum computing"
uv run python -m src.main --list-workflows
```

Set `SLM_TRACE=1` to see the selected plan, DAG nodes/skips, workflow steps, tool calls,
and agent steps on stderr.

## Evaluation and integration checks

```sh
# Fast offline evaluation with accuracy and latency metrics
uv run python -m evals.runner --no-mlflow --save

# Compare MLflow evaluation runs
uv run python -m evals.compare

# Live benchmark against the local LLM server
uv run python -m evals.live

# Gherkin acceptance/integration scenarios against the local LLM server
uv run behave features
```

## Requirements

```sh
sudo apt update
sudo apt install -y build-essential python3-dev cmake ninja-build
```
