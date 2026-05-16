# Design Rules

Use these rules to keep implementation maintainable, testable, accessible, and easy to change.

This skill is language-agnostic.
Apply principles through the project’s existing language, framework, and architecture.

## Design goal

Implement the task with the least design needed to be correct, testable, readable, accessible, and easy to change.

Use SOLID, design patterns, Ports and Adapters, Clean Architecture, Component-Driven Development, semantic HTML, accessibility, and Atomic Design as decision tools, not mandatory ceremonies.

Apply a principle only when it reduces current risk, clarifies responsibility, protects a volatile boundary, improves testability, improves accessibility, or follows existing project architecture.

Do not introduce abstractions, layers, adapters, factories, ports, design-system structure, or architectural patterns just because they are considered good practice.

Good:
- Keep a pure validation function when a full service would add no value.
- Add a port when provider replacement or test isolation is a real concern.
- Extract a component when multiple UI states or reuse justify it.
- Use native HTML elements instead of custom ARIA widgets.
- Follow the existing feature-folder structure instead of forcing Atomic Design.
- Keep direct simple code when there is no volatility, duplication, or boundary risk.

Bad:
- Add an interface for every class.
- Add a repository around simple existing queries without a boundary need.
- Add strategy pattern for one hardcoded behavior.
- Split every UI element into atoms and molecules.
- Add Clean Architecture layers to a small script or isolated utility.
- Introduce a pattern to look “enterprise-ready.”

## Follow the existing architecture first

Use SOLID, design patterns, Ports and Adapters, Clean Architecture, Component-Driven Development, semantic HTML, accessibility, or Atomic Design only when they improve the current task.

Do not introduce a new architecture style just because this skill mentions it.

Good:
- Follow the existing feature-folder convention for frontend code.
- Use the existing service and repository boundary for backend code.
- Add a port for email delivery because the task touches a volatile provider.
- Add component states using the project’s existing story or test pattern.
- Follow the project’s existing accessibility helpers and form patterns.

Bad:
- Restructure the whole app into Clean Architecture.
- Add Atomic Design directories to a project with a clear feature-based UI structure.
- Add interfaces for every class.
- Add design patterns before there is real variation.
- Replace native controls with custom widgets without a need.

## SOLID principles

Apply SOLID as design pressure, not ceremony.

Good:
- Keep validation rules in a validator or domain service, not scattered across UI and API.
- Keep project invitation policy separate from email delivery.
- Depend on a notification interface instead of a provider SDK.
- Add a new strategy only when behavior genuinely varies.
- Keep a component focused on rendering and interaction instead of owning unrelated business rules.

Bad:
- Add interfaces for every class.
- Create factories before there are variants.
- Mix permission rules, persistence, and HTTP formatting in one controller.
- Put business rules inside UI components.
- Split every function into a separate file.

## Ports and Adapters

Use Ports and Adapters when external systems or volatile infrastructure are involved.

Good:
- Domain service depends on `NotificationPort`.
- Email provider SDK lives in `SendGridNotificationAdapter`.
- Tests use an in-memory notification adapter.
- Repository interface hides database-specific queries from application logic.
- Analytics provider calls live behind an analytics adapter.

Bad:
- Domain logic imports the email provider SDK.
- UI component writes directly to the database.
- Tests require real external email delivery.
- Business rules depend on HTTP request objects.
- Provider-specific errors leak into domain rules.
- Add a port for a stable local helper with no external dependency.

## Clean Architecture boundaries

Keep dependency direction pointing inward.

Good:
- UI calls application use cases.
- API handlers translate HTTP input into application commands.
- Application services coordinate domain rules and ports.
- Infrastructure implements repositories, clients, queues, and provider adapters.
- Domain logic has no framework, database, UI, or provider dependency.

Bad:
- Domain imports React, Vue, Angular, Express, Fastify, Django, Rails, Prisma, or provider SDKs.
- Repository decides business permissions.
- API handler contains core domain rules.
- UI duplicates backend permission logic as the source of truth.
- Infrastructure types leak into domain APIs.
- Add layers that only pass data through without protecting a real boundary.

## Component-Driven Development

Use CDD for frontend implementation when the task changes UI behavior.

Build components in isolation first when practical, then compose them into screens.

