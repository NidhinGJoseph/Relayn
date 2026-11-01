# Stage 4 completion report

Implemented only contacts, identities, conversations, text message persistence,
explicit status transitions, and scoped inbox REST endpoints. See ARCHITECTURE.md
Stage 4 for ownership, identity matching, authorization, retry and transition policy.
ConversationParticipant is unnecessary for the single-contact/account scope.
MessageStatus is a constrained enum rather than a separate tenant-owned lookup table.

## Verification

- Full backend PostgreSQL suite: 61 tests passed before the final small service
  refinements and two added tests.
- Final focused PostgreSQL suite: 10 communication tests passed, including real
  simultaneous webhook retry writes using separate database connections.
- Coverage includes database uniqueness, conflicting duplicate payloads, tenant
  isolation, conversation ownership, identity matching/linking, outbound request
  idempotency, delivery ordering/failures, conversation transitions, API auth,
  entitlement denial, message ordering, metadata validation and atomic rollback.
- Ruff check backend: passed. New Python files formatted with Ruff.
- Django system check: passed.
- makemigrations --check --dry-run with database access: no changes detected.
- migrate --plan inspected: only communications.0001_initial is pending locally.
- Migration reviewed before tests executed it: additive tables/index/check/unique
  constraints, protected foreign keys, correct dependencies, no data migration or
  destructive operations. Django supplies reverse operations (dropping the new
  schema); reversal has not been executed.
- Migration applied successfully by the test runner to test_relayn. Application
  database migration has deliberately not been executed.
- Diff and new files reviewed; git diff --check passed. No credentials added.

## Changed files

- ARCHITECTURE.md
- STAGE4_REPORT.md
- backend/config/settings.py
- backend/config/urls.py
- backend/pyproject.toml
- backend/communications/__init__.py
- backend/communications/models.py
- backend/communications/services.py
- backend/communications/serializers.py
- backend/communications/views.py
- backend/communications/urls.py
- backend/communications/migrations/__init__.py
- backend/communications/migrations/0001_initial.py
- backend/tests/test_communications.py

## Limits

No Meta API, provider dispatch, webhook endpoint, CRM workflows, automation, AI,
group conversations or agent assignment. Identity normalization belongs to future
provider adapters; opaque IDs are matched exactly within a tenant/account.
All supported writes must use the services: direct ORM/SQL writes can bypass
cross-row tenant validation and transition rules. Tenant-wide write locking favors
simple correctness and may need refinement if contention becomes measurable.
Deployments must run the reviewed migration before using these endpoints and
explicitly assign SHARED_INBOX to organizations that should access the inbox.
