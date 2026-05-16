# Testing Rules

Choose tests based on task risk and confidence needed.

This guidance is language-agnostic and applies to frontend, backend, full-stack, CLI, service, API, and library work.

Do not add tests only to satisfy a category.
Prefer the smallest test that proves the behavior.

## Test selection

Add broader tests only when the task:

- crosses real boundaries
- changes critical user flows
- modifies permissions or trust boundaries
- affects performance risk
- changes observability
- fixes a known regression
- changes behavior shared by multiple features
- changes component behavior that users interact with
- changes interactive UI, forms, navigation, dialogs, menus, tables, or error states

If a category is not relevant, write:

```text
Not applicable — <specific reason>
```

## TDD and CDD testing split

Use TDD for backend, core logic, services, APIs, domain rules, validators, permissions, data transformations, and regressions.

Use CDD for frontend components: verify component states, semantic HTML, accessibility, inputs, outputs, events, and composition before relying on full E2E tests.

Good:
- Unit test domain validation before implementing it.
- Component test invalid, loading, submitting, and server-error states before composing a page.
- Component test accessible names, labels, roles, keyboard behavior, and error connections.
- Integration test API and database boundary when persistence changes.
- E2E test only the critical complete journey.

Bad:
- Use E2E for every validation branch.
- Use snapshots as the only component tests.
- Mock the database in an integration test whose risk is persistence.
- Skip component state tests and rely only on manual clicking.
- Skip accessibility tests after changing a form or dialog.

## Unit tests

Use unit tests for isolated rules, validators, mappers, permissions, reducers, hooks, components, and domain logic.

Good:
- Validate that `project.name` accepts 1–80 characters.
- Validate that duplicate invitations are rejected for the same project and email.
- Validate that only owners can update project settings.
- Validate that `ProjectForm` disables submit while saving.
- Validate that an invalid email shows the expected field error.

Bad:
- Test project creation end-to-end in a unit test.
- Mock every internal helper.
- Assert private method calls.
- Snapshot the entire page for one validation rule.

## Component tests

Use component tests for frontend behavior when the project has component-test support.

Good:
- Render `ProjectForm` with an empty name and verify the name error appears.
- Render `ProjectForm` in submitting state and verify the submit button is disabled.
- Render `InvitationPanel` with no invitations and verify the empty state explains the next action.
- Verify validation errors are associated with the related input.
- Verify the submit action is reachable by keyboard.
- Verify the button has an accessible name.

Bad:
- Test implementation-specific component internals.
- Snapshot large rendered trees without behavioral assertions.
- Skip keyboard and focus behavior for interactive components.
- Duplicate all E2E flows at component level.

## Integration tests

Use integration tests for real boundaries.

Good:
- Create a project through `POST /projects` and verify the database stores `name`, `description`, and `ownerId`.
- Invite a member through `POST /projects/:id/invitations` and verify a pending invitation is created.
- Call `PATCH /projects/:id/settings` as a member and verify the API returns `403`.
- Submit the connected project form against a test API adapter and verify success and error states.

Bad:
- Test database mocks only.
- Test route handlers without real middleware when middleware is the risk.
- Duplicate E2E coverage without boundary-specific assertions.
- Call a mocked service and call it integration.

## Smoke tests

Use smoke tests for shallow post-build or post-deploy confidence.

Good:
- Verify the dashboard loads for a signed-in user.
- Verify the project creation page opens without a client-side crash.
- Verify the health endpoint returns ready after deployment.
- Verify the CLI command starts and prints help.

Bad:
- Use smoke tests to verify every validation branch.
- Replace integration tests with smoke tests.
- Click through the whole app as a smoke test.
- Treat smoke tests as complete confidence.

## End-to-end tests

Use E2E tests for critical complete user journeys.

Good:
- User creates a project from the dashboard and sees it in the project list.
- Owner invites a member and sees the invitation as pending.
- Member opens project settings and sees access denied.
- User recovers from a failed save and successfully submits again.
- Keyboard user completes the project form when keyboard access is a critical requirement.

