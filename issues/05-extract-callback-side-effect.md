# Extract hidden RAG store side effect from `QuestionAnsweringHandler`

**Priority:** Medium
**Category:** Encapsulation, Testability
**Issue:** Finding 7 — `_rag_store` callback creates hidden mutable side effect
**Depends on:** Issue 04 (remove-module-level-singletons) — the callback currently captures a module-level `_rag_store`
**Estimated effort:** Small

---

## Current State

`src/handlers/__init__.py` creates a module-level `_rag_store` singleton and a callback closure that mutates it:

```python
# src/handlers/__init__.py:15-20
_rag_store = create_default_rag()

def _store_retrieval_results(contents: list[str], sources: list[str]) -> None:
    _rag_store.add_text(contents=contents, sources=sources)
```

This callback is passed through the node layer into `QuestionAnsweringHandler`:

```python
# src/handlers/__init__.py:30-33
QuestionAnsweringNode(
    retriever=_default_retriever,
    grounding_layer=_grounding_layer,
    rag_store=_store_retrieval_results,
)
```

In `QuestionAnsweringHandler.handle()`, the callback is invoked as a hidden side effect:

```python
# src/handlers/question_answering.py:30-36
def handle(self, user_input: str, llm: LLMClient) -> BaseModel:
    trace.handler("question_answering", user_input)
    trace.span_enter("question_answering")
    retrieved = self._retriever.fetch_context(user_input)

    if retrieved and self._rag_store and not tool_selection.is_math_expression(user_input):
        self._rag_store([retrieved], ["retrieval_cache"])
```

The callback type is:

```python
# src/handlers/question_answering.py:14
RagStoreCallback = Callable[[list[str], list[str]], None]
```

---

## Design Problem

1. **Hidden mutation**: `handle()` returns a `BaseModel` (`FinalAnswer`), but also has an invisible side effect — it mutates the RAG store. The caller has no way to know this happens from the return type or function name.

2. **No isolation**: The callback captures `_rag_store` — a module-level `HybridRAG` singleton. Tests cannot verify whether RAG storage occurred without inspecting the global.

3. **Temporal coupling**: The RAG store must exist before the handler is called. The handler's behavior is different depending on whether a `_rag_store` callback was provided (the check `if retrieved and self._rag_store` means the code path changes based on wiring).

4. **Callback pattern confuses ownership**: The `rag_store` parameter is a `Callable`, not a role interface. A reader cannot tell what operations it supports without tracing the callback definition.

---

## Recommended Changes

### Step 1: Remove the callback from `QuestionAnsweringHandler`

The handler should not have a side effect — it should return the retrieval result and let the caller decide what to persist:

```python
# src/handlers/question_answering.py — before
class QuestionAnsweringHandler:
    def __init__(self, retriever, grounding_layer=None, rag_store=None):
        self._retriever = retriever
        self._grounding = grounding_layer
        self._rag_store = rag_store

    def handle(self, user_input: str, llm: LLMClient) -> BaseModel:
        retrieved = self._retriever.fetch_context(user_input)
        if retrieved and self._rag_store and not tool_selection.is_math_expression(user_input):
            self._rag_store([retrieved], ["retrieval_cache"])
        ...
```

```python
# src/handlers/question_answering.py — after
class QuestionAnsweringHandler:
    def __init__(self, retriever, grounding_layer=None):
        self._retriever = retriever
        self._grounding = grounding_layer

    def handle(self, user_input: str, llm: LLMClient) -> tuple[BaseModel, str | None]:
        retrieved = self._retriever.fetch_context(user_input)
        ...
        result = ...  # BaseModel
        return result, retrieved  # return the context for caller-side persistence
```

Two options for the return type:

**Option A**: Return `tuple[BaseModel, str | None]` — the handler returns the `FinalAnswer` plus the retrieved context string (or `None` if no retrieval happened). The caller handles persistence.

**Option B**: Keep returning `BaseModel` but return the context via a separate property or output parameter. Option A is simpler.

### Step 2: Move the persistence decision to the caller

The caller (in `bootstrap.py` or the DAG execution layer) decides whether to persist:

```python
# In bootstrap.py or orchestrator — after
rag_store = HybridRAG()

def on_retrieval_result(result: BaseModel, retrieved_context: str | None) -> BaseModel:
    if retrieved_context and not is_math_expression(...):
        rag_store.add_text(contents=[retrieved_context], sources=["retrieval_cache"])
    return result

# Usage in DAG flow
result, retrieved = handler.handle(user_input, llm)
result = on_retrieval_result(result, retrieved)
```

### Step 3: Update callers of `QuestionAnsweringHandler`

The `QuestionAnsweringNode` (if it still exists) or the DAG executor should be updated to:

1. Call `handler.handle()`
2. Receive the tuple `(result, retrieved_context)`
3. Optionally persist the context (via a store function provided at composition time)
4. Return the `result`

---

## Files to modify

| File | Changes |
|------|---------|
| `src/handlers/question_answering.py` | Remove `rag_store` parameter from constructor. Change `handle()` return type to `tuple[BaseModel, str \| None]`. Remove the callback invocation. |
| `src/handlers/__init__.py` (or `bootstrap.py` after issue 04) | Remove `rag_store` argument from the handler/node construction. Add persistence logic at the orchestration/composition layer. |
| `src/nodes/question_answering_node.py` | If this node still exists, handle the `tuple` return from `handler.handle()`, pass the `BaseModel` result forward, and route the context to a store function. |

---

## Verification

```bash
uv run pytest tests/unit/src/handlers/test_question_answering.py -v
```

Tests that verify RAG storage behavior (if any) should be updated to test at the orchestration layer, not inside the handler.
