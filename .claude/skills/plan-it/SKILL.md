---
name: plan-it
description: Use this skill when the user asks to plan, break down, scope, sequence, or prepare implementation work for a feature, refactor, bug fix, migration, or technical change. Produces prioritized self-contained task files with context, dependencies, requirements, acceptance criteria, test strategy, observability, ADR guidance, and issue markdown output.
---

Create an implementation plan with _one or more tasks_.

Each task must be short, concrete, testable, and self-contained.
Do not create artificial tiny tasks.
Do not create bureaucratic sections with duplicated content.

## Core workflow

1. Identify unresolved decisions, hidden assumptions, and missing constraints.
2. Clarify only what cannot be discovered from the codebase.
3. Prefer tracer-bullet vertical slices over horizontal layer work.
4. Keep irreversible architecture decisions open as long as practical.
5. Identify whether any task requires an ADR stub.
6. Create prioritized tasks with dependencies and enough context to execute.
7. Define requirements, acceptance criteria, observability, and a minimal meaningful test set.
8. Write one Markdown issue file per task in `issues/`.
9. Write ADR stubs in `docs/adrs/` only when architecture decisions are needed.

## Required references

Read these files when using this skill:

- `references/planning-rules.md` — use for clarification, tracer bullets, architecture-decision timing, task priority, dependencies, context, use cases, requirements, observability, acceptance criteria, and definition of done.
- `references/test-selection.md` — use before choosing unit, integration, smoke, E2E, regression, performance, security, usability, or observability tests.
- `references/output-files.md` — use before creating issue files in `issues/` or ADR files in `docs/adrs/`.
- `references/adr-rules.md` — use when the plan contains architectural decisions that may require an ADR.
- `assets/task-template.md` — use as the exact structure for each generated issue file.
- `assets/adr-template.md` — use as the exact structure for each generated ADR file.

## Issue output requirement

After all tasks are defined, create one Markdown file per task in `issues/`.

Before writing issue files, run:

```bash
bash scripts/ensure-issues-dir.sh issues
```

Then write task files using priority and dependency order:

```text
issues/001-create-project.md
issues/002-invite-project-member.md
issues/003-protect-project-settings.md
```

## ADR output requirement

During planning, identify whether any task needs an Architectural Decision Record.

Create an ADR stub when a task depends on a decision that is hard to reverse, cross-cutting, or affects architecture boundaries, data, infrastructure, security, scalability, protocols, vendors, or external dependencies.

Do not create ADRs for ordinary implementation details.

Before writing ADR files, run:

```bash
bash scripts/ensure-adrs-dir.sh docs/adrs
```

Then write ADR files using chronological numeric order:

```text
docs/adrs/001-use-notification-port.md
docs/adrs/002-store-project-events.md
docs/adrs/003-use-opentelemetry.md
```

## Final response

After creating the files, summarize:

- created issue files
- created ADR files, if any
- task order
- ADR dependencies, if any
- unresolved assumptions, if any
- tests intentionally marked not applicable