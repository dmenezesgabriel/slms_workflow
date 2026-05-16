# Test Selection

Choose the smallest meaningful test set for each task.

Do not create tests only to satisfy a category.
Do not add full E2E, performance, security, usability, or observability tests by default.

Use broader tests only when the task:

- crosses real boundaries
- changes critical flows
- affects user-visible behavior
- changes permissions or trust boundaries
- affects performance risk
- modifies telemetry or operational behavior
- prevents a known regression

If a test category is not relevant, write:

```text
Not applicable — <specific reason>
```

## Test type distinction

Unit tests verify isolated rules, functions, validators, mappers, permissions, reducers, hooks, and components.

Integration tests verify real boundaries between API, service, database, queue, cache, filesystem, or external adapters.

Smoke tests verify that a critical path starts, loads, or completes shallowly after build or deployment.

End-to-end tests verify a complete user journey through the real application surface.

Regression tests verify that a previously broken behavior does not break again.

Performance tests verify measurable latency, throughput, memory, rendering, or concurrency constraints.

Security tests verify authorization, authentication, input handling, data exposure, secrets, injection, abuse, and trust boundaries.

Usability tests verify clarity, accessibility, validation placement, empty states, loading states, and error recovery.

Observability tests verify logs, metrics, traces, analytics events, correlation IDs, and sensitive-data exclusion.

## Unit tests

Use unit tests for isolated logic.

Good:
- `UT-001`: Validate that `project.name` accepts 1–80 characters. Covers `FR-002`.
- `UT-002`: Validate that duplicate invitations are rejected for the same project and email. Covers `FR-004`.
- `UT-003`: Validate that only owners can update project settings. Covers `FR-003`, `AC-004`.

Bad:
- Test validation.
- Test permissions.
- Test project creation.

## Integration tests

Use integration tests for real boundaries.
Use Gherkin when applicable.

Good:
- `IT-001`: **Scenario**: Project is persisted through the API  
  **Given** a signed-in user with ID `user-123`  
  **When** they call `POST /projects` with name “Acme Migration”  
  **Then** the database stores `name`, `description`, and `ownerId`  
  **And** the API returns `201`  
  Covers `FR-001`, `AC-001`.

Good:
- `IT-002`: **Scenario**: Invitation is created through the API  
  **Given** Ana owns project `project-123`  
  **When** Ana calls `POST /projects/project-123/invitations` with `bruno@company.com`  
  **Then** a pending invitation is stored for Bruno  
  **And** the API returns `201`  
  Covers `FR-003`.

Not applicable example:
- `IT-001`: Not applicable — this task changes only a pure validation function already covered by unit tests.

Bad:
- Test backend.
- Test database.
- Test integration.

## Smoke tests

Use smoke tests for build, deploy, startup, or shallow critical-path availability.

Good:
- `SMK-001`: **Scenario**: Dashboard loads after deployment  
  **Given** a signed-in user exists  
  **When** the user opens the dashboard  
  **Then** the dashboard loads without a client-side crash  
  Covers release confidence for `FR-001`.

Good:
- `SMK-002`: **Scenario**: Project creation page opens after deployment  
  **Given** a signed-in user is on the dashboard  
  **When** the user opens the create project page  
  **Then** the project form is visible  
  Covers critical path availability.

Not applicable example:
- `SMK-001`: Not applicable — this task changes only a backend validation helper and does not affect deploy availability.

Bad:
- Check the app.
- See if it loads.
- Test production.

## End-to-end tests

Use E2E tests only for complete critical user journeys.

Good:
- `E2E-001`: **Scenario**: User creates a project from the dashboard  
  **Given** a signed-in user is on the dashboard  
  **When** they create a project named “Acme Migration”  
  **Then** “Acme Migration” appears in the project list  
  Covers `FR-001`, `AC-001`.

Good:
- `E2E-002`: **Scenario**: Member is blocked from project settings  
  **Given** Bruno is a member of “Acme Migration”  
  **When** Bruno opens the project settings page  
  **Then** Bruno sees the access-denied page  
  Covers `AC-004`.

Not applicable example:
- `E2E-001`: Not applicable — this task changes an isolated validation helper and no complete user journey changes.

Bad:
- Click around.
- Test the whole app.
- Test the flow.

## Regression tests

Use regression tests only when preventing a known previous defect.

Good:
- `REG-001`: **Scenario**: Duplicate invitation still shows a clear error  
  **Given** `bruno@company.com` already has a pending invitation  
  **When** Ana invites `bruno@company.com` again  
  **Then** the form shows “Member already invited”  
  Covers previous defect `BUG-123`.

Not applicable example:
- `REG-001`: Not applicable — there is no known previous defect related to this task.

Bad:
- Add regression coverage.
- Make sure old bugs do not come back.
- Test previous problems.

## Performance tests

Use performance tests only for measurable performance risk.

Good:
- `PT-001`: Render 1,000 dashboard projects and verify typing in search stays under 100 ms interaction latency. Covers `NFR-001`.
- `PT-002`: Run normal-load project creation and verify `POST /projects` stays under 300 ms p95. Covers `NFR-002`.

Not applicable example:
- `PT-001`: Not applicable — this task only changes static empty-state copy and does not affect runtime behavior.

Bad:
- Make it fast.
- Test performance.
- Avoid slowness.

## Security tests

Use security tests for authentication, authorization, input handling, data exposure, secrets, injection, abuse, or trust boundaries.

Good:
- `ST-001`: Attempt to update another user’s project and verify the API returns `403`. Covers `AC-004`.
- `ST-002`: Send a forged `projectId` in the invitation request and verify the server rejects it. Covers `FR-003`.
- `ST-003`: Save `<script>alert(1)</script>` as a project name and verify it renders as text, not HTML. Covers input handling risk.

Not applicable example:
- `ST-001`: Not applicable — this task does not touch authentication, authorization, input handling, storage, secrets, or external communication.

Bad:
- Make it secure.
- Check auth.
- Avoid vulnerabilities.

## Usability tests

Use usability tests for clarity, accessibility, validation placement, empty states, loading states, and error recovery.

Good:
- `UX-001`: Submit an empty project form and verify errors appear next to `name` and `description`. Covers `AC-002`.
- `UX-002`: Click Create twice and verify the button prevents duplicate submissions. Covers duplicate-submission risk.
- `UX-003`: Open an empty dashboard and verify it explains how to create the first project. Covers `FR-001`.

Not applicable example:
- `UX-001`: Not applicable — this task changes only backend retry logic with no user-facing behavior change.

Bad:
- Make UI intuitive.
- Improve UX.
- Ensure it is easy to use.

## Observability tests

Use observability tests for logs, metrics, traces, analytics events, correlation IDs, and sensitive-data exclusion.

Good:
- `OT-001`: Create a project and verify the log contains `projectId`, `ownerId`, request ID, and success result. Covers `OBS-001`.
- `OT-002`: Submit an invalid form and verify the validation failure metric is incremented. Covers `OBS-002`.
- `OT-003`: Call `POST /projects` and verify the trace includes API, service, repository, and database spans. Covers `OBS-003`.
- `OT-004`: Complete project creation and verify the success analytics event is emitted once. Covers `OBS-004`.
- `OT-005`: Submit sensitive fields and verify logs do not contain project description, email body, tokens, or secrets. Covers `OBS-006`.

Not applicable example:
- `OT-001`: Not applicable — this task does not introduce or modify operationally relevant behavior.

Bad:
- Check logs.
- Monitor the feature.
- Test telemetry.