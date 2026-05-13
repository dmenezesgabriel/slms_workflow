# Extract `OpenAILocalClient` construction from `main.py`

**Priority:** Medium
**Category:** Ports and Adapters, Dependency Direction
**Issue:** Finding 5 — `main.py` instantiates concrete LLM provider directly
**Depends on:** Issue 06 (inject-model-profile) — ideally done after model configuration is handled at the composition root
**Estimated effort:** Small

---

## Current State

`src/main.py` imports and instantiates `OpenAILocalClient` directly in two places:

At the top-level import:
```python
# src/main.py:14
from src.providers.openai_local import OpenAILocalClient
```

In the `run()` function (fallback default):
```python
# src/main.py:30
llm = llm or OpenAILocalClient()
```

In the `main()` function:
```python
# src/main.py:244
llm = OpenAILocalClient()
```

The `OpenAILocalClient` is a concrete class that depends on the `openai` library and `llama.cpp` server:
```python
# src/providers/openai_local.py:15-26
class OpenAILocalClient:
    def __init__(self, base_url="http://127.0.0.1:8080/v1", api_key="sk-local", timeout=180.0):
        self.client = OpenAI(base_url=base_url, api_key=api_key, timeout=timeout)
```

The `run()` function signature accepts `LLMClient | None` and defaults:
```python
# src/main.py:21-33
def run(
    user_input: str,
    llm: LLMClient | None = None,
    conversation_context: str | None = None,
) -> BaseModel:
    trace.init()
    trace.span_enter("request")
    llm = llm or OpenAILocalClient()
    result = run_assistant(user_input, llm, conversation_context=conversation_context)
    trace.span_exit("request")
    return result
```

---

## Design Problem

1. **The CLI adapter (`main.py`) depends on a concrete infrastructure class**. Swapping to a different LLM provider (e.g., Anthropic, a different local server, a mock for testing) requires modifying `main.py`.

2. **The `run()` public API has a hidden default**: The `llm=None` default silently falls back to `OpenAILocalClient()`. Callers who don't pass an `llm` get a concrete implementation without realizing it. This makes the `LLMClient` protocol optional rather than explicit.

3. **Testability**: Testing `run()` or `main()` requires the `llama.cpp` server to be running (or monkey-patching). There is no way to call `run()` in a unit test without infrastructure.

---

## Recommended Changes

### Step 1: Add `create_llm_client()` to `bootstrap.py`

```python
# src/bootstrap.py — after
from src.providers.openai_local import OpenAILocalClient
from src.llm_client import LLMClient

def create_llm_client(
    base_url: str = "http://127.0.0.1:8080/v1",
    api_key: str = "sk-local",
    timeout: float = 180.0,
) -> LLMClient:
    """Factory for the default LLM client. Override this to swap providers."""
    return OpenAILocalClient(base_url=base_url, api_key=api_key, timeout=timeout)
```

### Step 2: Update `main.py`

Remove the direct import of `OpenAILocalClient` and use the factory:

```python
# src/main.py — after (imports)
from src.bootstrap import create_llm_client
from src.llm_client import LLMClient
# Remove: from src.providers.openai_local import OpenAILocalClient
```

Remove the fallback from `run()`:

```python
# src/main.py — after (run function)
def run(
    user_input: str,
    llm: LLMClient,
    conversation_context: str | None = None,
) -> BaseModel:
    """Unified public entrypoint used by CLI, tests, integrations, and chat.
    
    Requires an LLMClient instance. Tests should pass a mock.
    """
    trace.init()
    trace.span_enter("request")
    result = run_assistant(user_input, llm, conversation_context=conversation_context)
    trace.span_exit("request")
    return result
```

Update `main()` to use the factory:

```python
# src/main.py — after (main function)
def main() -> None:
    ...
    llm = create_llm_client()
    ...
```

### Step 3: Update test callers

Any test that calls `run()` without passing `llm` must be updated to pass a mock:

```python
# tests/... — before
result = run("hello")

# tests/... — after
llm = MagicMock(spec=LLMClient)
llm.structured.return_value = FinalAnswer(answer="Hello!")
result = run("hello", llm=llm)
```

### Step 4: (Optional) Make `run()` accept `LLMClient` without default

Remove the `None` default:
```python
# before
def run(user_input: str, llm: LLMClient | None = None, ...) -> BaseModel:

# after
def run(user_input: str, llm: LLMClient, ...) -> BaseModel:
```

This makes the dependency explicit at the type level.

---

## Files to modify

| File | Changes |
|------|---------|
| `src/bootstrap.py` | Add `create_llm_client()` factory |
| `src/main.py` | Remove `from src.providers.openai_local import OpenAILocalClient`. Change `run()` to require `LLMClient`. Use `create_llm_client()` in `main()`. |

---

## Verification

```bash
uv run python -m src.main --help
uv run pytest tests/unit/src/test_main.py -v
```

Any test that calls `run()` without passing `llm` will need a mock passed. This is desirable — it makes the dependency visible.
