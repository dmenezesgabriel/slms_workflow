# Output Rules

After implementation, write a short implementation summary in `implementation/`.

## Directory rule

Before writing implementation output, run:

```bash
bash scripts/ensure-implementation-dir.sh implementation
```

## File rules

- Use the same numeric prefix as the related issue when possible.
- Use a short descriptive lowercase slug.
- Use kebab-case for slugs.
- Use `.md` extension.
- Keep one implementation summary per implemented issue or task.
- Use `assets/implementation-summary-template.md`.

## File naming format

```text
implementation/001-short-descriptive-slug-summary.md
```

Good:
- `implementation/001-create-project-summary.md`
- `implementation/002-invite-project-member-summary.md`
- `implementation/003-protect-project-settings-summary.md`

Bad:
- `implementation/done.md`
- `implementation/task1.md`
- `implementation/summary final.md`
- `implementation/001.md`

## Summary content

The summary must include:

- task implemented
- files changed
- behavior implemented
- design notes
- tests added or updated
- validations run
- ADRs updated
- observability added or changed
- skipped or not-applicable test categories
- unresolved assumptions or follow-up work

Good:
- `UT-001` added for project name length.
- `IT-001` added for `POST /projects` persistence.
- `ProjectForm` component states verified for invalid, submitting, and server-error states.
- ADR `docs/adrs/001-use-notification-port.md` updated to `Accepted`.
- `E2E-001` not applicable because this task changed only a pure validator.

Bad:
- Done.
- Tests passed.
- Changed backend.
- Changed frontend.
- No issues.