Good:
- Define `ProjectForm` states: empty, invalid, submitting, success, server error, and permission denied.
- Verify component behavior with fixtures before wiring the real API.
- Compose field, form, panel, and page only after each state is clear.
- Keep component API small: inputs, outputs, events, accessible names, and labels.

Bad:
- Build the whole page before designing component states.
- Mix fetching, permission rules, formatting, validation, and rendering in one component.
- Add E2E tests for every component state.
- Create generic UI primitives before one real component needs them.

## Semantic HTML and accessibility

Use semantic HTML before ARIA.
Use native controls before custom controls.
Use ARIA only when native semantics are not enough.

Good:
- Use `<button>` for actions.
- Use `<a href="...">` for navigation.
- Use `<label>` for form controls.
- Use `<fieldset>` and `<legend>` for grouped form controls.
- Use headings in a logical order.
- Use lists for lists, tables for tabular data, and forms for form submission.
- Use landmarks such as `main`, `nav`, `header`, `footer`, and `aside` when they match the layout.
- Use `aria-describedby` or an equivalent project pattern to connect errors and help text to inputs.
- Use live regions only for dynamic messages that need announcement.

Bad:
- Use `<div onClick>` as a button.
- Use `<span>` as a link.
- Use placeholders as the only label.
- Add `role="button"` to a `div` when `<button>` works.
- Add ARIA that conflicts with native semantics.
- Use tables for layout.
- Hide focus outlines without an accessible replacement.

## Keyboard and focus behavior

Interactive UI must work with keyboard and predictable focus.

Good:
- Tab order follows the visual and logical flow.
- Focus remains visible.
- Dialogs move focus inside when opened and restore focus when closed.
- Escape closes dismissible dialogs when that matches project behavior.
- Error submission moves focus to the first invalid field when that is the project convention.
- Disabled controls expose clear state and do not trap focus.

Bad:
- A mouse-only menu.
- A modal that leaves focus behind the overlay.
- A custom dropdown without keyboard support.
- A hidden focus outline.
- A disabled button with no explanation when the user can fix the issue.

## Forms and validation accessibility

Forms must be understandable and recoverable.

Good:
- Every input has an accessible name.
- Required fields are communicated consistently.
- Errors appear next to the related field.
- Error text is connected to the related field.
- Server errors are shown in a visible and announced location.
- Submission state prevents duplicates without trapping the user.

Bad:
- Error summary with no field-level errors.
- Field-level errors not connected to inputs.
- Validation only through color.
- Placeholder-only labels.
- Duplicate submit allowed during pending request.

## Atomic Design

Use Atomic Design as a vocabulary for UI composition when it helps.
Do not force it onto projects that already use another coherent structure.

Good:
- Atom: button, input, label, icon, helper text.
- Molecule: validated field, search box, project status chip.
- Organism: project form, invitation panel, project list.
- Template: dashboard layout without final data.
- Page: dashboard with data, permissions, routing, and user flows.

Good:
- Reuse a validated field molecule across create and edit forms.
- Keep project list organism independent from route details.
- Keep page-level data loading out of simple atoms.
- Name components by domain meaning when domain meaning is clearer than Atomic Design labels.

Bad:
- Create atom/molecule/organism folders for a tiny one-off UI.
- Split every label and wrapper into separate files.
- Put business rules in atoms.
- Rename the project’s existing component structure without a task requirement.

## Frontend boundaries

Keep frontend concerns separated by responsibility.

Good:
- Presentational components render state and emit events.
- Container or page components coordinate data loading and routing when that is the project convention.
- Shared validators are reused by UI and API when the project supports shared code.
- Accessibility behavior is part of component behavior, not a final polish step.
- Client-side permission checks improve UX but backend remains authoritative.

Bad:
- UI is the only place enforcing authorization.
- One page component owns API calls, permissions, validation, formatting, state machine, and rendering.
- Validation messages differ between frontend and backend without reason.
- Accessibility is deferred until after implementation.

## Backend boundaries

Keep backend concerns separated by responsibility.

Good:
- API handler parses request and formats response.
- Application service coordinates use case behavior.
- Domain model or policy enforces business rules.
- Repository or adapter handles persistence.
- Provider adapter handles external communication.

