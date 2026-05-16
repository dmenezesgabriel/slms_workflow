# Implementation Summary: <task name>

## Related Task

- `<issues/001-example-task.md>`

## Files Changed

- `<path/to/file>` — <short reason>
- `<path/to/test>` — <short reason>

## Behavior Implemented

- <Concrete behavior implemented>
- <Concrete validation, permission, or error behavior implemented>
- <Concrete user-visible or system-visible outcome>

Example:
- Signed-in users can create projects from the dashboard.
- Project names longer than 80 characters are rejected.
- Duplicate invitations show “Member already invited.”

## Design Notes

- <Boundary, pattern, or design decision applied>
- <TDD, CDD, semantic HTML, accessibility, or Atomic Design approach used when relevant>
- <Reason for avoiding broader changes>
- <Existing convention followed>

Example:
- Project creation is implemented through the existing project service.
- `ProjectForm` was implemented as an isolated component with invalid, submitting, and server-error states.
- The form uses native labels, buttons, and field-level error associations.
- Email delivery remains behind `NotificationPort`.
- Domain logic does not import the email provider SDK.
- Atomic Design folders were not introduced because the project already uses feature-based UI organization.

## Tests Added or Updated

- `<test path>` — <what it verifies>
- `<test path>` — <what it verifies>

Example:
- `tests/unit/project-name.test.ts` — verifies project names accept 1–80 characters.
- `tests/integration/create-project.test.ts` — verifies `POST /projects` persists project data.
- `src/components/project-form.test.tsx` — verifies invalid, submitting, and server-error form states.
- `src/components/project-form.a11y.test.tsx` — verifies labels and field errors are accessible.

## Test Categories Not Applicable

- `<category>`: Not applicable — <specific reason>.

Example:
- `E2E`: Not applicable — this task changed only a pure validation helper and no complete user journey.
- `Performance`: Not applicable — this task does not affect runtime behavior.
- `Component`: Not applicable — this task changes only backend authorization logic.
- `Accessibility`: Not applicable — this task does not change user-facing UI, markup, keyboard behavior, or error states.

## Validation Run

```text
<command> — <result>
<command> — <result>
```

Example:
```text
npm test -- project-name — passed
npm run typecheck — passed
npm run test:a11y -- project-form — passed
```

## Accessibility Notes

- <Semantic HTML, keyboard behavior, focus behavior, labels, roles, or error announcement added>
- <Not applicable reason>

Example:
- `ProjectForm` uses native labels and submit button.
- Name field error is connected to the input.
- Submit button remains keyboard reachable and prevents duplicate submissions.
- Not applicable — this task does not change frontend UI.

## Observability Changes

- <Log, metric, trace, analytics, or sensitive-data exclusion added>
- <Not applicable reason>

Example:
- Added `project.created` metric with success and failure tags.
- Logs include `projectId`, `ownerId`, request ID, and result.
- Project descriptions and tokens are excluded from logs.

## ADR Updates

- `<docs/adrs/001-example.md>` — <status or update>
- Not applicable — <specific reason>

Example:
- `docs/adrs/001-use-notification-port.md` — updated from `Proposed` to `Accepted`.
- Not applicable — this task does not touch architectural decisions.

## Unresolved Assumptions or Follow-Up

- <Assumption or follow-up>
- None.