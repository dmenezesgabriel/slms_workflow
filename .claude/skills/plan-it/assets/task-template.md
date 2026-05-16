# Task: <clear task name>

## Priority

<P0 | P1 | P2> — <short reason this task has this priority>.

Example:
- P0 — Required before member invitations because projects must exist first.

## Dependencies

- <Dependency 1>
- <Dependency 2>
- <No task dependency; can start after...>
- <No ADR dependency; this task uses existing architecture.>

Example:
- Depends on Task 1: Create project.
- Depends on ADR `docs/adrs/001-use-notification-port.md`.
- Depends on the `projects` table with `id`, `name`, `description`, and `ownerId`.
- Depends on the authentication middleware exposing `currentUser.id`.
- No task dependency; can start after the API contract is approved.
- No ADR dependency; this task uses existing architecture.

## Context

<Short self-contained explanation of the task. Include enough context to understand it without previous discussion.>

Example:
- Users create projects from the dashboard before they invite members or configure settings.
- A project has a name, optional description, owner, member list, and settings page.
- Only the project owner can invite members or change project settings.

## Use Cases

Use Gherkin. Highlight reserved words in bold.

- **Feature**: <feature name>
- **Scenario**: <real user or system scenario>
- **Given** <initial context>
- **When** <action happens>
- **Then** <business outcome is achieved>

Example:
- **Feature**: Project creation
- **Scenario**: Team lead starts a client project
- **Given** Ana is a signed-in team lead
- **When** Ana creates a project named “Acme Migration”
- **Then** Ana can manage work for that client inside the project

## Definition of Ready

- <Specific condition required before work starts>
- <Specific contract, model, rule, or decision that must exist>
- <Specific dependency that must be available>
- <Required ADR stub exists when the task depends on an architectural decision>

Example:
- The `POST /projects` API contract includes request, response, and error formats.
- The `project.name`, `project.description`, and `project.ownerId` fields are defined.
- The owner, admin, and member permission rules are documented.
- ADR `docs/adrs/001-use-notification-port.md` exists because this task depends on the notification boundary.

## Functional Requirements

- `FR-001`: <specific behavior the system must provide>
- `FR-002`: <specific validation, rule, or action>
- `FR-003`: <specific user-visible or system-visible behavior>

Example:
- `FR-001`: A signed-in user can create a project from the dashboard.
- `FR-002`: The system rejects project names longer than 80 characters.
- `FR-003`: A project owner can invite a member using their email address.

## Non-Functional Requirements

- `NFR-001`: <specific measurable quality constraint>
- `NFR-002`: <specific reliability, performance, accessibility, localization, or compatibility constraint>
- `NFR-003`: <specific consistency or maintainability constraint>

Example:
- `NFR-001`: Project creation returns a response in under 300 ms at p95 under normal load.
- `NFR-002`: API validation errors use the same `{ code, message, field }` format.
- `NFR-003`: All project form labels, buttons, and errors use localization keys.

## Observability Requirements

- `OBS-001`: <specific log requirement>
- `OBS-002`: <specific metric requirement>
- `OBS-003`: <specific tracing requirement>
- `OBS-004`: <specific analytics requirement>
- `OBS-005`: <specific sensitive-data exclusion rule>

Example:
- `OBS-001`: Log project creation with `projectId`, `ownerId`, request ID, and result.
- `OBS-002`: Record a `project.created` metric with success and failure counts.
- `OBS-003`: Trace `POST /projects` across API, service, repository, and database calls.
- `OBS-004`: Track `project_create_succeeded` once after successful creation.
- `OBS-005`: Do not log project descriptions, emails, tokens, passwords, or personal secrets.

## Acceptance Criteria

Use observable pass/fail outcomes. Prefer Gherkin.

- `AC-001`: **Given** <context>, **When** <action>, **Then** <observable result>.
- `AC-002`: **Given** <context>, **When** <action>, **Then** <observable result>.
- `AC-003`: **Given** <context>, **When** <action>, **Then** <observable result>.

Example:
- `AC-001`: **Given** a signed-in user, **When** they submit a valid project form, **Then** the project appears on the dashboard.
- `AC-002`: **Given** a project name with 81 characters, **When** the user submits the form, **Then** the name field shows a validation error.

## Required Tests

Choose the smallest meaningful test set for this task.
Do not create tests only to satisfy a category.
If a category is not relevant, write `Not applicable — <specific reason>`.

### Unit Tests

