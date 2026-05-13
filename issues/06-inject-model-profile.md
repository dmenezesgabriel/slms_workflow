# Inject `ModelProfile` instead of accessing `MODEL_REGISTRY` global in handlers

**Priority:** Medium
**Category:** Dependency Direction, Coupling
**Issue:** Finding 6 — Handlers access `MODEL_REGISTRY` global directly instead of receiving model configuration
**Depends on:** Issue 04 (remove-module-level-singletons) — ideally done together since both move globals into constructor injection
**Estimated effort:** Medium

---

## Current State

Every handler and several core classes read model configuration by indexing into the global `MODEL_REGISTRY` dict with a string key:

```python
# src/handlers/question_answering.py:42-43
profile = MODEL_REGISTRY["question_answering"]
result = llm.structured(
    LLMRequest(model=profile.model, system=profile.system, ...), FinalAnswer, ...
)
```

The same pattern appears in:

| File | Line(s) | Key |
|------|---------|-----|
| `src/handlers/question_answering.py` | 42 | `"question_answering"` |
| `src/handlers/summarization.py` | 29 | `"summarization"` |
| `src/handlers/classification.py` | 17 | `"classification"` |
| `src/handlers/function_calling.py` | 56 | `"function_calling"` |
| `src/handlers/general.py` | 17 | `"general"` |
| `src/handlers/image_understanding.py` | (likely) | `"image_understanding"` |
| `src/router.py` | 189 | `"router"` |
| `src/agent.py` | 52 | `"agent"` |

The global is a plain `dict` defined in `src/model_registry.py:76-164`:

```python
MODEL_REGISTRY: dict[str, ModelProfile] = {
    "router": ModelProfile(...),
    "summarization": ModelProfile(...),
    "question_answering": ModelProfile(...),
    ...
}
```

It is mutated at runtime by `apply_model_overrides()` (`src/model_registry.py:246-270`), which replaces `ModelProfile` entries based on CLI flags:

```python
def apply_model_overrides(*, default_model=None, role_models=None):
    if default_model:
        for role, profile in list(MODEL_REGISTRY.items()):
            if role != "image_understanding":
                MODEL_REGISTRY[role] = replace(profile, model=default_model)
    for role, model in (role_models or {}).items():
        ...
        MODEL_REGISTRY[normalized] = replace(MODEL_REGISTRY[normalized], model=model)
```

---

## Design Problem

1. **Business logic coupled to global configuration**: Handlers cannot be constructed or tested without the `MODEL_REGISTRY` dict being populated and imported.

2. **Mutable global affects behavior over time**: `apply_model_overrides()` can change the model configuration mid-process. A handler used before and after the override would use different models, even within the same request.

3. **Hidden dependency**: Reading `profile = MODEL_REGISTRY["question_answering"]` looks like a dictionary lookup but is actually an ambient dependency on a process-wide configuration singleton. The handler's signature does not reveal this dependency.

4. **Test isolation requires monkey-patching**: Every handler test must do `patch("src.handlers.question_answering.MODEL_REGISTRY", ...)` or similar. This is fragile and verbose.

---

## Recommended Changes

### Step 1: Add `ModelProfile` as constructor parameter to each handler

Each handler that uses `MODEL_REGISTRY` should receive its `ModelProfile` via dependency injection:

```python
# src/handlers/question_answering.py — after
class QuestionAnsweringHandler:
    def __init__(
        self,
        retriever: Retriever,
        grounding_layer: GroundingLayer | None = None,
        rag_store: RagStoreCallback | None = None,
        profile: ModelProfile | None = None,  # NEW
    ) -> None:
        self._retriever = retriever
        self._grounding = grounding_layer
        self._rag_store = rag_store
        self._profile = profile or MODEL_REGISTRY["question_answering"]  # fallback for backward compat

    def handle(self, user_input: str, llm: LLMClient) -> BaseModel:
        ...
        profile = self._profile  # ← use injected profile, not global
        ...
```

