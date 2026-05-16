# Planning Rules

Use these rules to create implementation plans that are concrete, sequenced, testable, and not overloaded.

## Task shape

Create one or more tasks.

Each task must be:

- short
- concrete
- testable
- self-contained
- ordered by priority and dependency
- understandable without previous conversation context

Do not create artificial tiny tasks.
Do not create bureaucratic sections with duplicated content.

## Tracer-bullet planning

Prefer tracer-bullet tasks: each task should deliver a thin, working vertical slice through the real UI, API, domain logic, persistence, and telemetry when applicable.

Avoid horizontal-only tasks that implement isolated layers without proving the end-to-end behavior.

Good:
- Implement project creation from dashboard form to API, service, database, success message, and telemetry.
- Implement member invitation from settings page to API, permission check, invitation record, pending state, and audit log.

Bad:
- Build all database tables first.
- Build all API endpoints first.
- Build all UI screens before connecting real behavior.

## Keep decisions open

Keep irreversible decisions open as long as practical: plan around stable behavior, boundaries, and contracts before locking in frameworks, databases, vendors, protocols, or infrastructure details.

Good:
- Define the project creation contract before choosing the final database migration strategy.
- Hide email delivery behind a notification port before choosing the provider.
- Keep analytics behind an event interface before choosing the analytics tool.

Bad:
- Couple domain logic directly to the database client.
- Put provider-specific API calls inside UI components.
- Choose a queue, cache, or vendor before the task proves the need.

## ADR planning

During planning, identify whether any task needs an ADR.

Create a lightweight ADR stub when a task depends on a decision that is:

- hard to reverse
- cross-cutting
- architecture-shaping
- security-sensitive
- infrastructure-related
- data-model-related
- scalability-related
- vendor-related
- protocol-related
- boundary-defining

Do not create ADRs for ordinary implementation details.

Good:
- Create an ADR stub before tasks depend on a notification port.
- Create an ADR stub before choosing how project audit events are stored.
- Create an ADR stub before adopting OpenTelemetry across services.

Bad:
- Create an ADR for renaming a component.
- Create an ADR for moving a helper function.
- Create an ADR for changing CSS spacing.

Good rule:
- Plan phase: identify ADR needed.
- Implementation phase: decide, validate, and complete ADR.

## Planning clarification rule

Before finalizing the plan, identify unresolved decisions, hidden assumptions, and missing constraints.

Ask one question at a time until the plan is clear enough to execute.

Each question must include numbered alternatives.
Mark the recommended alternative with `(recommended)`.
Keep each alternative short, concrete, and mutually exclusive.

Resolve dependencies between decisions before planning dependent tasks.

Walk the design tree from:

1. product behavior
2. data
3. API
4. UI
5. tests
6. security
7. observability
8. rollout

If a question can be answered by inspecting the codebase, delegate codebase exploration to a sub-agent instead of asking the requester.

The sub-agent must return only:

- decision-relevant findings
- file paths
- existing behavior
- constraints
- uncertainty

Do not ask questions already answered by existing code, tests, documentation, configuration, or sub-agent findings.

Good:
- Question: Should project names be unique per owner?
  1. Yes, enforce uniqueness per owner. `(recommended)`
  2. Allow duplicate names with different IDs.
  3. Enforce global uniqueness across all users.

- Question: Should invitations expire?
  1. Expire pending invitations after 7 days. `(recommended)`
  2. Never expire pending invitations.
  3. Expire pending invitations after 24 hours.

- Question: Which task must come first?
  1. Create project first because invitations require `projectId`. `(recommended)`
  2. Prototype invitation UI first with mocked project data.
  3. Build invitation API first with a temporary project fixture.

Bad:
- What should we do?
- Any other requirements?
- Should this be good?
- Is everything clear?

## Gherkin rule

Use Gherkin language for:

- Use Cases
- Integration Tests
- Smoke Tests
- End-to-End Tests
- Regression Tests

Highlight Gherkin reserved words in bold:

- **Feature**
- **Rule**
- **Scenario**
- **Given**
- **When**
- **Then**
- **And**
- **But**
- **Background**
- **Scenario Outline**
- **Examples**

## Requirement and test IDs

Use stable requirement and test IDs.

Required prefixes:

- `FR-001` for functional requirements.
- `NFR-001` for non-functional requirements.
- `OBS-001` for observability requirements.
- `AC-001` for acceptance criteria.
- `UT-001` for unit tests.
- `IT-001` for integration tests.
- `SMK-001` for smoke tests.
- `E2E-001` for end-to-end tests.
- `REG-001` for regression tests.
- `PT-001` for performance tests.
- `ST-001` for security tests.
- `UX-001` for usability tests.
- `OT-001` for observability tests.

Restart numbering inside each task.
Do not reuse IDs inside the same task.
Use IDs when linking tests to requirements, acceptance criteria, risks, or previous defects.

## Avoid duplication

Use each section for a separate concern:

- Use Cases explain real user or system scenarios.
- Requirements define required behavior and quality constraints.
- Acceptance Criteria define observable pass/fail outcomes.
- Tests verify selected requirements, acceptance criteria, risks, or regressions.

Do not restate the same sentence across sections.
Do not duplicate every acceptance criterion as an E2E test.

## Task sections

Every task must contain these sections:

1. Task title
2. Priority
3. Dependencies
4. Context
5. Use Cases
6. Definition of Ready
7. Functional Requirements
8. Non-Functional Requirements
9. Observability Requirements
10. Acceptance Criteria
11. Required Tests
12. Definition of Done