- `UT-001`: <isolated rule, function, validator, mapper, permission, reducer, hook, or component test>. Covers `<FR/AC/Risk ID>`.
- `UT-002`: Not applicable — <specific reason>.

Example:
- `UT-001`: Validate that `project.name` accepts 1–80 characters. Covers `FR-002`.

### Integration Tests

Use Gherkin when applicable.

- `IT-001`: **Scenario**: <boundary behavior being verified>  
  **Given** <realistic system state>  
  **When** <API/service/repository action happens>  
  **Then** <persistent or integration result is verified>  
  **And** <response, event, queue message, or side effect is verified>  
  Covers `<FR/AC/Risk ID>`.

Example:
- `IT-001`: **Scenario**: Project is persisted through the API  
  **Given** a signed-in user with ID `user-123`  
  **When** they call `POST /projects` with name “Acme Migration”  
  **Then** the database stores `name`, `description`, and `ownerId`  
  **And** the API returns `201`  
  Covers `FR-001`, `AC-001`.

### Smoke Tests

Use only for critical build, deploy, startup, or shallow availability checks.

- `SMK-001`: **Scenario**: <critical path starts or loads>  
  **Given** <minimal valid state>  
  **When** <critical page, command, endpoint, or service starts>  
  **Then** <it loads, responds, or completes without crash>  
  Covers `<release confidence or critical path>`.

Example:
- `SMK-001`: **Scenario**: Dashboard loads after deployment  
  **Given** a signed-in user exists  
  **When** the user opens the dashboard  
  **Then** the dashboard loads without a client-side crash  
  Covers release confidence for `FR-001`.

### End-to-End Tests

Use only for complete critical user journeys.

- `E2E-001`: **Scenario**: <complete user journey>  
  **Given** <realistic user state>  
  **When** <user completes the journey through the app UI>  
  **Then** <final user-visible result is shown>  
  Covers `<FR/AC/Risk ID>`.

Example:
- `E2E-001`: **Scenario**: User creates a project from the dashboard  
  **Given** a signed-in user is on the dashboard  
  **When** they create a project named “Acme Migration”  
  **Then** “Acme Migration” appears in the project list  
  Covers `FR-001`, `AC-001`.

### Regression Tests

Use only when preventing a known previous defect.

- `REG-001`: **Scenario**: <previous defect does not return>  
  **Given** <state that previously failed>  
  **When** <previous failure action happens>  
  **Then** <fixed behavior remains correct>  
  Covers previous defect `<BUG-ID>`.

Example:
- `REG-001`: **Scenario**: Duplicate invitation still shows a clear error  
  **Given** `bruno@company.com` already has a pending invitation  
  **When** Ana invites `bruno@company.com` again  
  **Then** the form shows “Member already invited”  
  Covers previous defect `BUG-123`.

### Performance Tests

- `PT-001`: <measurable latency, throughput, memory, rendering, or concurrency test>. Covers `<NFR/Risk ID>`.
- `PT-002`: Not applicable — <specific reason>.

Example:
- `PT-001`: Run normal-load project creation and verify `POST /projects` stays under 300 ms p95. Covers `NFR-001`.

### Security Tests

- `ST-001`: <authorization, authentication, input handling, data exposure, secrets, injection, abuse, or trust-boundary test>. Covers `<FR/AC/Risk ID>`.
- `ST-002`: Not applicable — <specific reason>.

Example:
- `ST-001`: Attempt to update another user’s project and verify the API returns `403`. Covers `AC-004`.

### Usability Tests

- `UX-001`: <clarity, accessibility, validation placement, empty state, loading state, or error recovery test>. Covers `<AC/Risk ID>`.
- `UX-002`: Not applicable — <specific reason>.

Example:
- `UX-001`: Submit an empty project form and verify errors appear next to `name` and `description`. Covers `AC-002`.

### Observability Tests

- `OT-001`: <log, metric, trace, analytics event, correlation ID, or sensitive-data exclusion test>. Covers `<OBS ID>`.
- `OT-002`: Not applicable — <specific reason>.

Example:
- `OT-001`: Create a project and verify the log contains `projectId`, `ownerId`, request ID, and success result. Covers `OBS-001`.

## Definition of Done

- Code is implemented behind the correct domain, service, component, or adapter boundary.
- Required tests for this task pass.
- Loading, empty, validation, server error, and permission-denied states are handled where applicable.
- Required telemetry is implemented and verified.
- Required ADRs are updated from `Proposed` to `Accepted` or left with explicit open questions.
- API contracts, user-facing behavior, ADRs, or operational runbooks are documented when changed.