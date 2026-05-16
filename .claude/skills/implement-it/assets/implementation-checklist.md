# Implementation Checklist

Use this checklist while implementing.

## Before coding

- [ ] Read the assigned issue, task, story, or plan.
- [ ] Read related ADRs, if any.
- [ ] Inspect existing code before asking questions.
- [ ] Identify current architecture boundaries.
- [ ] Identify existing frontend component conventions, if UI changes are needed.
- [ ] Identify existing semantic HTML and accessibility conventions, if UI changes are needed.
- [ ] Identify existing backend service, handler, repository, or adapter conventions, if backend changes are needed.
- [ ] Identify existing tests and validation commands.
- [ ] Identify telemetry conventions, if relevant.
- [ ] Ask only unresolved questions that cannot be answered from code or docs.

## During coding

- [ ] Prefer a thin vertical slice.
- [ ] Use TDD for logic, services, APIs, permissions, data flows, and regressions when practical.
- [ ] Use CDD for frontend component behavior when practical.
- [ ] Use semantic HTML and native controls before ARIA.
- [ ] Treat accessibility as component behavior, not final polish.
- [ ] Use Atomic Design as a heuristic only when it fits the existing UI architecture.
- [ ] Keep dependency direction stable.
- [ ] Keep business rules outside controllers and UI components.
- [ ] Keep provider SDKs outside domain and application logic.
- [ ] Keep backend authorization authoritative.
- [ ] Keep component states explicit: loading, empty, error, disabled, success, and permission states where applicable.
- [ ] Preserve keyboard access, focus order, accessible names, labels, roles, and error announcements for interactive UI.
- [ ] Use existing naming and folder conventions.
- [ ] Avoid broad rewrites.
- [ ] Avoid speculative abstractions.
- [ ] Avoid workarounds that hide the root cause.
- [ ] Add or update the smallest meaningful tests.
- [ ] Add or update telemetry only when required or risk-reducing.

## Validation

- [ ] Run focused tests for changed behavior.
- [ ] Run component tests when UI state behavior changed.
- [ ] Run accessibility checks when interactive UI, forms, dialogs, navigation, menus, tables, or error states changed.
- [ ] Run integration tests when boundaries changed.
- [ ] Run typecheck when types or interfaces changed.
- [ ] Run lint when code style may be affected.
- [ ] Run build when frontend, routing, bundling, packaging, or public API changed.
- [ ] Run security, performance, usability, accessibility, or observability checks only when relevant.

## Before finishing

- [ ] Confirm all acceptance criteria are satisfied.
- [ ] Confirm required tests pass.
- [ ] Confirm no unrelated changes were introduced.
- [ ] Confirm frontend states, semantic HTML, and accessibility are handled when applicable.
- [ ] Confirm backend authorization and validation are enforced when applicable.
- [ ] Confirm ADRs are updated when needed.
- [ ] Confirm implementation summary is written.