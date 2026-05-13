---
name: software-design-audit
description: Analyze code for design issues that reduce understandability, maintainability, testability, extensibility, replaceability, or boundary integrity.
---

## Purpose

Audit code for concrete design issues in responsibility, cohesion, coupling, encapsulation, dependency direction, boundaries, extension points, testability, and simplicity.

This skill is language-agnostic.

## Review Principles

### Responsibility and Cohesion

Check whether each function, class, module, component, service, or package has one clear responsibility, one focused reason to change, and behavior that belongs together.

Flag god objects, generic utility modules, mixed abstraction levels, scattered feature logic, unrelated methods, domain policy inside controllers/UI, orchestration mixed with low-level mechanics, and over-fragmented structures.

Key terms: Single Responsibility Principle, high cohesion, low cohesion, divergent change, shotgun surgery, god object, feature envy, responsibility leakage, locality of behavior, locality of change.

### Coupling and Dependency Direction

Check whether units depend on stable policy instead of volatile details.

Core logic must not depend directly on frameworks, databases, SDKs, APIs, queues, file systems, UI, transport, global state, or shared mutable state.

Flag circular dependencies, concrete infrastructure dependencies, framework types in core code, use cases instantiating clients directly, control coupling, temporal coupling, and change ripple.

Key terms: loose coupling, tight coupling, afferent coupling, efferent coupling, Dependency Rule, Dependency Inversion Principle, policy/detail separation, infrastructure leakage, temporal coupling, control coupling.

### Encapsulation and Invariants

Check whether state, invariants, and implementation details are protected behind intentional APIs.

Flag public mutable state, callers enforcing internal rules, primitive obsession, data clumps, excessive getters/setters, persistence models used as domain models, internal representation leakage, and anemic domain models.

Key terms: encapsulation, information hiding, invariant protection, Tell Don’t Ask, Law of Demeter, value object, domain service, anemic domain model, primitive obsession.

### Boundaries and Contexts

Check whether modules, packages, services, and contexts match business capabilities and domain language.

Flag cross-context model sharing, ambiguous domain terms, generic DTOs reused across unrelated contexts, direct cross-context calls without explicit contracts, and internal details exposed across boundaries.

Key terms: Bounded Context, Ubiquitous Language, context boundary, published interface, contract boundary, Anti-Corruption Layer, shared kernel.

### Ports, Adapters, and Test Seams

Check whether core policy is separated from external mechanisms.

Delivery adapters should call application use cases. Use cases may depend on ports. Infrastructure adapters implement those ports. Domain logic stays technology-agnostic.

Flag business logic requiring a database, network, clock, filesystem, framework runtime, randomness, environment variables, or real external services to test.

Key terms: Ports and Adapters, Hexagonal Architecture, primary adapter, secondary adapter, application port, infrastructure adapter, test seam, pure function, deterministic core, imperative shell, contract test, characterization test.

### Abstraction and Extension Points

Check whether abstractions are meaningful, narrow, behavior-based, and justified by real change pressure.

Flag premature abstraction, speculative generality, interface proliferation, leaky abstractions, unnecessary indirection, interfaces that mirror one implementation, and large conditional chains over provider, type, status, mode, feature flag, or strategy when they represent recurring variation.

Prefer direct code until duplication, volatility, testability, boundary pressure, or real variation justifies abstraction.

Key terms: Open/Closed Principle, Protected Variation, strategy pattern, polymorphism, role interface, capability interface, leaky abstraction, indirection cost, accidental complexity.

### Simplicity and Locality

Do not fragment code into many tiny modules, classes, interfaces, layers, or files unless the split creates a clear design benefit.

A split is justified only when it improves cohesion, encapsulation, testability, dependency direction, boundary clarity, replaceability, volatility isolation, invariant protection, or locality of change.

Prefer shallow, cohesive, locally understandable structures.

Key terms: Simple Design, essential complexity, accidental complexity, locality of behavior, locality of change, indirection cost, premature abstraction, speculative generality, pattern-driven design.

## Review Rules

Be concrete, falsifiable, and code-specific.

Do not say:

- Improve architecture
- Use SOLID
- Make it cleaner
- Refactor this
- Separate concerns

Instead state:

- Which responsibility is misplaced
- Which boundary is missing
- Which dependency direction is wrong
- Which invariant is unprotected
- Which abstraction is premature or leaky
- Which variation axis is recurring
- Which code is over-fragmented
- Which behavior-preserving refactor is smallest

Do not recommend extraction only because something is long.

Recommend extraction only when there is a real design force: low cohesion, multiple reasons to change, mixed abstraction levels, duplicated policy, hidden side effects, poor testability, leaked infrastructure, unprotected invariants, unclear ownership, recurring variation, or strong coupling.

## Output Format

For each finding, use:

### Finding: precise design issue

Priority: High | Medium | Low

Category: Responsibility | Cohesion | Coupling | Encapsulation | Boundary | Dependency Direction | Ports and Adapters | Testability | Extension Point | Simplicity

Issue:
Exact structural problem.

Evidence:
Specific function, class, module, dependency, control flow, or data flow.

Design impact:
Why it hurts maintainability, testability, extensibility, replaceability, boundary integrity, or change safety.

Recommendation:
Smallest behavior-preserving refactor.

Target shape:
Intended responsibility split, dependency direction, boundary, interface, module structure, or flow.

## Refactoring Strategy

Prefer incremental refactoring over rewrites:

1. Add characterization tests around current behavior.
2. Identify responsibilities that change for different reasons.
3. Separate pure decision logic from side effects.
4. Move domain policy out of delivery/infrastructure code.
5. Protect invariants inside domain objects or domain services.
6. Introduce ports only for external dependencies or real variation axes.
7. Move concrete infrastructure behind adapters.
8. Reverse dependency direction so core policy does not depend on details.
9. Replace duplicated conditionals only when variation is real.
10. Rename concepts according to domain intent.
11. Keep the structure shallow.

## Core Principle

Favor cohesive, locally understandable modules over excessive fragmentation.

Introduce abstractions, layers, interfaces, ports, adapters, and patterns only when they reduce coupling, protect invariants, isolate volatility, improve testability, clarify ownership, or enforce architectural boundaries.
