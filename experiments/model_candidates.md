# Small-model experiment candidates

Constraints: CPU-only, ~4 GB RAM budget, llama.cpp GGUF models, preferably <= current ~0.8B default.

Searched with `uv run hf models list ...` and repo file listings.

## Candidates

| Alias | Hugging Face repo | GGUF file | Size | Notes |
| --- | --- | --- | ---: | --- |
| `qwen3.5-0.8b-text` | `unsloth/Qwen3.5-0.8B-GGUF` | `Qwen3.5-0.8B-UD-Q4_K_XL.gguf` | ~533 MB | Current default; strong for the size. |
| `smollm2-360m-instruct-q4km` | `bartowski/SmolLM2-360M-Instruct-GGUF` | `SmolLM2-360M-Instruct-Q4_K_M.gguf` | ~258 MB | Downloaded and smoke-tested; faster and lower RAM. |
| `qwen2.5-0.5b-instruct-q4km` | `Qwen/Qwen2.5-0.5B-Instruct-GGUF` | `qwen2.5-0.5b-instruct-q4_k_m.gguf` | ~469 MB | Registered for future comparison. |

## Acceptance experiment notes

Acceptance cases are run one at a time with MLflow logging:

```sh
uv run python -m evals.acceptance --case hitchhiker --mlflow
uv run python -m evals.acceptance --case gba_pokemon_first --mlflow
uv run python -m evals.acceptance --case solid --mlflow
```

SmolLM2 config tested with:

```sh
uv run python -m src.download_models --model smollm2-360m-instruct-q4km
uv run python -m llama_cpp.server --config_file experiments/server_config.smollm2-360m.json
uv run python -m evals.acceptance --case hitchhiker --model smollm2-360m-instruct-q4km --server-config experiments/server_config.smollm2-360m.json --mlflow
```

Server configs are saved as MLflow artifacts by `evals.acceptance` under `llama_cpp_server_config/`.
