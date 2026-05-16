# Implementation Summary: Fix composed DAG tool-to-QA input handoff

## Related Task

- `issues/001-fix-composed-dag-tool-qa-handoff.md`

## Files Changed

- `src/workflows/composer.py:159` — Changed `_processing_format` default case from `"{value}\n\nQuestion: {{query}}"` to `"Context:\n{value}\n\nQuestion: {{query}}"` so tool results are explicitly labeled as context.
- `src/handlers/question_answering.py:34-53` — Added DAG-formatted input detection: when the input contains `\n\nQuestion: `, the original user query is extracted (via `rsplit`) and passed to `fetch_context` instead of the combined string. The handler no longer re-wraps pre-formatted input with another `Context:\n...\n\nQuestion: ...` layer.
- `tests/unit/src/workflows/test_composer.py:68` — Added assertion for the new `Context:\n{tool}\n\nQuestion: {query}` input format on the QA node.
- `tests/unit/src/handlers/test_question_answering.py:247-310` — Added 4 new test methods covering DAG-formatted input extraction, no-re-wrap behavior, additional context appending, and `rsplit` edge case.

## Behavior Implemented

- When the DAG composer creates a tool→QA workflow, the final node input format labels tool results as context: `"Context:\n{tool}\n\nQuestion: {query}"` instead of `"{tool}\n\nQuestion: {query}"`.
- The `QuestionAnsweringHandler` detects DAG-formatted input (contains `\n\nQuestion: `), extracts the original query via `rsplit`, and passes only the query to the retriever.
- When the retriever returns additional context for a DAG-sourced input, it is added as `Additional context:` rather than re-wrapping the whole input.
- Plain (non-DAG) input follows the original code path unchanged.

## Design Notes

- The split uses `rsplit("\n\nQuestion: ", 1)` instead of `split` to handle edge cases where tool results might themselves contain "Question:" text.
- The `WorkflowNode` protocol is unchanged — the handoff still uses a single string; the labeling convention (`Context:\n` prefix, `\n\nQuestion: ` separator) is the contract.
- Summarization and classification processing formats are untouched (`FR-005`).

## Tests Added or Updated

- `tests/unit/src/workflows/test_composer.py` — Updated `test_compose_builds_wikipedia_to_question_answering_graph` to assert the new `Context:\n{tool}\n\nQuestion: {query}` format (covers `UT-004`).
- `tests/unit/src/handlers/test_question_answering.py::test_extracts_original_query_from_dag_formatted_input` — Verifies `fetch_context` is called with the extracted original query (covers `UT-001`, `FR-001`, `FR-004`).
- `tests/unit/src/handlers/test_question_answering.py::test_does_not_re_wrap_when_dag_formatted_input_has_no_additional_context` — Verifies the pre-formatted input is passed through as-is when no RAG context is found (covers `UT-002`, `FR-002`).
- `tests/unit/src/handlers/test_question_answering.py::test_appends_additional_context_when_dag_formatted_input_has_retrieved_context` — Verifies additional RAG context is appended without duplicating the Question label (covers `FR-003`).
- `tests/unit/src/handlers/test_question_answering.py::test_uses_rsplit_to_handle_question_in_tool_results` — Verifies correct query extraction when tool results contain the word "Question:" (covers edge case).

## Test Categories Not Applicable

- `Integration`: Not applicable — the changes modify isolated handler/composer logic that can be tested with unit tests using mocked retriever and LLM.
- `Smoke`: Not applicable — no deployment or startup changes.
- `E2E`: Not applicable — no user-facing UI or complete journey changes.
- `Regression`: Not applicable — no known previous defect.
- `Performance`: Not applicable — no measurable performance impact.
- `Security`: Not applicable — no authentication, authorization, or trust boundary changes.
- `Usability`: Not applicable — no user-facing UI changes.
- `Observability`: Not applicable — existing trace flow is unchanged.

## Validation Run

```text
uv run pytest tests/unit/src/workflows/test_composer.py tests/unit/src/handlers/test_question_answering.py -v — 40 passed
uv run ruff check src/workflows/composer.py src/handlers/question_answering.py tests/unit/src/workflows/test_composer.py tests/unit/src/handlers/test_question_answering.py — All checks passed
uv run mypy src/workflows/composer.py src/handlers/question_answering.py — No errors in changed files (pre-existing error in src/graph/trace_types.py:44)
```

## Observability Changes

Not applicable — existing trace flow covers DAG node execution and handler intent. No new telemetry was added.

## ADR Updates

Not applicable — this task modifies existing code within current architecture boundaries. No architectural decision was introduced.

## Unresolved Assumptions or Follow-Up

- The `compress` function's sentence-level splitting on web search results may still lose information from structured tool output. If answers remain poor after this handoff fix, a follow-up task should address compression for semi-structured text (e.g., web result titles, URLs, and snippets).
- The `\n\nQuestion: ` separator in the `_processing_format` is now a contract between the composer and the handler. If new processing intents are added, they must either not call the retriever or follow the same format convention.
