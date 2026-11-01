# Stage 1 implementation report

## Disposition (2026-10-05)

Stage 1 is complete for the authorized local scope. The user approved the model,
policy, tenant strategy and migration graph; migrations are applied and all 35
backend tests pass on real PostgreSQL, including all 21 Stage 1 security tests.
No Stage 2 functionality was introduced. No application privileges, credentials,
PostgreSQL authentication rules, existing databases or volumes were reset.

## Models and authentication

- core.User: Django AbstractUser with UUID primary key, AUTH_USER_MODEL=core.User.
  Django remains the sole password/authentication implementation. Existing
  configuration had default auth.User and no DRF authenticators. Live PostgreSQL
  introspection returned no tables before generation, so no user-data conversion
  or auth migration history rewrite is needed.
- Organization: UUID primary key, name, created_at, updated_at.
- OrganizationMembership: UUID primary key, organization/user foreign keys,
  OWNER/ADMIN/MANAGER/AGENT TextChoices, created_at, updated_at.
- Unique constraint unique_org_user on organization/user; database check
  valid_membership_role; standard indexed foreign keys and UUID primary keys.
  The unique composite index plus user index support actor/tenant resolution.
- Membership user deletion uses PROTECT; deleting an account cannot silently
  cascade its ownership away. Organization deletion has no endpoint.
- BasicAuthentication checks Django credentials and active account state.
  Production HTTPS settings remain enforced. Public health authentication remains
  disabled explicitly. No account registration or alternate credential store.
- Exposed users include only UUID and username. Organizations and memberships
  expose their required identifiers, role, name and timestamps; no password,
  email, groups, staff flags, permissions or authentication state is serialized.

## Tenant context and policy

Organization context is explicit in versioned UUID paths. resolve_membership
filters by actor and organization before any organization detail read. Member
queries filter by the resolved organization. Inaccessible/absent objects use
404; invalid UUID paths use 404. No default/current tenant field or superuser
bypass exists. Scoped missing members use 404; validation uses DRF 400 errors,
authentication 401, insufficient capability/authority 403. Lists use configured
page-number pagination (50) and deterministic created_at/id ordering.

| Capability | OWNER | ADMIN | MANAGER | AGENT |
| --- | --- | --- | --- | --- |
| organization.view | yes | yes | yes | yes |
| members.view | yes | yes | yes | yes |
| members.create | yes | yes | no | no |
| members.change_role | yes | yes | no | no |
| members.remove | yes | yes | no | no |

Role authority is separate from capability: OWNER can manage any role; ADMIN
can manage and grant only MANAGER/AGENT. Both target and requested roles are
checked. An ADMIN cannot elevate itself or change an OWNER/ADMIN membership.

All supported writes use core.services transactions. Membership mutations first
resolve actor scope, lock only the organization row, then reload actor membership
after obtaining the lock. This serializes mutations for each organization and
prevents stale actor authority. Final OWNER demotion/removal is rejected; an
unchanged OWNER role is allowed. Ownership transfer adds/promotes another OWNER
before demoting/removing the former one. create_organization creates the initial
owner in the same transaction and rejects inactive/unsaved owners.

Cross-row ownership is deliberately enforced in services, not represented as a
fictional database constraint. Raw ORM/SQL mutations can bypass the policy; future
views, jobs and writable admin actions must use services. Account deactivation
is not membership removal and is outside these guarantees. An inactive owner
retains its membership; no account lifecycle API was introduced.

## Endpoints

All paths below are relative to /api/v1/ and require authentication:

- GET users/me/
- GET organizations/
- GET organizations/<organization UUID>/
- GET organizations/<organization UUID>/members/
- POST organizations/<organization UUID>/members/
- PATCH organizations/<organization UUID>/members/<membership UUID>/
- DELETE organizations/<organization UUID>/members/<membership UUID>/

Direct addition accepts an existing active account UUID and a valid role.
Operators already know the target ID; there is no global account directory.
Missing/inactive/duplicate targets share a generic 400 error. Successful addition
necessarily reveals eligibility to an authorized membership administrator. No
invitation, consent, email delivery, pending state, or fake invitation exists.
Account and organization provisioning is operator-facing Django/service use,
not a public registration/organization creation endpoint.

## Migration review and execution

Generated and inspected backend/core/migrations/0001_initial.py. Depends on
auth.0012_alter_user_first_name_max_length, transitively on contenttypes. Creates
Organization, the sole active User model, Django user/group/permission M2M tables,
and OrganizationMembership with both constraints. settings.AUTH_USER_MODEL is
used for the membership reference. Django's built-in auth.User is swapped out:
the generic migrate plan still describes auth's Create User operation, but it
will not create a competing auth_user table with this configuration.

