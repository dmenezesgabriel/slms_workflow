# Deduplicate `_node()` lookup function

**Priority:** Low
**Category:** Simplicity, Responsibility
**Issue:** Finding 8 — `_node()` function duplicated across `orchestrator.py` and `planner.py`
**Depends on:** Issue 07 (collapse-node-handler-layers) — the `_node()` functions reference `NODE_REGISTRY`
**Estimated effort:** Trivial

---

## Current State

Identical `_node()` function exists in two modules:

**`src/orchestrator.py:20-26`**:
```python
def _node(intent: str) -> WorkflowNode:
    node = NODE_REGISTRY.get(intent)
    if node is None:
        node = NODE_REGISTRY.get("general")
    if node is None:
        raise KeyError(f"Node registry misconfigured: no {intent!r} and no 'general' fallback")
    return node
```

**`src/planner.py:15-21`**:
```python
def _node(intent: str) -> WorkflowNode:
    node = NODE_REGISTRY.get(intent)
    if node is None:
        node = NODE_REGISTRY.get("general")
    if node is None:
        raise KeyError(f"Node registry misconfigured: no {intent!r} and no 'general' fallback")
    return node
```

Both functions do the exact same thing: look up a node by intent name, fall back to `"general"`, and raise if neither exists.

---

## Design Problem

Any change to the fallback logic (e.g., different fallback strategy, logging, metrics, caching) requires updating two identical functions. This is a copy-paste violation that will inevitably diverge.

---

## Recommended Changes

### Step 1: Add `resolve()` method to `NodeRegistry`

Move the fallback logic into `NodeRegistry`:

```python
# src/nodes/base.py — after
class NodeRegistry:
    def __init__(self, nodes: Sequence[WorkflowNode]) -> None:
        self._nodes: dict[str, WorkflowNode] = {n.id: n for n in nodes}
        self._fallback = self._nodes.get("general")

    def get(self, node_id: str) -> WorkflowNode | None:
        return self._nodes.get(node_id)

    def resolve(self, node_id: str) -> WorkflowNode:
        """Look up a node by id, falling back to 'general', or raise."""
        node = self.get(node_id)
        if node is None:
            node = self._fallback
        if node is None:
            raise KeyError(
                f"Node registry misconfigured: no {node_id!r} and no 'general' fallback. "
                f"Available: {sorted(self._nodes)}"
            )
        return node

    def all(self) -> list[WorkflowNode]:
        return list(self._nodes.values())
```

### Step 2: Replace callers

**`src/planner.py`** — remove the local `_node()` function and use `self._node_registry.resolve()`:

```python
# src/planner.py — after
class Planner:
    def __init__(self, node_registry: NodeRegistry, composer: DAGComposer | None = None) -> None:
        self._node_registry = node_registry
        self._composer = composer or DAGComposer(node_registry=node_registry)

    def _single(self, intent: str, description: str) -> DagWorkflow:
        return DagWorkflow(
            name=intent,
            description=description,
            nodes=(DagNode("final", self._node_registry.resolve(intent), "{query}"),),
            final_node="final",
        )

    def _agent(self, description: str) -> DagWorkflow:
        return DagWorkflow(
            name="agent",
            description=description,
            nodes=(DagNode("agent", self._node_registry.resolve("agent"), "{query}"),),
            final_node="agent",
        )
```

**`src/orchestrator.py`** — same pattern, remove `_node()`:

```python
# src/orchestrator.py — after
class Orchestrator:
    def __init__(self, node_registry: NodeRegistry) -> None:
        self._node_registry = node_registry
        self._planner = Planner(node_registry=node_registry)

    def run_direct_with_intent(self, ...):
        ...
        graph = DagWorkflow(
            name=intent,
            description=f"Direct dispatch to {intent}.",
            nodes=(DagNode("final", self._node_registry.resolve(intent), "{query}"),),
            final_node="final",
        )
        ...
```

---

## Files to modify

| File | Changes |
|------|---------|
| `src/nodes/base.py` | Add `resolve()` method to `NodeRegistry` |
| `src/orchestrator.py` | Remove `_node()` function, use `self._node_registry.resolve()` |
| `src/planner.py` | Remove `_node()` function, use `self._node_registry.resolve()` |

---

## Verification

```bash
uv run pytest tests/unit/src/test_orchestrator.py tests/unit/src/test_plugin.py -v
```

The behavior is identical — the same lookup-then-fallback-then-raise logic, just centralized.
