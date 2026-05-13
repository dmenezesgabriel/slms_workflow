---
name: software-feature-planning
description: Plan new features with clear responsibilities, cohesive boundaries, correct dependency direction, protected invariants, testable seams, and simple extension points.
---

## Purpose

Plan a new feature before implementation by defining behavior, responsibilities, boundaries, data flow, dependency direction, invariants, seams, tests, and rollout strategy.

Use this skill when adding a feature to an existing codebase or designing a new feature from scratch.

This skill is language-agnostic.

## Planning Principles

### Behavior and Scope

Start from observable behavior, user intent, business rules, acceptance criteria, and explicit non-goals.

Define what must change in the system without assuming implementation structure too early.

Key terms: user story, acceptance criteria, use case, scenario, happy path, edge case, non-goal, observable behavior.

### Responsibility and Cohesion

Assign each responsibility to the smallest cohesive owner: function, class, module, component, service, package, or use case.

Keep behavior that changes together together.

Avoid god objects, generic utility modules, scattered feature logic, mixed abstraction levels, and unnecessary tiny files.

Key terms: Single Responsibility Principle, high cohesion, locality of behavior, locality of change, responsibility boundary, divergent change.

### Coupling and Dependency Direction

Plan dependencies so stable policy does not depend on volatile details.

Core feature logic must not depend directly on frameworks, databases, SDKs, APIs, queues, file systems, UI, transport, global state, or environment variables.

Key terms: loose coupling, Dependency Rule, Dependency Inversion Principle, policy/detail separation, infrastructure leakage, change ripple.

### Encapsulation and Invariants

Identify feature invariants before designing APIs or data models.

Protect rules inside the owning domain object, value object, aggregate, domain service, application service, or state machine.

Do not rely on scattered callers, controllers, UI components, database constraints, or external services to enforce core rules.

Key terms: encapsulation, information hiding, invariant protection, Tell Don’t Ask, value object, domain service, aggregate, state transition.

### Boundaries and Contexts

Place the feature inside the correct business capability, module, package, service, or bounded context.

Define published interfaces at boundaries and avoid leaking internal models across contexts.

Key terms: Bounded Context, Ubiquitous Language, context boundary, published interface, contract boundary, Anti-Corruption Layer, shared kernel.

### Ports, Adapters, and Test Seams

Plan seams only for external, slow, volatile, nondeterministic, or replaceable dependencies.

Delivery adapters call application use cases. Use cases may depend on ports. Infrastructure adapters implement ports. Domain logic stays technology-agnostic.

Key terms: Ports and Adapters, Hexagonal Architecture, primary adapter, secondary adapter, application port, infrastructure adapter, test seam, pure function, imperative shell, contract test.

### Abstraction and Extension Points

Introduce abstractions only when real variation exists or change pressure is likely.

Do not create interfaces, strategies, registries, factories, or plugins only to make the design look flexible.

Prefer direct code until duplication, volatility, testability, boundary pressure, or recurring variation justifies indirection.

Key terms: Open/Closed Principle, Protected Variation, strategy pattern, role interface, capability interface, leaky abstraction, indirection cost, speculative generality.

### Simplicity and Locality

Keep the planned structure shallow, cohesive, and locally understandable.

Do not fragment the feature into many tiny modules, classes, interfaces, layers, or files unless the split creates a concrete design benefit.

A split is justified only when it improves cohesion, encapsulation, testability, dependency direction, boundary clarity, replaceability, volatility isolation, invariant protection, or locality of change.

Key terms: Simple Design, essential complexity, accidental complexity, locality of behavior, locality of change, premature abstraction, pattern-driven design.

## Planning Rules

Be concrete, falsifiable, and implementation-oriented.

Do not say:

- Design clean architecture
- Use SOLID
- Add a service layer
- Make it modular
- Add an abstraction
- Make it reusable
- Add tests later

Instead state:

- Which behavior must be implemented
- Which responsibility belongs to which owner
- Which boundary contains the feature
- Which dependency direction must be preserved
- Which invariant must be protected
- Which side effect requires a port or adapter
- Which data crosses each boundary
- Which variation axis is real
- Which abstraction would be premature
- Which tests protect the feature
- Which smallest implementation slice comes first

Do not introduce a layer, interface, port, adapter, strategy, registry, or event unless there is a real design force: external dependency, real variation, poor testability, boundary protection, replaceability, volatility isolation, duplicated policy, or change safety.

## Output Format

For each feature plan, use:

### Feature Plan: precise feature name

Goal:
User-visible behavior or business capability being added.

Non-goals:
What is intentionally out of scope.

Acceptance criteria:
Concrete scenarios, rules, edge cases, and observable outcomes.

Primary flow:
Step-by-step behavior from input to result.

Responsibilities:
Which function, class, module, component, service, package, or use case owns each responsibility.

Boundary:
Feature boundary, context boundary, module boundary, API boundary, or UI boundary.

Dependency direction:
Which units may depend on which other units, and which dependencies are forbidden.

Invariants:
Rules that must always hold and where they are protected.

Data flow:
Input, output, domain data, DTOs, events, commands, queries, and persistence shape.

Side effects:
Database, network, filesystem, queue, clock, randomness, browser API, SDK, or external service interactions.

Ports and adapters:
Only the justified ports, adapters, contracts, fakes, or stubs required for isolation or replaceability.

Extension points:
Only real variation axes and the simplest mechanism to support them.

Test strategy:
Unit, component, integration, contract, E2E, regression, mutation, performance, or accessibility tests required.

Implementation sequence:
Smallest safe vertical slices in order.

Risk:
Coupling risk, invariant risk, migration risk, concurrency risk, security risk, performance risk, test fragility, over-abstraction, or over-fragmentation.

Target shape:
Final intended module structure, responsibility split, dependency direction, boundary, interface, or flow.

## Planning Sequence

1. Define the feature goal and non-goals.
2. Write acceptance criteria and edge cases.
3. Identify the primary use case or user journey.
4. Locate the correct module, package, service, component, or bounded context.
5. Assign responsibilities to cohesive owners.
6. Identify invariants and their owning model or service.
7. Define input, output, data flow, and boundary contracts.
8. Separate pure decision logic from side effects.
9. Introduce ports only for external dependencies or real variation axes.
10. Place concrete infrastructure behind adapters.
11. Define tests before implementation.
12. Plan the first small vertical slice.
13. Add remaining states, edge cases, and integration paths incrementally.
14. Refactor names and boundaries while behavior stays protected.
15. Keep the structure shallow.

## Implementation Strategy

Prefer incremental vertical slices over broad foundational rewrites:

1. Add or update acceptance examples.
2. Add characterization tests if changing existing behavior.
3. Add one failing test for the first behavior.
4. Implement the smallest path through the feature.
5. Keep domain policy independent of delivery and infrastructure.
6. Protect invariants at the owning boundary.
7. Add adapters for external dependencies only when needed.
8. Add contract tests for adapters.
9. Add integration tests for real composition points.
10. Add E2E tests only for critical user journeys.
11. Add regression tests for discovered bugs.
12. Refactor toward the target shape after tests pass.

## Core Principle

Feature planning should produce the smallest safe design that can implement the required behavior while preserving cohesion, encapsulation, dependency direction, testability, and boundary integrity.

Introduce abstractions, layers, interfaces, ports, adapters, events, registries, and patterns only when they reduce coupling, protect invariants, isolate volatility, improve testability, clarify ownership, or enforce architectural boundaries.