No RunSQL, RunPython, database reset, legacy-user conversion or destructive
forward operation is in the core migration. Immediately before execution, live
application introspection again returned no tables. It is structurally reversible;
reversing initial table creation after data exists deletes that data and must
never be treated as a safe data rollback. Built-in migrations were reviewed via
the live plan. Executed the approved graph on relayn using
`backend/.venv/Scripts/python backend/manage.py migrate --noinput`. Django's
integration test setup applied the same graph to the separately provisioned
test_relayn database using the unchanged relayn application login.

Exact migrations executed on BOTH relayn and test_relayn (15 total per database):

- contenttypes.0001_initial, contenttypes.0002_remove_content_type_name
- auth.0001_initial through auth.0012_alter_user_first_name_max_length
- core.0001_initial

## Reproducible test database provisioning and safety

Added infrastructure/postgres/provision-test-database.sh and the host wrapper
scripts/provision_test_database.py. Run from the root:

```powershell
backend/.venv/Scripts/python scripts/provision_test_database.py
# If Docker is missing from PATH, supply --docker with its executable path.
```

The wrapper pipes normalized LF shell source into the existing Compose postgres
container. The shell reads the existing bootstrap secret internally and connects
as relayn_admin over the existing password-authenticated loopback connection.
Credentials never appear in printed commands/output. It creates only test_relayn
when absent, verifies its owner is relayn, rejects elevated application-role flags,
and revokes PUBLIC database access. Re-running it passed without recreating or
dropping the database. No application role grants or authentication changes.

Django TEST.NAME is explicitly test_relayn. Application DATABASE_URL may not point
to that name. config.test_runner.ProvisionedDatabaseRunner requires --keepdb,
PostgreSQL, separate names and prior database provisioning; the existing schema
is preserved. Tests run on test_relayn, not relayn. No SQLite or PostgreSQL mocks
are used in identity tests. Test fixtures are transactionally rolled back/flushed
inside the test database only; development records remain untouched.

Verified both database owners are relayn. Application role flags remain
NOSUPERUSER/NOCREATEDB/NOCREATEROLE/NOREPLICATION/NOBYPASSRLS with zero inherited
role memberships. Negative safety checks passed: test without --keepdb fails
before database mutation; an application URL pointing at test_relayn fails at
settings startup. These were expected guard failures, not suite failures.

## Schema verification

Read-only introspection assertions passed for both databases:

- AUTH_USER_MODEL is core.User; get_user_model resolves core_user.
- core_user, core_organization and core_organizationmembership exist.
- No competing auth_user table exists.
- All three exposed model primary keys use PostgreSQL UUID.
- unique_org_user uniquely constrains organization_id/user_id.
- valid_membership_role is a database CHECK constraint.
- Membership foreign keys reference core_organization.id and core_user.id.
- Both membership foreign-key columns have individual indexes; the composite
  unique index and primary-key indexes exist.
- django_migrations contains the exact 15-entry reviewed graph in each database.
- Development User/Organization/Membership tables remain empty after tests.

## Tests added

backend/tests/test_identity.py adds 21 PostgreSQL-backed tests with real Basic
credentials and real ORM tenant scoping. Coverage includes anonymous/bad-password/
inactive rejection, safe serialization, multiple organizations, scoped lists,
foreign/nonexistent tenant response equivalence, cross-tenant mutations, all four
role capabilities, ADMIN authority restrictions, escalation rejection, valid role
transitions/removal, final owner protection, invalid roles/UUIDs/missing objects,
duplicate/invalid-role database constraints, account-deletion protection,
superuser isolation, initial owner creation, direct-service denial, and concurrent
owner demotions using independent connections. All 21 passed in the full suite.

## Failures encountered and fixes

1. Initial test provisioner had Windows CRLF endings; the Linux shell rejected
   `set -eu` before any provisioning. Corrected the script to LF and added the
   wrapper's read_text normalization so future Windows checkouts work reliably.
2. The first suite attempt correctly stopped because test_relayn was not yet
   provisioned. After successful provisioning, Django reused the separate DB.
3. First executed suite: 35 tests, 42.104 seconds, one failure. The service raised
   a field error as a scalar ErrorDetail while the test and serializer contract
   required a list of messages. Changed service user_id and role field errors to
   lists for consistent transport validation. No security assertion was weakened,
   removed or changed; no authentication/authorization behavior was altered.
