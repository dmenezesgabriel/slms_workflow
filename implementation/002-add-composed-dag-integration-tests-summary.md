# Implementation Summary: Add integration tests for composed DAG flows

## Related Task

- `issues/002-add-composed-dag-integration-tests.md`

## Files Changed

- `tests/unit/src/workflows/test_composer.py:70-82` — Added `test_compose_builds_search_to_question_answering_graph` (UT-001)
- `tests/unit/src/test_dag.py:174-214` — Added `test_composed_dag_tool_output_flows_to_final_answer` (UT-002)
- `tests/unit/src/test_orchestrator.py:1-15,127-176` — Added `test_orchestrated_composed_search_to_qa_produces_substantive_answer` (covers IT-001 / REG-001), updated imports

## Behavior Implemented

No production code changes — this task adds only tests. The three tests cover:

1. **UT-001** — `DAGComposer.compose()` with "search for llama.cpp and tell me what it is" returns a 2-node DAG (`function_calling → question_answering`) with the correct input format `"Context:\n{tool}\n\nQuestion: {query}"` and node types. Covers `FR-001`, `FR-004`, `AC-002`.

2. **UT-002** — `run_graph()` with a DAG matching the composer's structure, a mock tool node returning known llama.cpp content (`"llama.cpp is a C/C++ implementation..."`), and a mock QA node proves the tool output flows through to the final answer. Final answer contains `"C/C++"` and `"llama.cpp"`. The DAG trace confirms the tool output is recorded and the QA input contains `Context:` and `Question:` labels. Covers `FR-002`, `AC-001`.

3. **IT-001 / REG-001** — Full compose → execute path via `Orchestrator.compose_dag()` with realistic mock nodes and `run_graph()` execution. Proves the previously broken prompt now produces a substantive answer containing content from the tool results. The trace confirms the tool node's full output and the final node's labeled input format. Covers `AC-001`, `REG-001`.

## Design Notes

- All tests are unit-level (no integration marker, no LLM server required).
- Tests use mock nodes and mock LLM clients — no network or model server calls.
- UT-002 explicitly builds a DAG matching the composer's `_processing_format` (`"Context:\n{tool}\n\nQuestion: {query}"`) to verify the input format contract.
- IT-001/REG-001 reuses the existing `_make_orchestrator` pattern extended with custom mock nodes that return realistic tool content.
- Pre-existing test failures in `tests/unit/src/handlers/test_function_calling.py:3` are unrelated to these changes.

## Tests Added or Updated

- `tests/unit/src/workflows/test_composer.py::test_compose_builds_search_to_question_answering_graph` — new (UT-001)
- `tests/unit/src/test_dag.py::test_composed_dag_tool_output_flows_to_final_answer` — new (UT-002)
- `tests/unit/src/test_orchestrator.py::test_orchestrated_composed_search_to_qa_produces_substantive_answer` — new (IT-001 / REG-001)

## Test Categories Not Applicable

- `Smoke`: Not applicable — no deployment or startup changes.
- `E2E`: Not applicable — integration tests at the `run_graph` level provide sufficient coverage.
- `Performance`: Not applicable — no measurable performance impact.
- `Security`: Not applicable — no authentication, authorization, or trust boundary changes.
- `Usability`: Not applicable — no user-facing UI changes.
- `Observability`: Not applicable — no telemetry changes.

## Validation Run

```text
uv run pytest tests/unit/src/workflows/test_composer.py tests/unit/src/test_dag.py tests/unit/src/test_orchestrator.py -v — 24 passed (3 new + 21 existing)
uv run pytest --tb=short — 345 passed, 3 failed (3 failures in test_function_calling.py are pre-existing and unrelated)
uv run ruff check tests/unit/src/workflows/test_composer.py tests/unit/src/test_dag.py tests/unit/src/test_orchestrator.py — All checks passed
```

## Observability Changes

Not applicable — tests only, no telemetry changes.

## ADR Updates

Not applicable — this task does not touch architectural decisions.

## Unresolved Assumptions or Follow-Up

None. The three tests cover composer correctness (UT-001), DAG execution data flow (UT-002), and the full compose→execute regression path (IT-001/REG-001) for the previously broken "search for llama.cpp and tell me what it is" prompt.
