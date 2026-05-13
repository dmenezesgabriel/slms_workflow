# Collapse node delegation layer into handlers

**Priority:** Medium
**Category:** Simplicity, Cohesion
**Issue:** Finding 4 — Every node is a zero-value delegation wrapper around its handler
**Depends on:** Issue 04 (remove-module-level-singletons), Issue 06 (inject-model-profile) — removing nodes only makes sense after handlers are the composition boundary
**Estimated effort:** Medium

---

## Current State

There are 7 node files in `src/nodes/`. Every one is a thin delegation wrapper with identical structure. The `WorkflowNode` protocol that nodes implement is:

```python
# src/nodes/base.py:10-13
class WorkflowNode(Protocol):
    id: str
    def execute(self, input: str, llm: LLMClient) -> BaseModel: ...
```

Every node follows the same pattern — it wraps a handler and delegates:

**`SummarizationNode`** (`src/nodes/summarization_node.py`):
```python
class SummarizationNode:
    id = "summarization"
    def __init__(self) -> None:
        self._handler = SummarizationHandler()
    def execute(self, input: str, llm: LLMClient) -> BaseModel:
        return self._handler.handle(input, llm)
```

**`ClassificationNode`** (`src/nodes/classification_node.py`):
```python
class ClassificationNode:
    id = "classification"
    def __init__(self) -> None:
        self._handler = ClassificationHandler()
    def execute(self, input: str, llm: LLMClient) -> BaseModel:
        return self._handler.handle(input, llm)
```

**`FunctionCallingNode`** (`src/nodes/function_calling_node.py`): Same pattern.

**`GeneralNode`** (`src/nodes/general_node.py`): Same pattern.

**`ImageUnderstandingNode`** (`src/nodes/image_understanding_node.py`): Same pattern.

**`QuestionAnsweringNode`** (`src/nodes/question_answering_node.py`): Same pattern, but additionally passes `retriever`, `grounding_layer`, `rag_store` through (these could just go to the handler directly).

**`AgentNode`** (`src/nodes/agent_node.py`): Same idea, delegates to `run_agent()`:
```python
class AgentNode:
    id = "agent"
    def execute(self, input: str, llm: LLMClient) -> BaseModel:
        from src.agent import run_agent
        return run_agent(input, llm)
```

Every handler class has a `handle(self, user_input: str, llm: LLMClient) -> BaseModel` method whose signature is **isomorphic** to the `WorkflowNode.execute()` protocol — same parameters (modulo naming), same return type.

The `NodeRegistry` is built from nodes in `handlers/__init__.py`:
```python
NODE_REGISTRY = NodeRegistry([
    SummarizationNode(),           # wraps SummarizationHandler
    QuestionAnsweringNode(...),    # wraps QuestionAnsweringHandler
    FunctionCallingNode(),         # wraps FunctionCallingHandler
    ClassificationNode(),          # wraps ClassificationHandler
    ImageUnderstandingNode(),      # wraps ImageUnderstandingHandler
    GeneralNode(),                 # wraps GeneralHandler
    AgentNode(),                   # delegates to run_agent()
])
```

---

## Design Problem

1. **7 files, ~120 lines of pure delegation with zero additional behavior.** Every node's `execute()` method is a one-line delegation to the handler's `handle()`. There is no transformation, no validation, no adaptation.

2. **One-to-one mapping**: There is exactly one node per handler. No handler is used by multiple nodes. No node composes multiple handlers. The mapping is purely mechanical.

3. **The "node" concept is not a seam**: The node doesn't provide a test boundary that the handler doesn't already provide. You test the handler's logic, and the node is trivially correct by inspection.

4. **Slows down feature development**: Adding a new intent requires creating 2 files (handler + node) and registering in 2 places. The node file is always 15 lines of boilerplate.

5. **Confuses the architecture**: New contributors see "nodes" and "handlers" as two separate concepts and must trace through the delegation to understand the system. This is accidental complexity.

---

## Recommended Changes

### Step 1: Make handlers implement `WorkflowNode` protocol directly

