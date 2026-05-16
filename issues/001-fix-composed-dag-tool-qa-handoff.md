# Task: Fix composed DAG tool-to-QA input handoff

## Priority

P0 — Required before other quality improvements because the systemic input-format issue causes poor answers in all composed tool→QA workflows (e.g., "search for X and tell me what it is").

## Dependencies

- No task dependency; the composer and question-answering handler exist and are independently testable.
- No ADR dependency; this task modifies existing code within current architecture boundaries.
- Depends on `src/workflows/composer.py:150-159` (`_processing_format`).
- Depends on `src/handlers/question_answering.py:34-63` (`QuestionAnsweringHandler.handle`).
- Depends on `src/nodes/question_answering_node.py` (`QuestionAnsweringNode.execute`).

## Context

When the DAG composer creates an on-demand workflow for a prompt like "search for llama.cpp and tell me what it is", it builds a two-node DAG:

1. `function_calling` node (tool) → executes web search, returns `FinalAnswer`
2. `question_answering` node (final) → receives the compressed tool output + query

The composer's `_processing_format` (`composer.py:150`) builds the final node input as:

```
{tool}\n\nQuestion: {query}
```

This string is the only input the `question_answering` handler receives. The handler then:

1. Calls `self._retriever.fetch_context(user_input)` — which runs `plan_retrieval` on the **combined** string (tool results + query). The tool results contain URLs, entities, and temporal keywords that trigger wrong retrieval strategies (e.g., `url_fetch` on an already-fetched URL).
2. Wraps the result: `Context:\n<retrieved>\n\nQuestion: <user_input>` — which duplicates the "Question:" label and embeds the tool output inside the question field instead of labeling it as context.

The final LLM prompt becomes confusing and multi-layered, causing the small model (Qwen3.5-0.8B) to return minimal or incorrect answers.

## Use Cases

- **Feature**: Composed search-to-answer workflow
- **Scenario**: User asks to search for a topic and explain it
- **Given** the user provides a prompt with a search request and a processing intent
- **When** the composer builds a DAG with a tool node followed by a QA node
- **Then** the QA node receives cleanly separated context and question
- **And** the retriever is called on the original user query, not the combined string

## Definition of Ready

- The `_processing_format` function in `composer.py` is analyzed and understood.
- The `QuestionAnsweringHandler.handle()` input-processing logic is analyzed.
- Unit tests for both modules demonstrate the current broken behavior.
- Existing eval fixtures for tool_selection and routing are understood.

## Functional Requirements

- `FR-001`: The QA handler must extract the original user query from pre-formatted DAG input and use only the query for retrieval.
- `FR-002`: The QA handler must not re-wrap input that already has a Context section.
- `FR-003`: When a tool node (e.g., function_calling) feeds the QA node via the composer, the tool output must appear as labeled context and the original query as the question.
- `FR-004`: The retriever must be called with only the original user query, not the combined node input.
- `FR-005`: The summarization and classification processing formats must remain unchanged (they do not call a retriever).

## Non-Functional Requirements

- `NFR-001`: The change must not break existing unit tests for `composer.py` or `question_answering.py`.
- `NFR-002`: The change must not add new dependencies or change the `WorkflowNode` protocol.

## Observability Requirements

- `OBS-001`: Trace output for composed DAGs must still log the DAG node execution and handler intent.
- `OBS-002`: No new log levels or metrics are required; existing tracing covers the flow.

## Acceptance Criteria

- `AC-001`: **Given** a composed DAG with tool node outputting web search results, **When** the QA handler processes the rendered input, **Then** the LLM receives a prompt with tool results labeled as context and the original query as the question, with no duplicate "Question:" sections.
- `AC-002`: **Given** a composed DAG input like `"<tool results>\n\nQuestion: <query>"`, **When** the QA handler calls `fetch_context`, **Then** it passes only `<query>` to the retriever, not the full combined string.
- `AC-003`: **Given** a QA-only prompt (not from a DAG), **When** the handler processes it, **Then** the behavior is unchanged from the current implementation.

## Required Tests

### Unit Tests

- `UT-001`: Test that `QuestionAnsweringHandler.handle()` with a string containing `\n\nQuestion: ` extracts the part after the final `Question: ` for `fetch_context`. Covers `FR-001`, `FR-004`.
- `UT-002`: Test that `QuestionAnsweringHandler.handle()` with a string starting with `Context:\n` does not add another `Context:\n` wrapper. Covers `FR-002`.
- `UT-003`: Test that `QuestionAnsweringHandler.handle()` with a plain query (no `\n\nQuestion: `) follows the original code path unchanged. Covers `FR-005`, `AC-003`.
- `UT-004`: Test that the composer's `_processing_format` for `question_answering` produces `"Context:\n{tool}\n\nQuestion: {query}"`. Covers `FR-003`.

### Integration Tests

Not applicable — this task modifies isolated handler and composer logic that can be tested with unit tests using mocked retriever.

### Smoke Tests

Not applicable — no deployment or startup changes.

### End-to-End Tests

Not applicable — the changes are internal to handler/composer logic and can be verified with unit tests.

### Regression Tests

Not applicable — no known previous defect related to this specific issue.

### Performance Tests

Not applicable — no measurable performance impact.

### Security Tests

Not applicable — no authentication, authorization, input handling, storage, secrets, or external communication changes.

### Usability Tests

Not applicable — no user-facing UI changes.

### Observability Tests

- `OT-001`: Not applicable — existing trace flow is unchanged.

## Definition of Done

- Code is implemented in `src/workflows/composer.py` and `src/handlers/question_answering.py` (and/or `src/nodes/question_answering_node.py`).
- Required unit tests for this task pass.
- All existing unit tests pass (`pytest -m unit`).
- Ruff lint (`ruff check .`) and mypy pass.
- The composed DAG flow produces cleanly formatted LLM prompts with context and question properly separated.
