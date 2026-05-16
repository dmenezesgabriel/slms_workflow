# Implementation Rules

Use these rules to implement tasks safely, directly, and without unnecessary complexity.

This skill is language-agnostic.
Use the existing project stack, package manager, framework, commands, style, and architecture.

## Implementation scope

Implement only what the assigned issue, task, story, or user request requires.

Do not add unrelated features.
Do not rewrite working code unless needed for the task.
Do not hide failures with workarounds.
Do not fragment code into many tiny modules without a clear design reason.
Do not introduce a new architectural style when the project already has a clear working structure.

Good:
- Implement project creation through the existing service boundary.
- Add validation for project names where input rules already live.
- Update only the affected dashboard form, API handler, service, repository, and tests.
- Follow the existing component structure before adding Atomic Design naming.

Bad:
- Rewrite the whole dashboard.
- Replace the router because one route needs validation.
- Add a generic framework for future project workflows.
- Patch the UI to ignore backend errors.
- Introduce Atomic Design folders into a project that already has a consistent feature-based UI structure.

## Principle selection

Use design principles only when they help the current task.

Apply SOLID, design patterns, Ports and Adapters, Clean Architecture, Component-Driven Development, semantic HTML, accessibility, and Atomic Design only when they reduce current risk, clarify boundaries, improve testability, improve accessibility, or match the existing project architecture.

Do not introduce abstractions, layers, adapters, factories, ports, design-system structure, or architectural patterns just because they are considered good practice.

Good:
- Add a `NotificationPort` because the task touches a volatile email provider.
- Extract a validator because the same rule is used by API and UI.
- Add a component boundary because the form has multiple states and tests.
- Use a native `<button>` because the UI action is clickable.
- Keep a simple function when there is only one behavior and no boundary risk.
- Follow the existing feature-folder structure instead of forcing Atomic Design.

Bad:
- Add ports for every dependency.
- Add factories for single constructors.
- Add Atomic Design folders for one small component.
- Add a design pattern before there is variation.
- Use ARIA to imitate a button with a `div` when a native button works.
- Hide a broken dependency behind a workaround instead of fixing it.
- Add Clean Architecture layers to a small isolated script.

## Codebase exploration

Inspect the codebase before asking questions when the answer can be discovered.

Look for:

- existing issue file or task description
- related tests
- existing domain models
- existing services, use cases, or handlers
- existing components and UI states
- existing semantic HTML and accessibility patterns
- existing adapters and repositories
- existing routes, pages, commands, or entry points
- existing validation style
- existing telemetry patterns
- existing ADRs

Good:
- Search for existing project creation flow before adding a new one.
- Read current permission checks before implementing a new role rule.
- Inspect existing telemetry helpers before adding logs or metrics.
- Inspect existing component stories or examples before creating a new component API.
- Inspect existing form accessibility patterns before adding a new form.

Bad:
- Ask where validation belongs before checking the codebase.
- Add a new logger without checking existing logging patterns.
- Create a new folder structure without reading current architecture.
- Add a new component pattern without checking existing UI conventions.
- Add custom ARIA widgets before checking whether native controls are already used.

## Clarification rule

Ask only when the task cannot be implemented safely from the issue, codebase, tests, docs, or ADRs.

Ask one question at a time.

Each question must include numbered alternatives.
Mark the recommended alternative with `(recommended)`.

Good:
- Question: Should duplicate project names be rejected per owner?
  1. Reject duplicates per owner. `(recommended)`
  2. Allow duplicates with different IDs.
  3. Reject duplicates globally.

Bad:
- What should I do?
- Any other requirements?
- Is this correct?
- Should I make it better?

## TDD workflow

Use Test-Driven Development when practical for logic, services, APIs, domain rules, permissions, data transformations, regressions, and backend behavior.

Default loop:

1. Add or update the smallest meaningful failing test.
2. Implement the simplest correct behavior.
3. Refactor while tests stay green.
4. Repeat until the task is complete.

