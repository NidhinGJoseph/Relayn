# Stage 3 implementation report

Implemented generic channel abstraction only. The adapter and credential boundaries
were explained in chat before coding. No Meta integration or fake provider exists.

## Decisions and behavior

- Channel is a global transport catalog; WHATSAPP is the only currently accepted
  code. ChannelAccount has a required organization FK and a protected channel FK.
  Future channels extend this catalog and adapter support without altering future
  channel-neutral communication models. No communication models were added.
- Account status defaults to INACTIVE; ACTIVE and DISABLED are the other allowed
  values. A database constraint enforces the status set. ACTIVE is an operator
  switch, not proof of provider connectivity. No automatic activation is provided.
- Account lookups verify active-user membership before querying by organization
  and account ID. Foreign IDs, unauthorized organization IDs, inactive users and
  staff/superusers without membership cannot bypass the tenant boundary.
- The internal send seam rejects inactive/disabled accounts. Missing provider,
  unavailable adapter and unsupported provider/channel combinations raise distinct
  domain failures. There is no public sending API, permission grant, outbound
  persistence, retry workflow, webhook route or provider HTTP call.
- ProviderAdapter is an abstract contract for configuration validation, text
  sending and inbound-text normalization. Small neutral dataclasses carry message
  inputs/results. No provider-specific fields or payloads enter persistence.
  The code-owned provider registry is empty. Resolution tests temporarily use the
  abstract contract as registry metadata; they implement no fake transport.
- The explicit secrets boundary reads deployment-managed JSON files from an
  absolute CHANNEL_SECRETS_DIR using organization/account UUIDs. Credentials,
  provider configuration and arbitrary filesystem paths have no model fields.
  Missing/invalid configuration raises sanitized errors. Provider adapters own
  schema validation. Only trusted adapter/service code may consume the mapping.

## Credential deployment limitations

No production secret store or application encryption has been invented. The
current host-run deployment uses protected files; operators must enforce ACLs,
secret distribution, backup protection, rotation and any at-rest encryption.
Files should live outside the checkout; channel-secrets directories are also
Git-ignored. No real credentials or configuration files were created. Future
production secret-store mounts can preserve this loader contract. Future product
entry points must implement send-specific role permissions and entitlements in
addition to the membership and tenant checks supplied here. These are deliberate
later-stage responsibilities, not completed product sending capabilities.

## Migration review and execution

Reviewed channels.0001_initial source, migrate --plan and sqlmigrate output before
execution. It depends on core.0001_initial and creates only Channel and
ChannelAccount, their primary keys, organization/channel foreign keys and indexes,
and channel/status checks. No data migration, account provisioning or modification
of existing tables. Reversal drops the new tables and loses account records.
Applied successfully to local relayn; test setup applied it to test_relayn.
Catalog rows are operator-provisioned with the documented get_or_create command.

## Validation actually run

- Full backend suite: `.venv/Scripts/python.exe manage.py test --keepdb --noinput`
  from backend: 53 tests passed in 45.370 seconds on PostgreSQL.
- Ten new tests cover organization ownership, required tenant ownership, cross-tenant
  account lookup/send rejection, no staff bypass, inactive membership, account
  status, explicit missing/unavailable provider failures, database constraints,
  per-account configuration isolation/invalid configuration, registry resolution,
  unsupported channels, and abstract-contract enforcement.
- Django system check: zero issues (also run by tests).
- makemigrations --check --dry-run: no changes detected.
- migrate --plan after applying: no planned operations.
- Ruff check backend and scripts: passed.
- Ruff format --check backend and scripts: all 44 files formatted.
- git diff --check: passed. Reviewed new source and migration plus tracked diff
  for scope, authorization, tenant filters, error paths and secrets.

The first migration-generation command could not check database history because
the sandbox denied the local database connection; generation succeeded. Subsequent
approved local database checks, migration execution and tests succeeded. Initial
Ruff findings were formatting/import issues in new files, corrected before the
passing checks. Frontend checks and provider integration tests are not applicable:
neither frontend nor provider integration was implemented. No implementation or
verification blocker remains.

## Changed files for this stage

- .gitignore
- ARCHITECTURE.md (Stage 3 section)
- README.md (Stage 3 section)
- STAGE3_REPORT.md
- backend/config/settings.py (channels registration and secrets-directory setting)
- backend/pyproject.toml (channels package discovery)
- backend/channels/__init__.py
- backend/channels/models.py
- backend/channels/exceptions.py
- backend/channels/providers.py
- backend/channels/secrets.py
- backend/channels/services.py
- backend/channels/migrations/__init__.py
- backend/channels/migrations/0001_initial.py
- backend/tests/test_channels.py

Pre-existing Stage 2 changes were retained. Stopped after Stage 3.
