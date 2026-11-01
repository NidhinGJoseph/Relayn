# Stage 2 implementation report

Stage 2 implements organization entitlements only. The schema and service interface
were presented in chat before implementation. Architecture places this interface
in billing, separate from core member permissions and any future pricing system.

## Behavior and boundaries

- All ten requested boolean keys and two numeric limit keys are defined in code.
- One assignment per organization/key, enforced by PostgreSQL uniqueness.
- Database checks enforce known keys, non-null boolean capability values, and
  nonnegative integer limits, with mutually exclusive value columns.
- has_capability denies missing and disabled assignments; require_capability raises
  CapabilityUnavailable with HTTP 403 semantics and code capability_unavailable.
- get_limit returns None for missing assignments, preserving explicit zero values.
- set_capability and set_limit provide validated, atomic internal assignments.
  Operators use Django shell; no public endpoint or writable admin was added.
- Every entitlement read/write scopes to the supplied persisted organization.
  Request callers must authorize it using core.tenancy first. These trusted internal
  functions do not independently authenticate an actor or grant staff/owner bypasses.
- No plans, prices, subscriptions, payments, product implementations, usage counters,
  or automatic grants. Later resource operations must enforce stored numeric limits.

## Migration review and execution

Reviewed billing.0001_initial source, live migrate --plan and sqlmigrate output
before execution. It depends on core.0001_initial and creates only the entitlement
table, UUID primary key, organization foreign key/index, unique organization/key
constraint, and typed-value check. No data migration or existing-table rewrite.
Structurally reversible by dropping the table; reversal loses its assignments.
Applied successfully to local relayn; test setup applied it to dedicated test_relayn.
No entitlement assignments were inserted into the development database.

## Validation actually run

- Full backend suite from backend: `.venv/Scripts/python manage.py test --keepdb
  --noinput`: 43 tests passed in 44.855 seconds on PostgreSQL.
- Eight new tests cover all boolean keys, disabled/revoked and missing capability
  failures, numeric and zero/missing limits, tenant isolation, invalid inputs,
  uniqueness, and database rejection of unknown keys and invalid value combinations.
- Django check: zero issues.
- makemigrations --check --dry-run: no changes detected.
- migrate --plan after execution: no planned operations.
- Ruff check backend scripts: passed.
- Ruff format --check backend scripts: all 35 files formatted.
- git diff --check: passed. Reviewed changed source and diff for scope, error paths,
  tenant filters, assignment exposure and secrets; no credentials added.

Initial migration generation encountered sandbox network denial. An elevated local
connection then timed out because Compose services were stopped; starting the
existing PostgreSQL/Redis containers restored connectivity. Generated migration
formatting/import lint issues were corrected. An initial test invocation from the
repository root discovered zero tests; this was not counted as validation. The
corrected invocation from backend discovered and passed all 43 tests.

Frontend and deployment checks were not run: this stage changes neither frontend
nor deployment settings. No unresolved implementation/test blocker remains.

## Changed files

- ARCHITECTURE.md
- README.md
- STAGE2_REPORT.md
- backend/config/settings.py
- backend/pyproject.toml
- backend/billing/__init__.py
- backend/billing/definitions.py
- backend/billing/models.py
- backend/billing/services.py
- backend/billing/migrations/__init__.py
- backend/billing/migrations/0001_initial.py
- backend/tests/test_entitlements.py

Stopped after Stage 2.
