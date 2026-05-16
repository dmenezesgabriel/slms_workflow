# ADR Rules

Use Architectural Decision Records only for meaningful architectural decisions.

Do not create ADRs for every task.

## When to create an ADR

Create an ADR stub during planning when a task depends on a decision that is:

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

Good:
- Choose how project audit events are stored.
- Hide email delivery behind a notification port.
- Use OpenTelemetry for traces, metrics, and log correlation.
- Store project permissions as role assignments instead of boolean flags.
- Use asynchronous invitation email delivery through a queue.

Bad:
- Rename a component.
- Move a helper function.
- Add a button label.
- Change CSS spacing.
- Add a unit test.

## Planning vs implementation

Planning phase:
- Identify that an ADR is needed.
- Create a lightweight ADR stub.
- Capture context, options, recommendation, and open questions.
- Link the ADR to affected task files.

Implementation phase:
- Validate the decision against real code constraints.
- Update the ADR status.
- Record final consequences.
- Link the final implementation PR, issue, or commit when available.

Good rule:
- Plan phase: identify ADR needed.
- Implementation phase: decide, validate, and complete ADR.

## ADR status

Use one of these statuses:

- `Proposed` — decision is suggested but not validated.
- `Accepted` — decision is chosen and implementation can depend on it.
- `Superseded` — decision was replaced by another ADR.
- `Rejected` — decision was considered but not chosen.

## ADR file rules

Write ADRs inside `docs/adrs/`.

Use chronological numeric prefixes and short lowercase kebab-case slugs.

Good:
- `docs/adrs/001-use-notification-port.md`
- `docs/adrs/002-store-project-events.md`
- `docs/adrs/003-use-opentelemetry.md`

Bad:
- `docs/adrs/adr.md`
- `docs/adrs/architecture decision.md`
- `docs/adrs/final-choice.md`
- `docs/adrs/001.md`

## ADR linking rule

When a task depends on an ADR, reference it in the task Dependencies section.

Good:
- Depends on ADR `docs/adrs/001-use-notification-port.md`.
- Depends on ADR `docs/adrs/002-store-project-events.md`.
- No ADR dependency; this task uses existing architecture.

Bad:
- Depends on architecture.
- Needs ADR.
- Check decision later.

## ADR quality rule

Each ADR must be short and decision-focused.

Good:
- State the decision in one or two sentences.
- List two or three realistic options.
- Mark the recommended option with `(recommended)`.
- Explain positive and negative consequences.
- List validation steps for implementation.

Bad:
- Write a long essay.
- Document every implementation step.
- Hide the decision inside background text.
- Skip consequences.

## ADR and task relationship

Tasks should not silently depend on unrecorded architecture decisions.

Good:
- The task references the ADR in Dependencies.
- The ADR references the related task file.
- The task Definition of Ready says the ADR stub exists.
- The task Definition of Done says the ADR is accepted or explicitly left proposed with open questions.

Bad:
- The task chooses a provider without an ADR.
- The task adds an architectural boundary without documenting the decision.
- The ADR exists but no task references it.