Apply the same pattern to:

| Handler | Profile key |
|---------|-------------|
| `SummarizationHandler` | `"summarization"` |
| `ClassificationHandler` | `"classification"` |
| `GeneralHandler` | `"general"` |
| `ImageUnderstandingHandler` | `"image_understanding"` |
| `FunctionCallingHandler` | `"function_calling"` |
| `Router` | `"router"` |
| `Agent` | `"agent"` |

For each, the change is:
1. Add `profile: ModelProfile | None = None` to `__init__`
2. Store as `self._profile`
3. Replace `MODEL_REGISTRY["key"]` with `self._profile`
4. Add fallback `self._profile = self._profile or MODEL_REGISTRY["key"]` if backward compat is needed

### Step 2: Update all construction sites to pass the profile

In `bootstrap.py` (after issue 04) pass the appropriate `ModelProfile`:

```python
# bootstrap.py — after
from src.model_registry import MODEL_REGISTRY

def build_node_registry(...) -> NodeRegistry:
    ...
    return NodeRegistry([
        SummarizationHandler(profile=MODEL_REGISTRY["summarization"]),
        QuestionAnsweringHandler(
            retriever=retriever,
            grounding_layer=grounding_layer,
            profile=MODEL_REGISTRY["question_answering"],
        ),
        FunctionCallingHandler(profile=MODEL_REGISTRY["function_calling"]),
        ClassificationHandler(profile=MODEL_REGISTRY["classification"]),
        ImageUnderstandingHandler(profile=MODEL_REGISTRY["image_understanding"]),
        GeneralHandler(profile=MODEL_REGISTRY["general"]),
        ...
    ])
```

### Step 3: Handle `apply_model_overrides` at the composition root

Instead of mutating `MODEL_REGISTRY` in place, apply overrides when building the registry:

```python
# bootstrap.py — after
def apply_model_overrides_to_registry(
    registry: dict[str, ModelProfile],
    default_model: str | None = None,
    role_models: dict[str, str | None] | None = None,
) -> dict[str, ModelProfile]:
    """Return a copy of registry with overrides applied. Does not mutate the original."""
    result = dict(registry)
    if default_model:
        for role, profile in result.items():
            if role != "image_understanding":
                result[role] = replace(profile, model=default_model)
    for role, model in (role_models or {}).items():
        if model:
            result[role] = replace(result[role], model=model)
    return result
```

Then in `main.py`, pass the overridden profiles:

```python
# main.py — after
from src.bootstrap import build_node_registry, apply_model_overrides_to_registry
from src.model_registry import MODEL_REGISTRY

registry_with_overrides = apply_model_overrides_to_registry(
    MODEL_REGISTRY, default_model=args.model, role_models=...
)
node_registry = build_node_registry(model_registry=registry_with_overrides)
```

---

## Files to modify

| File | Changes |
|------|---------|
| `src/handlers/question_answering.py` | Add `profile` param, store as `self._profile`, use instead of global |
| `src/handlers/summarization.py` | Same |
| `src/handlers/classification.py` | Same |
| `src/handlers/function_calling.py` | Same |
| `src/handlers/general.py` | Same |
| `src/handlers/image_understanding.py` | Same |
| `src/router.py` | Same — `Router.__init__` gets `profile` param |
| `src/agent.py` | Same — `Agent.__init__` gets `profile` param |
| `src/bootstrap.py` | Pass profiles when constructing handlers |
| `src/main.py` | Apply overrides at bootstrap level, pass to registry builder |
| `src/model_registry.py` | Keep the `MODEL_REGISTRY` dict (it's the canonical config definition), but make `apply_model_overrides` return a copy instead of mutating in place |

---

## Verification

```bash
uv run pytest tests/unit/ -v
uv run mypy src/
```

All existing tests that monkey-patch `MODEL_REGISTRY` should continue to work (the fallback `profile or MODEL_REGISTRY["key"]` preserves backward compatibility). New tests can inject a mock `ModelProfile` directly.
