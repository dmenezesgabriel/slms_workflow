# Output Files

After all tasks are defined, write each task as a separate Markdown file inside an `issues/` directory.

If ADRs are needed, write each ADR as a separate Markdown file inside a `docs/adrs/` directory.

## Issue directory rule

Create the `issues/` directory if it does not exist.

Before writing issue files, run:

```bash
bash scripts/ensure-issues-dir.sh issues
```

## Issue file rules

- Use priority order for file numbering.
- Respect dependency order.
- A dependent task must not appear before the task it depends on.
- If two tasks have the same priority, order the task with fewer dependencies first.
- Use a short descriptive lowercase slug.
- Use kebab-case for slugs.
- Use `.md` extension.
- Keep one task per file.
- Preserve all task sections inside the file.
- Use `assets/task-template.md` as the required structure.

## Issue file naming format

```text
issues/001-short-descriptive-slug.md
```

Good:
- `issues/001-create-project.md`
- `issues/002-invite-project-member.md`
- `issues/003-protect-project-settings.md`
- `issues/004-add-project-observability.md`

Bad:
- `issues/create project.md`
- `issues/task1.md`
- `issues/high-priority-feature.md`
- `issues/001.md`
- `issues/ProjectCreation.md`

## Issue ordering rule

Sort tasks by:

1. priority
2. dependencies
3. lowest implementation risk
4. earliest tracer-bullet validation

Good:
- `001-create-project.md` before `002-invite-project-member.md`, because invitations require `projectId`.
- `002-invite-project-member.md` before `003-resend-invitation.md`, because resend requires an existing invitation.
- `003-protect-project-settings.md` before `004-add-settings-form.md`, because permissions define who can use the form.

Bad:
- Write UI polish before the core project creation flow exists.
- Write invitation tasks before the project identity exists.
- Write analytics-only tasks before the user behavior exists.

## ADR directory rule

Create the `docs/adrs/` directory if ADRs are needed and it does not exist.

Before writing ADR files, run:

```bash
bash scripts/ensure-adrs-dir.sh docs/adrs
```

## ADR file rules

- Use chronological numeric prefixes.
- Use short descriptive lowercase slugs.
- Use kebab-case for slugs.
- Use `.md` extension.
- Keep one architectural decision per file.
- Use `assets/adr-template.md` as the required structure.
- Link ADRs from task Dependencies when a task depends on that decision.

## ADR file naming format

```text
docs/adrs/001-short-decision-slug.md
```

Good:
- `docs/adrs/001-use-notification-port.md`
- `docs/adrs/002-store-project-events.md`
- `docs/adrs/003-use-opentelemetry.md`

Bad:
- `docs/adrs/architecture.md`
- `docs/adrs/decision1.md`
- `docs/adrs/final-choice.md`
- `docs/adrs/001.md`
- `docs/adrs/UseProvider.md`

## ADR ordering rule

Sort ADRs by when the decision is first needed.

Good:
- `001-use-notification-port.md` before `002-send-invitation-email.md`, because email delivery tasks depend on the port decision.
- `002-store-project-events.md` before tasks that write audit events.
- `003-use-opentelemetry.md` before tasks that standardize traces and metrics.

Bad:
- Create provider-specific ADRs before deciding the boundary.
- Create implementation detail ADRs before the architecture question exists.
- Create ADRs after tasks already depend on unrecorded architecture decisions.

## Scripts

Use the bundled scripts:

```bash
bash scripts/ensure-issues-dir.sh issues
bash scripts/ensure-adrs-dir.sh docs/adrs
```

Each script must create the directory and exit successfully if it already exists.

## Final response after file generation

Report:

- each issue file created
- each ADR file created
- final task order
- ADR dependencies
- skipped or not-applicable test categories
- unresolved assumptions, if any

Good:
- Created `issues/001-create-project.md`.
- Created `issues/002-invite-project-member.md`.
- Created `docs/adrs/001-use-notification-port.md`.
- `E2E-001` was marked not applicable for the validation-only task because no user journey changed.
- Assumption: invitations expire after 7 days.

Bad:
- Done.
- Created issues.
- Created ADRs.
- Everything is ready.