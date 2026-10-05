# Intended architecture

Relayn is a multi-tenant customer communication and business-action platform.
The initial product covers official Meta API WhatsApp communication, shared team
inbox, contacts, conversations, leads, workflows, Meta attribution, and analytics.
The platform must also accommodate Instagram, Messenger, other channels, public
APIs, external business systems, and vertical products such as Rental OS.

## Architecture and stack

Build a modular monolith with explicit domain boundaries and versioned REST APIs
(for example, `/api/v1/`). Use internal events where they clarify collaboration
between domains. Do not introduce premature microservices.

The intended backend uses Python, Django, Django REST Framework, PostgreSQL,
Redis, and Celery. The intended frontend uses React, TypeScript, Vite, and
Tailwind CSS. Stage 0 initializes these stacks without product capabilities.

## Conceptual domain boundaries

The names below are conceptual/domain boundaries. Create Django apps or modules
only when an implementation stage requires them; do not scaffold them in advance.

| Boundary | Responsibility |
| --- | --- |
| `core/` | Organization identity, membership, tenant context, and foundational platform primitives. |
| `channels/` | Channel accounts and provider adapters, including Meta/WhatsApp transport and provider payload translation. |
| `communications/` | Channel-neutral conversations, messages, participants, and shared inbox behavior. |
| `crm/` | Contacts, leads, and customer relationship business logic. |
| `automation/` | Workflows reacting to explicit events and invoking defined actions. |
| `attribution/` | Acquisition/source attribution, including normalization of Meta attribution inputs. |
| `integrations/` | Public integration contracts and adapters for external business systems. |
| `billing/` | Billing lifecycle and entitlement decisions, separate from business capabilities. |
| `analytics/` | Tenant-scoped reporting and derived metrics through defined domain interfaces. |
| `configurator/` | Validated organization-level configuration of supported platform capabilities. |

## Dependency principles

- `core` must not depend on product-specific modules.
- `communications` must remain channel-neutral. Its core models and business
  rules must not depend on WhatsApp, Meta payloads, or provider SDK types.
- Meta/WhatsApp implementations belong behind channel/provider adapters.
  Translate provider-specific inputs and outputs at that boundary.
- CRM may reference communication-domain identifiers through defined interfaces.
  It must not duplicate communication logic or reach into provider internals.
- Automation operates through explicit events/actions with defined contracts;
  avoid hidden side effects and circular domain dependencies.
- Billing/entitlements remain separate from business capabilities. Capabilities
  consult defined entitlement interfaces instead of embedding billing logic.
- Vertical applications such as Rental OS integrate through APIs/events rather
  than being imported into the core platform.
- External systems use adapters and defined interfaces. Reuse existing
  abstractions before adding new ones, and keep each module cohesive.

## Tenant isolation, consistency, and failures

Organization is the tenant boundary. Authorize tenant context against the
authenticated actor; a client-supplied organization ID is never sufficient.
Every tenant-owned query, including background work and reporting, must enforce
organization isolation. Cross-domain references must preserve that boundary.

Use database constraints for important invariants and transactions for atomic
operations. Asynchronous actions must have explicit failure handling and, where
retries are introduced, defined idempotency behavior.

Keep API error, validation, and pagination conventions consistent. Missing
required configuration and provider failures must fail clearly and remain
diagnosable, without exposing secrets or internal stack traces to clients.
Never silently substitute SQLite, mock providers, fake responses, or fabricated
data. Secrets belong in appropriate configuration, never source control or logs.

## Staged implementation

This document records intended boundaries, not implemented functionality.
Stage 0 contains configuration, infrastructure health checks, and a minimal
frontend shell. Each later stage should
implement only its agreed scope and satisfy the AGENTS.md definition of done.

## Stage 0 structure

`backend/config` owns environment settings and process entry points.
`backend/infrastructure` owns dependency probes and structured logging; it must
not contain product logic. `frontend/src/api` owns HTTP transport, while React
components own presentation. PostgreSQL is the only persistence backend. Redis
is required infrastructure and the Celery broker; no tasks or result backend are
configured. Health endpoints are public and return no configuration details.