Good:
- Add a unit test for the 80-character project name limit before implementing validation.
- Add an integration test for `POST /projects` persistence before wiring the repository.
- Add a regression test before fixing a known duplicate-invitation bug.
- Add a permission test before changing owner-only settings behavior.

Bad:
- Write tests only after manual implementation.
- Add snapshot tests that only freeze markup.
- Add tests that assert implementation details instead of behavior.
- Skip tests because the change is small but risky.

## Component-Driven Development workflow

Use Component-Driven Development for frontend UI work when practical.

Build and verify the smallest useful component or composition before wiring the full page.

Default loop:

1. Identify the component boundary.
2. Define props, inputs, events, states, and accessibility behavior.
3. Implement semantic HTML and native controls first.
4. Implement isolated states first.
5. Verify loading, empty, error, disabled, success, focus, keyboard, and permission states where applicable.
6. Compose the component into the page or flow.
7. Add integration, smoke, or E2E coverage only when the composed behavior needs it.

Good:
- Build `ProjectForm` with valid, invalid, submitting, and server-error states before wiring the dashboard.
- Build `InvitationList` with empty, pending, accepted, and failed states before connecting the API.
- Use `<button>` for submit actions and `<a>` for navigation.
- Verify keyboard navigation and form error announcements before composing the full settings page.
- Use existing story, preview, fixture, or component test patterns when available.

Bad:
- Build the whole page before testing component behavior.
- Hide all state handling inside one large screen component.
- Add E2E tests for every visual state instead of component-level behavior tests.
- Create a design system abstraction for one component.
- Use clickable `div` elements for buttons or links.

## Semantic HTML and accessibility

For frontend work, accessibility is part of implementation, not a final polish step.

Use semantic HTML before ARIA.
Use native elements before custom widgets.
Use ARIA only when native semantics are not enough.

Good:
- Use `<button>` for actions.
- Use `<a href="...">` for navigation.
- Use `<label>` associated with each form control.
- Use field-level error text connected to the invalid input.
- Use headings in logical order.
- Use lists, tables, forms, and landmarks when they match the content.
- Keep focus visible and predictable.
- Ensure dialogs move focus in, trap focus when open, and restore focus when closed.
- Announce async validation or save errors when needed.

Bad:
- Use `<div onClick>` as a button.
- Use `<span>` as a link.
- Remove focus outlines without replacement.
- Add ARIA roles that conflict with native semantics.
- Use placeholders as the only label.
- Render form errors far from the related field.
- Hide interactive controls from keyboard users.

## Atomic Design guidance

Use Atomic Design as a UI organization heuristic when it fits the existing project.

Atomic Design terms:

- Atoms: smallest UI primitives, such as buttons, labels, inputs, icons, and tokens.
- Molecules: small composed controls, such as search fields, form rows, and validation fields.
- Organisms: larger sections, such as project cards, invitation panels, and navigation bars.
- Templates: page layouts without final data.
- Pages: real screens with data, routing, permissions, and user flows.

Good:
- Put reusable input behavior in a field component instead of duplicating validation markup.
- Compose `ProjectNameField` and `DescriptionField` into `ProjectForm`.
- Compose `ProjectForm` into the dashboard project creation page.
- Keep page-level data loading outside small presentational components when the project already separates them.

Bad:
- Force Atomic Design folder names into a project that uses feature folders consistently.
- Create atoms, molecules, organisms, templates, and pages for a tiny one-off screen.
- Split every button, label, and wrapper into separate files without reuse.
- Move business logic into UI primitives.

## Backend and core implementation

For backend, service, CLI, library, data, or domain work, prefer TDD and clear boundaries.

Good:
- Implement validation in a domain validator or application service.
- Keep HTTP parsing in the API boundary.
- Keep persistence details inside repositories or data adapters.
- Keep external provider calls inside infrastructure adapters.
- Return consistent domain or application errors.