Use `assets/task-template.md` as the exact Markdown structure.

## Priority

State the task priority and why it comes in that order.

Good:
- P0 — Required before member invitations because projects must exist first.
- P1 — Depends on project creation because invitations require a valid `projectId`.
- P2 — Can be done after the core flow because it improves filtering, not creation.

Bad:
- High priority.
- Do this later.
- Important task.

## Dependencies

State which tasks, APIs, data models, decisions, ADRs, or external systems must exist first.

Good:
- Depends on Task 1: Create project.
- Depends on ADR `docs/adrs/001-use-notification-port.md`.
- Depends on the `projects` table with `id`, `name`, `description`, and `ownerId`.
- Depends on the authentication middleware exposing `currentUser.id`.
- No task dependency; can start after the API contract is approved.
- No ADR dependency; this task uses existing architecture.

Bad:
- Depends on backend.
- Depends on architecture.
- Depends on other tasks.
- Needs some setup.

## Context

Provide enough context for someone to understand the task without reading previous discussion.

Good:
- Users create projects from the dashboard before they invite members or configure settings.
- A project has a name, optional description, owner, member list, and settings page.
- Only the project owner can invite members or change project settings.

Bad:
- Implement this feature.
- Use the existing flow.
- Same as discussed before.

## Use Cases

State real user or system scenarios using Gherkin.
Describe who uses the feature and why.
Do not duplicate every acceptance criterion.

Good:
- **Feature**: Project creation
- **Scenario**: Team lead starts a client project
- **Given** Ana is a signed-in team lead
- **When** Ana creates a project named “Acme Migration”
- **Then** Ana can manage work for that client inside the project

Good:
- **Feature**: Member invitation
- **Rule**: Only project owners can invite members
- **Scenario**: Owner invites an engineer
- **Given** Ana owns the “Acme Migration” project
- **When** Ana invites `bruno@company.com`
- **Then** Bruno can be added to the project team after accepting the invitation

Bad:
- User uses the feature.
- Admin manages projects.
- Handle normal and error cases.
- Support the main flow.

## Definition of Ready

State what must be true before work starts.

Good:
- The `POST /projects` API contract includes request, response, and error formats.
- The `project.name`, `project.description`, and `project.ownerId` fields are defined.
- The owner, admin, and member permission rules are documented.
- Required ADR stubs are created and linked when the task depends on architecture decisions.

Bad:
- Requirements are clear.
- Backend is ready.
- Design is done.

## Functional Requirements

State what the feature must do.

Good:
- `FR-001`: A signed-in user can create a project from the dashboard.
- `FR-002`: The system rejects project names longer than 80 characters.
- `FR-003`: A project owner can invite a member using their email address.
- `FR-004`: A duplicated invitation shows “Member already invited.”

Bad:
- Add project features.
- Handle project errors.
- Make the project flow work.

## Non-Functional Requirements

State measurable quality constraints.

Good:
- `NFR-001`: The dashboard loads 1,000 projects in under 2 seconds.
- `NFR-002`: Project creation returns a response in under 300 ms at p95 under normal load.
- `NFR-003`: All project form labels, buttons, and errors use localization keys.
- `NFR-004`: API validation errors use the same `{ code, message, field }` format.

Bad:
- Make it fast.
- Make it scalable.
- Improve usability.
- Ensure quality.

## Observability Requirements

State what must be logged, measured, traced, and analyzed by design.

Good:
- `OBS-001`: Log project creation with `projectId`, `ownerId`, request ID, and result.
- `OBS-002`: Record a `project.created` metric with success and failure counts.
- `OBS-003`: Trace `POST /projects` across API, service, repository, and database calls.
- `OBS-004`: Track `project_create_submitted`, `project_create_succeeded`, and `project_create_failed` analytics events.
- `OBS-005`: Include validation error code, field name, and request ID in failed form submissions.
- `OBS-006`: Do not log project descriptions, emails, tokens, passwords, or personal secrets.

Bad:
- Add logs.
- Monitor the feature.
- Track user behavior.
- Make it observable.

## Acceptance Criteria

Define observable pass/fail outcomes.
Prefer Gherkin.
Do not duplicate the use cases word-for-word.

Good:
- `AC-001`: **Given** a signed-in user, **When** they submit a valid project form, **Then** the project appears on the dashboard.
- `AC-002`: **Given** a project name with 81 characters, **When** the user submits the form, **Then** the name field shows a validation error.
- `AC-003`: **Given** an invalid email, **When** the owner sends an invitation, **Then** the email field shows “Enter a valid email.”
- `AC-004`: **Given** a member without owner permission, **When** they open project settings, **Then** they see an access-denied message.

Bad:
- The form should work.
- Permissions should be respected.
- Errors should be handled.
- The user should have a good experience.

## Definition of Done

State what must be complete before the task is finished.
Do not repeat every required test category here.

Good:
- Code is implemented behind the correct domain, service, component, or adapter boundary.
- Required tests for this task pass.
- Loading, empty, validation, server error, and permission-denied states are handled where applicable.
- Required telemetry is implemented and verified.
- Required ADRs are updated from `Proposed` to `Accepted` or left with explicit open questions.
- API contracts, user-facing behavior, ADRs, or operational runbooks are documented when changed.

Bad:
- Code is done.
- Tests are added.
- Feature looks good.
- Everything works.