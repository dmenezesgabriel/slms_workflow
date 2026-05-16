---
name: implement-it
description: Use this skill when the user asks to implement, code, fix, refactor, or complete an existing issue, task, story, or plan in frontend, backend, full-stack, CLI, service, API, or library code. Applies TDD, Component-Driven Development, semantic HTML, accessibility, Atomic Design when relevant, SOLID, Ports and Adapters, Clean Architecture boundaries, meaningful tests, observability, ADR updates, and validation while avoiding overengineering and workarounds.
---

Implement one or more existing tasks, issues, stories, or plan items.

This skill is programming-language agnostic.
Use the existing project language, framework, architecture, commands, style, and conventions.

Implementation must satisfy the task requirements without introducing unnecessary complexity, broad rewrites, hidden workarounds, or unrelated changes.

Use design principles selectively.
Avoid overengineering and workarounds.
Do not apply every design principle by default.
Prefer the simplest implementation that satisfies the task, preserves existing architecture, and keeps likely change points safe.

Use SOLID, design patterns, Ports and Adapters, Clean Architecture, Component-Driven Development, semantic HTML, accessibility, and Atomic Design as decision tools, not mandatory ceremonies.

Apply a principle only when it reduces current risk, clarifies responsibility, protects a volatile boundary, improves testability, improves accessibility, or follows existing project architecture.

Do not introduce abstractions, layers, adapters, factories, ports, design-system structure, or architectural patterns just because they are considered good practice.

## Core workflow

1. Read the assigned issue, task, story, plan, or user request.
2. Inspect the codebase before asking questions when the answer can be discovered.
3. Identify relevant existing architecture, tests, conventions, components, services, boundaries, accessibility patterns, and ADRs.
4. Implement the smallest safe vertical slice that satisfies the task.
5. Use TDD for logic, APIs, services, domain rules, data flows, permissions, and regressions when practical.
6. Use Component-Driven Development for frontend UI work when practical.
7. Use semantic HTML and native controls before ARIA for frontend work.
8. Treat accessibility as part of component behavior, not final polish.
9. Use Atomic Design as a UI organization heuristic when it matches or improves the existing project structure.
10. Preserve architecture boundaries and dependency direction.
11. Add or update only meaningful tests.
12. Add or update logs, metrics, traces, and analytics only when required by the task or risk.
13. Update ADRs when implementation confirms, changes, or rejects architectural assumptions.
14. Validate with the relevant test, lint, typecheck, build, accessibility, and runtime checks.
15. Write a short implementation summary.

## Required references

Read these files when using this skill:

- `references/implementation-rules.md` — use for implementation workflow, codebase exploration, TDD, CDD, frontend/backend execution, accessibility execution, scope control, and validation.
- `references/design-rules.md` — use for SOLID, design patterns, Ports and Adapters, Clean Architecture, Component-Driven Development, semantic HTML, accessibility, Atomic Design, boundaries, naming, cohesion, coupling, and avoiding overengineering.
- `references/testing-rules.md` — use before adding or changing unit, component, integration, smoke, E2E, regression, performance, security, usability, accessibility, or observability tests.
- `references/adr-implementation-rules.md` — use when implementation touches ADR-backed decisions or discovers new architectural decisions.
- `references/output-rules.md` — use before writing implementation notes or summaries.
- `assets/implementation-checklist.md` — use as the implementation checklist.
- `assets/implementation-summary-template.md` — use as the final implementation summary format.

## Output requirement

When implementation changes are complete, create or update an implementation summary in `implementation/`.

Before writing implementation output, run:

```bash
bash scripts/ensure-implementation-dir.sh implementation
```

Use this naming format:

```text
implementation/001-create-project-summary.md
implementation/002-invite-project-member-summary.md
```

## Final response

After implementation, summarize:

- files changed
- behavior implemented
- tests added or updated
- validations run
- accessibility checks run, if relevant
- ADRs updated, if any
- intentional non-applicable test categories
- unresolved assumptions or follow-up work