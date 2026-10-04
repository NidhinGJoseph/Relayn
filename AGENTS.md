# Repository engineering instructions

These instructions apply to all future Codex work in this repository. Read
ARCHITECTURE.md before implementation and keep changes within the requested stage.

## Project direction and current scope

This is a production, multi-tenant customer communication and business-action
platform. Initial capabilities include official Meta API WhatsApp communication,
a shared team inbox, contacts, conversations, lead management, workflows,
Meta attribution, and analytics. Future stages may add Instagram, Messenger,
other channels, public APIs, external systems, and vertical products such as
Rental OS. Implement only capabilities authorized by the current task.

Use a modular monolith, REST APIs, organization-based tenancy, explicit domain
boundaries, provider adapters, and internal events where useful. Do not introduce
premature microservices. Intended backend: Python, Django, Django REST Framework,
PostgreSQL, Redis, and Celery. Intended frontend: React, TypeScript, Vite, and
Tailwind CSS.

The repository currently contains instructions only. Stage 0 application
scaffolding has NOT been completed. Do not create backend/ or frontend/, install
dependencies, initialize frameworks, create models or Docker infrastructure, or
implement authentication, WhatsApp, billing, or AI until a later task authorizes
that work. Conceptual domains are not instructions to scaffold every module.

## Engineering rules

1. This is production software, not a prototype.
2. Prefer explicit, simple, maintainable implementations.
3. Do not generate speculative features.
4. Do not duplicate business logic.
5. Keep domain logic out of controllers/views where practical.
6. External providers must be isolated behind adapters.
7. Core communication models must not depend on WhatsApp or Meta.
8. Organization is the tenant boundary.
9. Every tenant-owned query must enforce organization isolation.
10. Never trust organization IDs supplied by clients without authorization.
11. Use database constraints for important invariants.
12. Use transactions for operations requiring atomicity.
13. Do not silently catch exceptions.
14. Never use `except Exception: pass`.
15. Never return success when an operation actually failed.
16. Never fabricate placeholder/fallback data when real data is unavailable.
17. Never silently fall back to SQLite.
18. Never silently fall back to mock providers.
19. Never silently fall back to fake API responses.
20. Never add test-only production behavior.
21. Missing required configuration must fail clearly.
22. Provider/API failures must remain observable and diagnosable.
23. Never log secrets, access tokens, or credentials.
24. Do not expose internal stack traces/provider secrets to API clients.
25. Configuration must come from appropriate settings/environment configuration.
26. Never commit secrets.
27. Do not modify unrelated code while completing a task.
28. Search for an existing abstraction before creating another.
29. Migrations must be reviewed before execution.
30. Tests must expose bugs rather than hide them.
31. Do not weaken tests simply to make them pass.
32. Mock only genuine external boundaries when necessary.
33. Do not mock the business logic being tested.
34. Failed tests must be investigated to determine root cause.
35. Never claim something was verified unless it was actually run.
36. Keep modules cohesive and avoid giant service/controller files.
37. Avoid circular imports and hidden side effects.
38. Use versioned APIs such as `/api/v1/`.
39. Maintain consistent API error/validation/pagination conventions.
40. Security and tenant isolation take priority over convenience.

## Definition of done

Every future implementation task must end with the following checklist:

- Inspect the git diff.
- Run relevant tests.
- Run configured lint/static checks.
- Run Django system checks where applicable.
- Check migrations where applicable; review them before execution.
- Review authorization.
- Review tenant isolation.
- Review error paths.
- Remove debug/dead code.
- Verify no secrets were introduced.
- List changed files.
- Report unresolved issues honestly.

Report checks actually run and their outcomes. If a check is unavailable or not
applicable, state why; never describe an unrun check as passing.