4. After the fix: 35 tests passed in 42.667 seconds. The requested final full-suite
   rerun also passed: 35 tests in 44.929 seconds, including concurrent demotion.

## Final validation actually performed

All commands use the real ignored local configuration; Python/Ruff refer to the
existing backend virtual environment. Django commands run from backend unless a
root-relative path is specified.

| Check | Actual result |
| --- | --- |
| python manage.py test --keepdb --noinput | PASS, 35/35 in 44.929s; 21 identity/security + 14 existing |
| python manage.py check | PASS, zero issues |
| python manage.py check --deploy | PASS, zero issues |
| python manage.py makemigrations --check --dry-run | PASS, no changes |
| python manage.py migrate --plan | PASS, no planned operations |
| ruff check backend scripts (root) | PASS |
| ruff format --check backend scripts (root) | PASS, 28 files formatted |
| python -m pip check | PASS, no broken requirements |
| Live application/database/Redis HTTP health | PASS, all 200 |
| docker compose ps | PASS, both containers healthy with unchanged loopback ports |
| PostgreSQL schema/privilege/data assertions | PASS in both databases |
| git diff --check | PASS |
| Exact generated-secret scan of tracked/non-ignored source | PASS |

Deployment checks override only DJANGO_ENV=production and DJANGO_DEBUG=false,
retaining the real local secret and URLs. This verifies settings, not a deployed
production environment. Expected 400/401/403/404 request logs and mocked health
503 logs inside the tests are negative-case coverage; independent live health
checks returned 200. The only mocks remain existing infrastructure failure tests;
tenant/security tests use real credentials and ORM queries against PostgreSQL.

Frontend checks were not rerun: no frontend or shared frontend transport changes.
Live health API compatibility is verified. Dependencies, Compose configuration,
credential files and volumes are unchanged.

## Final security review

Reviewed the final source and diff for all requested boundaries:

- Organization list and detail resolve the authenticated actor's membership.
- Membership list and mutation target queries filter by the authorized tenant.
- Guessed/foreign UUIDs receive the same 404 behavior as absent scoped objects.
- View authorization asks centralized capabilities, with no scattered role checks.
- Service policy checks both existing and proposed roles; ADMIN cannot manage or
  grant OWNER/ADMIN or elevate itself.
- Every supported membership write takes the same organization lock and reloads
  actor membership; real concurrent owner demotion left exactly one OWNER.
- Real Django Basic authentication rejects anonymous, invalid and inactive users.
- Django staff/superuser flags do not bypass membership scope or capability policy.
- Output serializers expose only required Stage 1 fields and never auth secrets.
- No secrets or Stage 2 domain/functionality were introduced.

No unresolved security finding in the supported Stage 1 operations. Raw SQL/ORM
writes can bypass service invariants and must remain outside supported membership
mutation paths. Administrative account deactivation and consent-based invitations
remain outside this stage, as documented in the architecture.

## Changed files

- ARCHITECTURE.md: Stage 1 boundary, policy, provisioning and invariant limits.
- README.md: current status, endpoint contract and migration/test operating gate.
- backend/config/settings.py: core app, AUTH_USER_MODEL, Django Basic auth.
- backend/config/test_runner.py: guarded dedicated-database test runner.
- backend/config/urls.py: versioned core URL inclusion.
- backend/pyproject.toml: include core in package discovery.
- backend/core/__init__.py
- backend/core/apps.py
- backend/core/models.py
- backend/core/policy.py
- backend/core/tenancy.py
- backend/core/services.py
- backend/core/serializers.py
- backend/core/views.py
- backend/core/urls.py
- backend/core/migrations/__init__.py
- backend/core/migrations/0001_initial.py
- backend/tests/test_identity.py
- infrastructure/postgres/provision-test-database.sh: idempotent admin provisioning.
- scripts/provision_test_database.py: reproducible host entry point and LF normalization.
- STAGE1_REPORT.md

## Final readiness and deferred scope

Stage 1 is ready for the authorized local scope. No unresolved migration or
PostgreSQL integration blocker remains. Operator account/organization provisioning
is documented; no fake accounts or organizations were inserted into development.
All 15 migrations are applied and all 35 backend tests pass. The separate test
schema is retained for repeatable --keepdb runs.

No authentication/product UI, invitations, password reset, external identity,
communication, contacts, channels, campaigns, billing, automations, integrations,
cloud infrastructure or later-stage domain was added. Production deployment/TLS
operations remain separate work. Stop after Stage 1; Stage 2 was not begun.