Bad:
- Add E2E for every field validation.
- Use E2E to test pure utility functions.
- Use E2E when a unit, component, or integration test gives the same confidence.
- Depend on brittle timing instead of observable UI states.

## Regression tests

Use regression tests for known previous defects.

Good:
- Duplicate invitation still shows “Member already invited.”
- Settings API still returns `403` for members after a permission refactor.
- Empty dashboard still renders after project search returns zero results.
- Form submission no longer sends duplicate requests after double-click.
- Modal focus no longer escapes behind the overlay after reopening.

Bad:
- Label every test as regression.
- Add regression tests without linking a bug, incident, or known failure.
- Test unrelated behavior in a regression test.
- Keep a regression test that no longer represents a real risk.

## Performance tests

Use performance tests for measurable latency, throughput, memory, rendering, or concurrency risk.

Good:
- Verify `POST /projects` stays under 300 ms p95 under normal load.
- Verify search typing stays under 100 ms interaction latency with 1,000 projects.
- Verify bulk invitation import does not exceed memory limits.
- Verify the dashboard does not rerender all cards when one filter changes, if that was the measured risk.

Bad:
- Add performance tests for static copy changes.
- Use vague assertions like “fast enough.”
- Measure locally and treat it as production evidence.
- Optimize before measuring the slow path.

## Security tests

Use security tests for authentication, authorization, input handling, data exposure, secrets, injection, abuse, and trust boundaries.

Good:
- Attempt to update another user’s project and verify `403`.
- Send forged `projectId` and verify the server rejects it.
- Save `<script>alert(1)</script>` as a project name and verify it renders as text.
- Verify logs do not contain tokens or passwords.
- Verify frontend-only permission hiding is backed by server-side authorization.

Bad:
- Only hide unauthorized UI controls.
- Trust client-side permission checks.
- Log raw request bodies.
- Skip security tests for role changes.
- Treat escaping as optional because the UI framework usually handles it.

## Usability and accessibility tests

Use usability and accessibility tests for user-facing clarity, semantic HTML, accessible names, roles, keyboard access, focus behavior, validation placement, empty states, loading states, and error recovery.

Good:
- Empty project form shows errors next to related fields.
- Create button prevents duplicate submissions while request is pending.
- Empty dashboard explains how to create the first project.
- Keyboard user can submit the form and read validation errors.
- Focus moves to the first invalid field after failed submit when that is the project convention.
- Required inputs have accessible names.
- Navigation uses links, and actions use buttons.
- Dialog focus moves inside on open and returns to the trigger on close.

Bad:
- Say “make it user friendly.”
- Test only happy-path visual appearance.
- Ignore loading and error states.
- Ignore keyboard and screen-reader behavior for interactive UI.
- Treat accessibility as separate from component behavior.
- Verify only colors for validation state.

## Observability tests

Use observability tests for logs, metrics, traces, analytics events, correlation IDs, and sensitive-data exclusion.

Good:
- Create a project and verify the log contains `projectId`, `ownerId`, request ID, and success result.
- Submit invalid form and verify validation failure metric increments.
- Call `POST /projects` and verify the trace includes API, service, repository, and database spans.
- Complete project creation and verify success analytics event emits once.
- Verify logs exclude descriptions, email bodies, tokens, passwords, and secrets.

Bad:
- Add logs without testing them.
- Track analytics twice on retry.
- Emit metrics without success or failure tags.
- Log sensitive payloads.
- Add frontend analytics events without confirming they are emitted once.

## Test quality

Tests must verify behavior, not implementation noise.

Good:
- Assert the API returns `403` for a member changing settings.
- Assert duplicate invitation returns the documented error code.
- Assert project appears after successful creation.
- Assert validation error is visible and associated with the correct field.
- Assert analytics event is emitted once on successful submission.
- Assert a form control has an accessible name.

Bad:
- Assert the private helper was called.
- Assert the exact internal function order.
- Snapshot the whole page for a small validation rule.
- Assert CSS class names unless styling behavior is the actual requirement.