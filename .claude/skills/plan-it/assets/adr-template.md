# ADR <number>: <short decision title>

## Status

<Proposed | Accepted | Superseded | Rejected>

## Date

<YYYY-MM-DD>

## Related Tasks

- `issues/001-example-task.md`

## Context

<Short explanation of the problem, constraints, and why this decision matters.>

Example:
- Project invitations must send email without coupling domain logic to a specific email provider.
- The system may later switch from SMTP to a transactional email provider.
- Invitation creation must be testable without sending real emails.

## Decision

<State the chosen decision clearly.>

Example:
- Use a `NotificationPort` interface for invitation emails.
- Keep provider-specific email code inside an infrastructure adapter.
- Domain and application services must depend on the port, not the provider SDK.

## Options Considered

1. <Option 1>. `(recommended)`
2. <Option 2>.
3. <Option 3>.

Example:
1. Use a notification port and provider adapter. `(recommended)`
2. Call the email provider SDK directly from the invitation service.
3. Send emails only from the UI after invitation creation.

## Consequences

Positive:
- <Positive consequence>
- <Positive consequence>

Negative:
- <Negative consequence>
- <Negative consequence>

Example:
Positive:
- Email provider can change without rewriting invitation logic.
- Tests can use an in-memory notification adapter.

Negative:
- Adds one extra interface and adapter.
- Requires clear ownership of notification error handling.

## Validation

<How the decision will be validated during implementation.>

Example:
- Integration tests verify invitation creation emits a notification request.
- Unit tests verify invitation logic without provider SDK imports.
- Observability tests verify email delivery failures are logged without exposing email body.

## Open Questions

- <Question 1>
- <Question 2>

Example:
- Should failed email delivery retry synchronously or through a queue?
- Should invitation emails expire after 7 days or 14 days?