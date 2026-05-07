# Small Language Models Workflow

```sh
# Download models
uv run python -m app.download_models

# Start the inference server (keep running in a separate terminal)
uv run python -m llama_cpp.server --config_file server_config.json

# Single prompt (fastest for iteration)
uv run python -m app.main "what is 3 plus 5"
uv run python -m app.main "summarize: the quick brown fox..."

# Agentic multi-step
uv run python -m app.main --agent "calculate 144 divided by 12 and summarize what that number means"

# Interactive REPL
uv run python -m app.main

# Interactive REPL with agent loop
uv run python -m app.main --agent
```

## Requirements

```sh
sudo apt update
sudo apt install -y build-essential python3-dev cmake ninja-build
```
