# Small Language Models Workflow

A unified local SLM assistant. Whether you pass a prompt in the CLI or use the
interactive chat, requests enter the same assistant engine. The assistant plans,
routes, composes deterministic on-demand DAG workflows, and only falls back to the
planner loop when needed. The goal is an agentic feel with controlled routing,
branches, tool nodes, and small-model specialist nodes.

```sh
# Download the default small model
uv run python -m src.download_models

# Download a known alias, or a custom GGUF from Hugging Face
uv run python -m src.download_models --model qwen3.5-0.8b-text
uv run python -m src.download_models --model smollm2-360m-instruct-q4km
uv run python -m src.download_models --repo-id USER/REPO-GGUF --filename model-q4.gguf

# Start the inference server (keep running in a separate terminal)
uv run python -m llama_cpp.server --config_file server_config.json

# Interactive chat-like session is the default, using the same engine for every turn
uv run python -m src.main

# One-shot prompt: auto-routes, composes DAGs, or falls back to the planner loop
uv run python -m src.main -p "what is 3 plus 5"
uv run python -m src.main --prompt "search for llama.cpp and tell me what it is"
uv run python -m src.main -p "calculate 144 divided by 12 and tell me if it is even or odd"

# Experiment with model aliases exposed by the local llama.cpp server
uv run python -m src.main --model qwen3.5-0.8b-text -p "what is spaCy?"
uv run python -m src.main --qa-model qwen3.5-0.8b-text -p "what is spaCy?"

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

# Live benchmark against the local LLM server; optionally log experiments to MLflow
uv run python -m evals.live
uv run python -m evals.live reference --model qwen3.5-0.8b-text --mlflow

# Complex acceptance cases with explicit ground truth and MLflow artifacts
uv run python -m evals.acceptance --case hitchhiker --mlflow
uv run python -m evals.acceptance --case gba_pokemon_first --mlflow
uv run python -m evals.acceptance --case solid --mlflow
uv run python -m evals.acceptance --all --mlflow

# Mutation testing for unit-test-covered code only
uv run mutmut run
uv run mutmut results

# Gherkin acceptance/integration scenarios against the local LLM server
uv run behave features
```

## Requirements

```sh
sudo apt update
sudo apt install -y build-essential python3-dev cmake ninja-build
```

## References

- https://towardsdatascience.com/rag-hallucinates-i-built-a-self-healing-layer-that-fixes-it-in-real-time/
- https://towardsdatascience.com/rag-isnt-enough-i-built-the-missing-context-layer-that-makes-llm-systems-work/
- https://towardsdatascience.com/your-rag-gets-confidently-wrong-as-memory-grows-i-built-the-memory-layer-that-stops-it/

- https://lalatenduswain.medium.com/choosing-the-right-small-language-model-for-rag-a-comprehensive-comparison-guide-6e60044441ac
- https://arxiv.org/html/2501.06713v1
https://developers.googleblog.com/google-ai-edge-small-language-models-multimodality-rag-function-calling/
- https://towardsdatascience.com/your-react-agent-is-wasting-90-of-its-retries-heres-how-to-stop-it/

- https://arxiv.org/pdf/2212.10915

## References

- https://github.com/daveebbelaar/ai-cookbook