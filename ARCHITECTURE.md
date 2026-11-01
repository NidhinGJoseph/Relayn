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

## Stage 2 organization entitlements

`billing` owns entitlement persistence and its service interface, independent of
pricing. Definitions in billing.definitions contain only capability and limit
keys. OrganizationEntitlement stores one explicit assignment per organization/key.
Database checks enforce known keys, boolean-only capability values, and nonnegative
integer-only limits. There are no default grants, plan tiers, prices, subscriptions,
payment operations, or product implementations.

Business code reads only through billing.services.has_capability, get_limit, and
require_capability. Missing/disabled capabilities deny access; require_capability
raises CapabilityUnavailable (DRF 403, code capability_unavailable). A missing limit
returns None (unassigned, never unlimited); zero is an explicit zero allocation.
Unknown or wrong-kind keys raise ValueError. No usage counting or quota enforcement
is implemented: later resource operations must explicitly enforce assigned limits.

Request callers must resolve authorized organization membership through core.tenancy
before calling these services. The services accept persisted Organization objects,
not client-supplied UUIDs, and scope every query to that organization. Possessing
an Organization object is not itself authorization. Existing core.policy member
permissions remain independent; product access requires both applicable member
permission and organization entitlement. Staff/owner status grants no entitlement.

set_capability and set_limit are trusted internal/operator assignment services for
Django shell use, with explicit type validation and atomic organization/key upserts.
No assignment endpoint or tenant-accessible admin interface exists. Future tenant
endpoints must not expose these operator services. ORM/SQL writes bypass service
validation but remain subject to the database's uniqueness and typed-value checks.
Adding a new key requires updating definitions and migrating the database check.

## Stage 3 channel abstraction

`channels` owns Channel and organization-owned ChannelAccount. WHATSAPP is the
only enabled channel code. Adding INSTAGRAM, MESSENGER or WEBCHAT requires extending
the channel catalog constraint/choices and registering a real supporting adapter;
future communication models reference ChannelAccount without transport-specific
fields. Operators create catalog rows and accounts through Django shell. No tenant
account administration or sending endpoint is provided at this stage.

Account status is INACTIVE (default), ACTIVE or DISABLED, protected by a database
check. ACTIVE means operator-enabled, not verified provider connectivity. Accounts
may exist without a provider; sending then raises ProviderNotConfigured. Unknown
providers and unsupported channel/provider pairs raise separate explicit failures.
There are no installed providers, Meta integration, fake adapters or fallbacks.

ProviderAdapter defines configuration validation, plain-text sending and inbound
text normalization with neutral input/output types. Provider envelopes, addressing
translation and credentials stay behind this boundary. No webhook ingress, message
persistence, retries, delivery guarantees or production sending workflow is added.
The internal send seam verifies current active-user membership and scopes account
lookup by organization before checking status or resolving transport. Future product
entry points must add send-specific role permissions and entitlements; membership
alone does not define the eventual product authorization policy.

Deployment-owned JSON configuration lives at
`CHANNEL_SECRETS_DIR/<organization UUID>/<account UUID>.json`. The setting must be
an absolute directory; missing/unreadable/invalid files fail explicitly. No provider
configuration, secret values or arbitrary secret paths are stored in generic
models. The loader is trusted internal code, invoked only after tenant-scoped
resolution by the send service, and returns sensitive mappings only to adapters.
Adapters validate their own configuration schema; provider changes require operators
to replace the corresponding file. Errors never echo file contents. Filesystem ACLs,
backups, rotation and distribution are operator responsibilities. This is a mounted
secret-file boundary for the current host-run architecture, not application-level
encryption or a secrets manager. Production can mount files from its secret store;
a future store implementation can replace the loader without changing core models.


## Stage 4 contacts and communication persistence

`communications` owns minimal Contact/ContactIdentity, Conversation and Message
models. Contacts are identity containers, without CRM behavior. Identity matching
uses (organization, channel account, opaque external identity); adapters must
supply normalized identifiers. No phone field globally identifies a person.
Explicit trusted linking can attach another identity to an existing tenant contact;
there is no automatic merge based on phone, email or display name.

A conversation belongs to one identity, hence one channel account and contact.
One durable conversation is reused for that identity. Group participants and agent
assignment are not implemented, so no participant table is needed. New inbound
messages do not implicitly reopen a resolved conversation. Explicit transitions:
OPEN -> PENDING/RESOLVED, PENDING -> OPEN/RESOLVED, RESOLVED -> OPEN; repeats are no-ops.

Inbound text is RECEIVED. Outbound records start QUEUED; this does not dispatch.
Delivery progresses QUEUED -> SENT -> DELIVERED -> READ, allowing forward skips
and ignoring late lower-rank events. QUEUED/SENT may become terminal FAILED;
DELIVERED/READ cannot fail. Retrying a failed send requires a new outbound request.
External IDs may be bound once through the delivery service and cannot change.
`occurred_at` records message time; `status_at` records the latest accepted state
change without moving backward; created/updated timestamps record persistence.
Metadata is supplemental JSON, excluded from inbox responses to avoid exposing
provider payloads. Text, direction, IDs, status and timestamps are explicit fields.

Supported writes use atomic services and a shared organization row lock. Services
validate every referenced tenant object. Database checks protect state/type values;
unique constraints protect identity matching, conversation reuse, account-scoped
external message IDs (both directions), and tenant-scoped outbound UUID keys.
Conflicting reuse raises an explicit validation error. Cross-row tenant consistency
and transition history are service invariants: direct ORM/SQL writes are unsupported
and can bypass these checks. Organization locking serializes writes per tenant;
revisit lock granularity if measured contention warrants it.

Persistence services are trusted internal boundaries accepting an authorized
persisted Organization. They do not authorize an arbitrary caller by themselves.
REST access resolves active membership and requires SHARED_INBOX entitlement;
all four existing membership roles can read and change conversation status.
There is no staff bypass. Status writes recheck membership after the parent lock.
Endpoints under /api/v1/organizations/<uuid>/conversations/ provide paginated GET
lists, GET/PATCH <conversation uuid>/ and paginated GET <conversation uuid>/messages/.
Messages sort ascending by occurred_at, created_at, then UUID for stable ties.
No public contact creation, message sending, webhook ingress, Meta adapter,
automation, CRM workflow or AI is implemented.
