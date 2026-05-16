# Task: Add integration tests for composed DAG flows

## Priority

P1 — Depends on the handoff fix because the tests would fail without the correct input format. Should be implemented immediately after Task 1 to prevent regression.

## Dependencies

- Depends on Task 1: Fix composed DAG tool→QA input handoff (the input-format fix must be in place for correct test behavior).
- No ADR dependency.
- Depends on existing test infrastructure: `tests/integration/`, `tests/unit/src/workflows/`.

## Context

The composed DAG flow (composer → planner → DAG execution → handler output) has no test that exercises a full tool-to-processing workflow. Existing tests cover:

- Individual tool selection (`tool_selection` eval fixtures, `test_tool_selection.py`)
- Individual handler behavior (handler unit tests)
- Simple single-node pipelines (integration `test_pipeline.py`)
- Gherkin scenarios for routing and tool selection (`features/`)

No test verifies that a prompt like "search for llama.cpp and tell me what it is" flows through the composer, produces a two-node DAG, executes both nodes, and returns a non-trivial answer containing content from the search results.

This gap means regressions in the DAG input handoff, compression, or node chaining go undetected.

## Use Cases

- **Feature**: Composed search-to-answer workflow integration
- **Scenario**: Full pipeline test with mocked web search
- **Given** a mock web search tool returns known results for a query
- **When** the user prompt contains a search request and a follow-up question
- **Then** the system returns an answer that contains content from the mock search results

## Definition of Ready

- Task 1 is implemented and merged.
- Mock infrastructure for `web_search` tool exists or can be injected.
- The `run_graph` function can be called with a mock LLM client.

## Functional Requirements

- `FR-001`: Add a unit test that verifies the composer produces a two-node DAG for search→QA prompts.
- `FR-002`: Add a unit test with mocked tools that verifies the full DAG execution for search→QA produces a `FinalAnswer` with non-trivial content.
- `FR-003`: The tests must inject mock tool results without making real network calls.
- `FR-004`: The test prompt must match the real user complaint: "search for llama.cpp and tell me what it is".

## Non-Functional Requirements

- `NFR-001`: Tests must be in the `unit` category (no LLM server required).
- `NFR-002`: Tests must complete in under 1 second.

## Observability Requirements

- `OBS-001`: Not applicable — tests verify behavior, not production telemetry.

## Acceptance Criteria

- `AC-001`: **Given** a mock web search that returns known text about "llama.cpp", **When** the system runs "search for llama.cpp and tell me what it is", **Then** the output contains keywords from the mock search result (e.g., "C/C++", "inference").
- `AC-002`: **Given** a mock web search returning known results, **When** the composer builds the DAG, **Then** the DAG has two nodes (tool → final) with the correct node types.
- `AC-003`: **Given** a prompt without a tool signal (e.g., "what is the capital of France"), **When** the composer runs, **Then** no DAG is composed and the fallback path is taken.

## Required Tests

### Unit Tests

- `UT-001`: Unit test for `DAGComposer.compose()` with "search for llama.cpp and tell me what it is" — verifies the returned `WorkflowGraph` has 2 nodes with correct types (function_calling then question_answering) and correct input formats. Covers `FR-001`, `FR-004`.
- `UT-002`: Orchestrated test of `run_graph()` with a composed DAG, mocked tool node (returns known text), mocked QA node (returns `FinalAnswer`), and mocked LLM — verifies the final output contains content from the tool node's output. Covers `FR-002`, `AC-001`.
- `UT-003`: Test that "what is the capital of France" does NOT compose a DAG (composer returns None). Covers `AC-003`.

### Integration Tests

- `IT-001`: **Scenario**: Full composed pipeline against a real mocked tool registry  
  **Given** a `ToolRegistry` with a mocked `web_search` that returns known results  
  **When** the assistant runs "search for llama.cpp and tell me what it is"  
  **Then** the orchestrated output contains the tool's mock result content  
  **And** the answer is non-empty and substantive  
  Covers `FR-002`, `AC-001`.

### Smoke Tests

Not applicable — no deployment or startup changes.

### End-to-End Tests

Not applicable — integration tests at the `run_graph` level provide sufficient coverage.

### Regression Tests

- `REG-001`: **Scenario**: The previously broken "search for llama.cpp and tell me what it is" prompt  
  **Given** the composed DAG input fix is in place  
  **When** the system processes the prompt  
  **Then** the answer contains substantive content from the tool results  
  **And** the answer is not just "llama.cpp"  
  Covers previous defect (no BUG-ID yet).

### Performance Tests

Not applicable — no measurable performance impact.

### Security Tests

Not applicable — no authentication, authorization, input handling, storage, secrets, or external communication changes.

### Usability Tests

Not applicable — no user-facing UI changes.

### Observability Tests

Not applicable — no telemetry changes.

## Definition of Done

- Tests are added in `tests/unit/src/workflows/` and/or `tests/unit/src/test_composer.py`.
- All tests pass with `pytest -m unit`.
- The tests use mocked tools and LLM — no network or model server required.
- Ruff lint (`ruff check .`) and mypy pass on new test files.
