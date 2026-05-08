# Small Language Models Workflow

A unified local SLM assistant. Whether you pass a prompt in the CLI or use the
interactive chat, requests enter the same assistant engine. The assistant plans,
routes, composes deterministic on-demand DAG workflows, and only falls back to the
planner loop when needed. The goal is an agentic feel with controlled routing,
branches, tool nodes, and small-model specialist nodes.

```sh
# Download models
uv run python -m src.download_models

# Start the inference server (keep running in a separate terminal)
uv run python -m llama_cpp.server --config_file server_config.json

# Interactive chat-like session is the default, using the same engine for every turn
uv run python -m src.main

# One-shot prompt: auto-routes, composes DAGs, or falls back to the planner loop
uv run python -m src.main -p "what is 3 plus 5"
uv run python -m src.main --prompt "search for llama.cpp and tell me what it is"
uv run python -m src.main -p "calculate 144 divided by 12 and tell me if it is even or odd"

# Start with an initial prompt, then keep the session open
uv run python -m src.main --chat -p "Tell me about OpenAI"

# Optional inspection/debugging
uv run python -m src.main --json -p "summarize: the quick brown fox..."
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
