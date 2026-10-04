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
Tailwind CSS. These are directions, not installed or initialized components.

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
Stage 0 application scaffolding has NOT been completed. Each later stage should
implement only its agreed scope and satisfy the AGENTS.md definition of done.