DRF denies anonymous access by default. Authentication and organization context
are intentionally deferred; no tenant-owned resources exist yet. Future product
endpoints must establish verified organization membership before querying data.
No product module, adapter interface, event bus, or tenant model is scaffolded.
JSON logs allowlist contextual fields; callers must never log secrets or message
content. Production uses HTTPS and explicit hosts; reverse-proxy trust must be
configured deliberately during deployment, never by blindly trusting headers.

## Local Stage 0 infrastructure

Root Compose runs only PostgreSQL 16 and Redis 7.4; Django/React remain host-run.
The application database identity is a non-superuser owning the relayn database,
separate from the initialization administrator. Secret files and backend/.env are
ignored. Services publish only loopback ports 5433/6380 with password authentication.
Named volumes preserve PostgreSQL and Redis AOF broker data. Init scripts never
reset an existing volume. This is development infrastructure; production TLS and
secret distribution remain deployment responsibilities.

## Stage 1 identity and tenant boundary

Stage 1 introduces `backend/core` only. `core.User` extends Django AbstractUser
with a UUID primary key; AUTH_USER_MODEL is configured before initial migrations.
Django owns credential checking and password hashing. DRF BasicAuthentication
provides the minimal authenticated API; credentials must travel over HTTPS in
production. There is no registration, session, token, or external identity API.
Public infrastructure views retain their explicit empty authentication classes.

Organization (UUID, name, timestamps) is the tenant boundary. Membership (UUID,
user, organization, role, timestamps) is authoritative. User/organization pairs
are unique; roles have model choices and a database check. Foreign keys have
Django's standard indexes; the unique organization/user index supports scoped
membership resolution alongside the user index. Membership user deletion is
PROTECT, preventing account deletion from silently cascading ownership away.

Organization context is explicit in `/api/v1/organizations/<uuid>/...`. Resolve
membership using the authenticated actor and organization ID in one ORM query
before accessing the organization. Resource queries then filter by that verified
organization. No permanent current organization, default tenant, or staff/
superuser tenant bypass exists. Inaccessible and absent scoped objects return
404; malformed path UUIDs also return 404. DRF provides validation errors (400),
authentication failures (401), capability failures (403), and page-number lists.

| Capability | OWNER | ADMIN | MANAGER | AGENT |
| --- | --- | --- | --- | --- |
| organization.view | yes | yes | yes | yes |
| members.view | yes | yes | yes | yes |
| members.create | yes | yes | no | no |
| members.change_role | yes | yes | no | no |
| members.remove | yes | yes | no | no |

Mutation capabilities additionally require role authority: OWNER may manage all
roles; ADMIN may manage only MANAGER/AGENT targets and grant only those roles.
ADMIN cannot modify itself or other ADMIN/OWNER memberships. No implicit role
ordering or Django administrative privilege substitutes for this policy.

All supported membership writes go through core.services. Transactions lock the
organization, reload actor membership after lock acquisition, enforce capability
and target/proposed-role authority, and protect the final owner. Organization
creation is an operator-facing service that creates its owner atomically, without
a public creation API. Every concurrent supported mutation uses the same parent
lock. This is a service invariant, not a cross-row database constraint: direct
ORM/SQL writes can bypass it and must not be used by future endpoints, scripts,
or admin actions. Organization deletion has no API. User deactivation and direct
administrative writes are outside these membership mutation guarantees.

Direct membership creation accepts an existing active account's UUID and role;
no account lookup/search or invitation workflow is provided. Operators provision
accounts through Django and supply known IDs. Missing/inactive/duplicate account
IDs receive the same generic error. Successful authorized addition necessarily
confirms that the supplied account is eligible. This is deliberate operator
access, not a public account discovery or consent-based invitation mechanism.

The Stage 1 graph has been approved and applied to the local relayn database.
PostgreSQL integration/security tests pass on dedicated test_relayn. Its creation
uses the existing Compose bootstrap administrator via the reproducible scripts,
without elevating relayn. TEST.NAME is fixed to test_relayn; the test runner
requires prior provisioning and --keepdb, and rejects application/test database
name collisions. See STAGE1_REPORT.md for schema and validation evidence.
