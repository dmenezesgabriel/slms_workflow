# Small Language Models Workflow

A unified local SLM assistant. Whether you pass a prompt in the CLI or use the
interactive chat, requests enter the same assistant engine. The assistant plans,
routes, composes deterministic on-demand workflow graphs, and only falls back to the
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

# One-shot prompt: auto-routes, composes workflow graphs, or falls back to the planner loop
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
uv run python -m src.main --list-workflows  # show predefined workflow graphs
```

Set `SLM_TRACE=1` to see the selected plan, graph node execution/skips, workflow steps,
tool calls, and agent steps on stderr.

## Lexical routing and heuristic architecture

The fast path is now built around shared deterministic lexical scoring instead of duplicated
module-local phrase gates.

Core shared modules:
- `src/text_normalization.py`
  - casefolding
  - diacritic folding
  - punctuation cleanup
  - tokenization
  - normalized lookup-query cleanup
- `src/lexical_scoring.py`
  - token overlap
  - RapidFuzz similarity
  - char n-gram TF-IDF similarity
  - combined lexical score helpers

Where the shared layer is used:
- `src/router.py`
  - scores user input against centralized intent prototypes in `src/router_prototypes.py`
  - returns a fast deterministic route when `_FAST_ROUTE_THRESHOLD` is met
  - falls back to the LLM router only when lexical confidence is too low
- `src/tool_selection.py`
  - ranks tool candidates using lexical prototypes, regex signals, and NER/entity cues
  - keeps deterministic math extraction and URL fetch handling as explicit fast paths
- `src/techniques/retrieval.py` and `src/retrievers/default.py`
  - choose retrieval strategy through scored planning instead of brittle branch-heavy string hacks
- `src/main.py`
  - uses shared token/lexical overlap helpers for follow-up and conversation-context decisions
- `src/handlers/summarization.py` and `src/techniques/grounding.py`
  - use normalized lexical checks for short-input validation and support/faithfulness checks

## Threshold and fallback ownership

Tune thresholds in the module that owns the decision surface instead of scattering literals:
- `src/router.py`
  - `_FAST_ROUTE_THRESHOLD`: minimum lexical score for fast intent routing
  - `_LLM_FALLBACK_THRESHOLD`: minimum LLM confidence before accepting the structured router result
- `src/handlers/summarization.py`
  - `_CONTENTLESS_MATCH_THRESHOLD` and related minimum-content constants control summarization guards
- `evals/quality_gate.py`
  - `DEFAULT_THRESHOLDS` defines benchmark gates for protected accuracy, target-improvement deltas,
    false-link tolerance, valid-short-input rejection, and answer-quality coverage floors
  - changing thresholds is a dataset-ownership decision: update the rationale together with the fixture version

Decision policy:
- prefer deterministic lexical decisions first
- fall back to the LLM only when deterministic confidence is below the owned threshold
- accept benchmark changes only when protected cases do not regress beyond the configured gates
- do not silently rewrite historical fixture expectations in place; introduce a new dataset version when semantics materially change

## Validation workflow

### Quick local checks

`pytest` follows the repo default in `pyproject.toml` and skips `integration`-marked tests unless you ask for them explicitly.

```sh
uv run ruff check .
uv run mypy .
uv run pytest
```

### Formatting

```sh
uv run ruff format .
```

### Integration tests

Integration tests require the local llama.cpp server from `server_config.json`.

```sh
uv run python -m llama_cpp.server --config_file server_config.json
uv run pytest -m integration
```

### Frozen quality benchmark

The metric gate now has two layers:
- `v1`: the original focused regression benchmark used for before/after comparisons against the frozen baseline
- `v2`: the hardened benchmark with `dev` and `heldout` splits, answer-level reporting, richer follow-up fixtures, and captured-model-output checks

Key files:
- `tests/evals/fixtures/v1/`
- `tests/evals/fixtures/v2/dev/`
- `tests/evals/fixtures/v2/heldout/`
- `evals/quality_gate.py`
- `scripts/run_eval.py`

```sh
# Legacy frozen baseline workflow
uv run python scripts/run_eval.py --dataset-version v1 --label latest
uv run python scripts/run_eval.py --dataset-version v1 --label candidate --compare-to artifacts/evals/baseline-v1.json

# Hardened benchmark across visible + held-out fixtures
uv run python scripts/run_eval.py --dataset-version v2 --split all --label benchmark-hardening
uv run python scripts/run_eval.py --dataset-version v2 --split heldout --label heldout-check
```

Benchmark reports are written to `artifacts/evals/`. See `artifacts/evals/README.md` for naming,
metrics, split handling, threshold rationale, and current automation gaps.

### CI-friendly full pass

```sh
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
uv run pytest -m integration
uv run python scripts/run_eval.py --label ci --compare-to artifacts/evals/baseline-v1.json
```

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