Bad:
- Put domain rules inside controllers.
- Let database row shape leak into UI or API contracts by accident.
- Call provider SDKs directly from business logic.
- Make CLI output hard to parse when automation needs structured output.

## Frontend implementation

For frontend work, prefer CDD, semantic HTML, accessibility, behavior tests, and existing component conventions.

Good:
- Implement component states before wiring the API.
- Keep business rules in shared validators or application logic when used by backend too.
- Keep UI permission checks as presentation guards, not the source of truth.
- Show validation errors next to the related field.
- Preserve keyboard access, focus behavior, labels, roles, and error announcements.
- Prefer native form behavior before custom JavaScript behavior.

Bad:
- Trust frontend-only authorization.
- Put all validation only in UI when backend must enforce it.
- Create one large component with fetching, validation, permissions, formatting, and rendering mixed together.
- Use visual snapshots as the only test for behavior.
- Treat accessibility as optional cleanup.

## Vertical-slice implementation

Prefer a thin, working vertical slice over isolated horizontal layers.

Good:
- Implement dashboard form, API route, service rule, database persistence, success message, and telemetry for project creation.
- Implement invitation request, permission check, invitation record, pending state, and audit log.
- Implement a component state, its page integration, API call, and error handling when the task is user-facing.

Bad:
- Build every database table first.
- Build all UI screens before connecting real behavior.
- Add every repository method before one user flow works.
- Build a design system before proving one working screen.

## Validation loop

Run the smallest relevant validation set after each meaningful change.

Use available project commands first.

Common validation command names:

```bash
npm test
npm run test
npm run lint
npm run typecheck
npm run build
pnpm test
pnpm lint
pnpm typecheck
pnpm build
yarn test
yarn lint
yarn typecheck
yarn build
pytest
ruff check .
mypy .
go test ./...
cargo test
dotnet test
mvn test
gradle test
```

Good:
- Run the specific unit test after changing a validator.
- Run the API integration test after changing the service and repository.
- Run typecheck after changing shared interfaces.
- Run build after changing frontend routing or bundling.
- Run component tests after changing UI state behavior.
- Run accessibility checks when interactive UI, forms, dialogs, navigation, or error states changed.

Bad:
- Skip validation because the change looks simple.
- Run only lint after changing business logic.
- Run the entire suite repeatedly when a focused test is enough.
- Run only component tests after changing authorization.
- Skip accessibility checks after changing a form.

## Error handling

Handle expected failures explicitly.

Good:
- Return `400` with `{ code, message, field }` for validation errors.
- Return `403` when a member changes owner-only settings.
- Show inline form errors next to the related field.
- Associate form errors with the related input.
- Preserve focus or announce errors when a form submission fails.
- Log unexpected failures with request ID and safe context.

Bad:
- Catch and ignore errors.
- Return generic `500` for validation failures.
- Show “Something went wrong” for every error.
- Log tokens, passwords, email bodies, or personal secrets.
- Disable a broken button instead of fixing the failing state.

## Observability during implementation

Implement telemetry when required by the task, risk, or existing pattern.

Good:
- Log project creation with `projectId`, `ownerId`, request ID, and result.
- Emit `project.created` metric with success and failure tags.
- Trace API, service, repository, and database spans for critical flows.
- Track `project_create_succeeded` once after successful creation.
- Exclude descriptions, email bodies, tokens, passwords, and secrets from logs.

Bad:
- Add logs everywhere.
- Track every click by default.
- Log raw request bodies.
- Add metrics without names, tags, or usage.
- Add analytics that duplicates existing events.

## Completion rule

Implementation is complete only when:

- task behavior is implemented
- required tests pass
- relevant validations pass
- architecture boundaries are respected
- frontend semantic HTML, accessibility, and state behavior are handled when applicable
- observability requirements are satisfied when applicable
- ADRs are updated when applicable
- implementation summary is written