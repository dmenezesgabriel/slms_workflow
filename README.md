# Small Language Models Workflow

```sh
# Download models
uv run python -m src.download_models

# Start the inference server (keep running in a separate terminal)
uv run python -m llama_cpp.server --config_file server_config.json

# Single prompt (fastest for iteration)
uv run python -m src.main "what is 3 plus 5"
uv run python -m src.main "summarize: the quick brown fox..."

# Agentic multi-step
uv run python -m src.main --agent "calculate 144 divided by 12 and summarize what that number means"

# Interactive REPL
uv run python -m src.main

# Interactive REPL with agent loop
uv run python -m src.main --agent
```

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