Rename `handle()` → `execute()` in each handler, and add the `id` class attribute:

```python
# src/handlers/summarization.py — after
from src.nodes.base import WorkflowNode  # or just implement protocol structurally

class SummarizationHandler:
    id = "summarization"

    def execute(self, input: str, llm: LLMClient) -> BaseModel:
        ...
```

### Step 2: Remove node files

Delete these files:

| File | Delete? | Alternative |
|------|---------|-------------|
| `src/nodes/summarization_node.py` | Yes | Handler implements `WorkflowNode` |
| `src/nodes/classification_node.py` | Yes | Same |
| `src/nodes/function_calling_node.py` | Yes | Same |
| `src/nodes/general_node.py` | Yes | Same |
| `src/nodes/image_understanding_node.py` | Yes | Same |
| `src/nodes/question_answering_node.py` | Yes | Same |

Keep:
- `src/nodes/base.py` — `WorkflowNode` protocol, `NodeRegistry`
- `src/nodes/plugin_node.py` — `PluginNode` is not a handler wrapper; it adapts the plugin protocol to `WorkflowNode`
- `src/nodes/agent_node.py` — `AgentNode` delegates to `run_agent()` from `src/agent.py`, not a handler; it's structurally different

### Step 3: Update `handlers/__init__.py`

Register handlers directly (after issue 04, this lives in `bootstrap.py`):

```python
# After: bootstrap.py or handlers/__init__.py (post-issue-04)
from src.handlers.summarization import SummarizationHandler
...

NodeRegistry([
    SummarizationHandler(),
    QuestionAnsweringHandler(retrizer=..., grounding_layer=...),
    FunctionCallingHandler(),
    ClassificationHandler(),
    ImageUnderstandingHandler(),
    GeneralHandler(),
])
```

### Step 4: Update callers

All existing callers use `NODE_REGISTRY.get(intent)` to get a node, then call `node.execute(input, llm)`. After the change, this works identically — the handlers **are** the nodes. No call site changes needed.

### Step 5: Handle `AgentNode` separately

`AgentNode` delegates to `run_agent()`. This is a valid seam if the agent loop is considered different orchestration logic. Keep `AgentNode` as-is, or fold it into the agent module by making `run_agent` satisfy the protocol:

```python
# src/agent.py
def run_agent(user_input: str, llm: LLMClient, max_steps: int = 5, ...) -> BaseModel:
    ...

# Still register via AgentNode or make Agent itself satisfy WorkflowNode
class Agent:
    id = "agent"
    def execute(self, input: str, llm: LLMClient) -> BaseModel:
        return self.run(input, llm)
```

---

## Files to modify

| File | Action |
|------|--------|
| `src/handlers/summarization.py` | Rename `handle()` → `execute()`, add `id = "summarization"` |
| `src/handlers/classification.py` | Same |
| `src/handlers/function_calling.py` | Same |
| `src/handlers/general.py` | Same |
| `src/handlers/image_understanding.py` | Same |
| `src/handlers/question_answering.py` | Same |
| `src/nodes/summarization_node.py` | **Delete** |
| `src/nodes/classification_node.py` | **Delete** |
| `src/nodes/function_calling_node.py` | **Delete** |
| `src/nodes/general_node.py` | **Delete** |
| `src/nodes/image_understanding_node.py` | **Delete** |
| `src/nodes/question_answering_node.py` | **Delete** |
| `src/handlers/__init__.py` (or `bootstrap.py`) | Register handlers directly instead of via node wrappers |

## Keep
| File | Reason |
|------|--------|
| `src/nodes/base.py` | `WorkflowNode` protocol and `NodeRegistry` |
| `src/nodes/plugin_node.py` | Adapts plugin protocol to `WorkflowNode` |
| `src/nodes/agent_node.py` | Wraps agent (not a handler) |

---

## Verification

```bash
uv run pytest tests/unit/ -v
uv run mypy src/
```

All tests should pass since `NodeRegistry.get("summarization").execute(input, llm)` works identically whether the returned object is a `SummarizationNode` or a `SummarizationHandler`.