Bad:
- Controller sends email, validates fields, checks permissions, writes database rows, and formats responses.
- Repository decides whether a user can perform a domain action.
- External provider errors are returned directly to clients.
- Database transactions are hidden in unrelated helpers.

## Cohesion and responsibility

Each module should have one clear reason to change.

Good:
- `ProjectNameValidator` changes when name rules change.
- `CreateProjectService` changes when project creation behavior changes.
- `ProjectRepository` changes when persistence changes.
- `ProjectForm` changes when form presentation or interaction changes.
- `InvitationPanel` changes when invitation UI states change.

Bad:
- `projectUtils` contains validation, API calls, formatting, rendering, and permissions.
- `ProjectController` sends email, validates fields, writes database rows, and formats UI messages.
- One component handles routing, fetching, validation, authorization, analytics, and rendering.
- One service handles unrelated project, user, billing, and notification behavior.

## Coupling

Prefer stable contracts over volatile details.

Good:
- Use application-level commands like `CreateProjectCommand`.
- Keep API response shape stable with `{ code, message, field }`.
- Hide provider-specific errors behind application errors.
- Keep telemetry helper usage consistent with existing patterns.
- Pass component data through explicit props or inputs instead of hidden globals.

Bad:
- Pass raw HTTP request objects through domain logic.
- Leak database row shape into UI components.
- Expose provider-specific error names to users.
- Couple unrelated modules through global mutable state.
- Let UI components import persistence clients.

## Design patterns

Use design patterns only when they reduce current complexity.

Good:
- Use Strategy when multiple invitation expiration policies are real.
- Use Adapter for email, payment, storage, analytics, or external APIs.
- Use Repository when persistence details should not leak into application logic.
- Use Factory when object creation has real branching rules.
- Use Presenter/ViewModel when UI formatting is complex and shared.

Bad:
- Add Strategy for one hardcoded behavior.
- Add Repository when the project already uses direct simple queries consistently.
- Add Factory for a single constructor call.
- Add AbstractFactory because it might be useful later.
- Add global state management for one local form.

## Naming

Use names that reveal intent and domain meaning.

Good:
- `CreateProjectService`
- `ProjectInvitation`
- `ownerId`
- `rejectDuplicateInvitation`
- `canUpdateProjectSettings`
- `ProjectForm`
- `InvitationStatusBadge`

Bad:
- `Manager`
- `Handler2`
- `processData`
- `doStuff`
- `flag`
- `CommonComponent`
- `Utils`

## Refactoring

Refactor only when it supports the task or removes local friction.

Good:
- Extract duplicate validation after adding the second real use.
- Rename a misleading method before adding behavior to it.
- Split a large function when the new branch would make it harder to test.
- Move provider code behind an adapter before adding the second provider-specific call.
- Extract a component when the screen has multiple states or reuse emerges.

Bad:
- Refactor the whole module before fixing a small bug.
- Split code into many files because small files look cleaner.
- Change architecture style mid-task without an ADR.
- Rename unrelated files.
- Create a design system before there is repeated UI behavior.

## Avoid overengineering

Do the simplest thing that satisfies current requirements and preserves likely change points.

Good:
- Add a small port for email delivery because the provider is volatile.
- Keep project creation synchronous until a real async requirement exists.
- Add one validation function instead of a validation framework.
- Use a local component state machine before adding global state.
- Keep code inline when extraction would reduce readability.

Bad:
- Build a workflow engine for one form.
- Add plugin architecture for one integration.
- Introduce event sourcing for simple CRUD without an ADR.
- Add caching before measuring a performance problem.
- Add global state management for one modal.
- Add patterns only because the codebase “should be more clean.”

## Avoid workarounds

Fix the root cause when practical.

Good:
- Fix the permission check in the service.
- Normalize API validation errors at the boundary.
- Escape project names at render time.
- Add a regression test for the bug.
- Fix focus management instead of hiding the failing interaction.

Bad:
- Hide the settings button but leave the API unprotected.
- Retry forever instead of handling the failure.
- Ignore type errors with unsafe casts or dynamic escape hatches.
- Disable a failing test without replacing coverage.
- Add CSS to hide broken content instead of fixing state logic.