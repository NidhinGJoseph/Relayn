# Engineering Constitution

This repository is a production SaaS platform, not a prototype.

## Core principles

1. Prefer simple, explicit, maintainable code over clever abstractions.
2. Do not implement functionality that was not requested.
3. Do not create speculative abstractions for hypothetical future features.
4. Do not duplicate business logic across views, serializers, models, tasks, or services.
5. Keep domain logic out of controllers/views whenever practical.
6. Keep external-provider-specific logic behind adapters.
7. Do not couple the core communication domain to WhatsApp, Meta, or any single provider.
8. All tenant-owned data must be scoped by organization.
9. Never trust organization_id supplied by a client without verifying membership and authorization.
10. Database constraints must protect important invariants where appropriate.
11. Use transactions for multi-step operations that must succeed or fail atomically.
12. Use explicit names. Avoid vague names such as helper, utils2, manager_new, data_handler, temp_service.
13. Keep functions/classes focused. Split code when responsibilities materially differ, not merely to reduce line count.
14. Avoid circular imports and hidden side effects.
15. Do not silently catch exceptions.
16. Never use `except Exception: pass`.
17. Never convert genuine failures into successful responses.
18. Never fabricate placeholder data when real data is unavailable.
19. Never add production fallback behavior merely to make a failing path appear to work.
20. Never silently switch to SQLite, mock providers, dummy credentials, fake responses, cached fake values, or alternate providers when configuration is missing.
21. Missing required configuration must fail clearly with an actionable error.
22. Provider/API failures must remain observable and debuggable.
23. Log useful context but never credentials, access tokens, secrets, or sensitive message content unnecessarily.
24. Do not expose internal exceptions, credentials, provider payloads, or stack traces to API clients.
25. Configuration belongs in environment/settings, not scattered constants.
26. Do not commit secrets.
27. Do not modify unrelated code while implementing a task.
28. Before creating a new abstraction, search the repository for an existing equivalent.
29. Follow existing repository conventions unless they violate this constitution.
30. Every migration must be reviewed for correctness and reversibility before proceeding.

## Testing philosophy

Tests are required for important domain behavior, permissions, tenant isolation, parsing, provider adapters, and state transitions.

Tests must expose bugs, not hide them.

DO NOT:
- modify production behavior just to satisfy a test;
- add fallback branches only used by tests;
- catch exceptions in tests unless the exception itself is the behavior being tested;
- mock the function under test;
- replace meaningful integration boundaries with unrealistic mocks;
- accept multiple unrelated outputs merely to make a flaky test pass;
- weaken assertions to get green tests;
- automatically retry broken behavior in tests;
- create alternate test-only business logic.

Mock only true external boundaries such as Meta HTTP calls, time, or external storage when required.

When a test fails:
1. determine the actual cause;
2. explain the cause;
3. fix production code if production code is wrong;
4. fix the test only if the test expectation is wrong.

## Error handling

Expected domain failures should use explicit domain exceptions.

Unexpected failures should propagate to the central error handling/logging layer.

External API errors must preserve enough structured context for diagnosis:
- provider;
- operation;
- HTTP status where available;
- provider request/correlation ID where available;
- sanitized provider error code.

Do not expose secrets or raw sensitive payloads.

## API design

Use versioned APIs:

/api/v1/...

Use consistent:
- pagination;
- validation;
- error responses;
- authorization;
- filtering conventions.

Serializers validate transport/input concerns.
Services implement use cases/business operations.
Models represent persistence and core invariants.
Provider adapters communicate with external systems.

## Multi-tenancy

Organization is the tenant boundary.

Every tenant-owned query must be scoped to the authenticated user's authorized organization.

Object IDs alone are never sufficient authorization.

Cross-tenant access is a critical security bug.

## Definition of done

Before declaring a task complete:
- inspect the diff;
- run relevant tests;
- run lint/static checks configured by the repository;
- check migrations;
- check tenant isolation;
- check authorization;
- check error paths;
- remove dead/debug code;
- ensure no secret is committed;
- list changed files;
- explain architectural decisions;
- report remaining limitations honestly.

Never claim something works if it was not actually verified.