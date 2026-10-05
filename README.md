# Relayn

Stage 0 infrastructure and Stage 1 identity, membership and tenant authorization.
Stage 1 migrations and PostgreSQL integration validation are complete.
Read AGENTS.md, ENGINEERING.md, and ARCHITECTURE.md before changes.

## Backend

Requires Python 3.11+ and Docker Desktop (Linux containers).
From the repository root (PowerShell):

```powershell
python -m venv backend/.venv
backend/.venv/Scripts/python -m pip install -r backend/requirements.lock
python scripts/setup_local_env.py
docker compose config
docker compose up -d --wait
```

The setup script generates local secrets once and refuses to overwrite existing
configuration. From `backend/`:

```powershell
.venv/Scripts/python manage.py check
.venv/Scripts/python manage.py test --keepdb
.venv/Scripts/ruff check .
.venv/Scripts/ruff format --check .
.venv/Scripts/python manage.py makemigrations --check --dry-run
.venv/Scripts/python manage.py migrate --plan
.venv/Scripts/python manage.py runserver
```

Review `core.0001_initial` and Django auth/contenttypes migrations and their plan
before running `migrate`. The Stage 1 graph was approved and applied locally;
see STAGE1_REPORT.md for results. Production must set
DJANGO_ENV=production, DEBUG=false, a strong unique secret (50+ characters),
explicit allowed hosts, DATABASE_URL and REDIS_URL. Run `check --deploy` before
deploying. Missing settings fail at startup; unreachable services return 503
from readiness probes. There is no SQLite fallback. Infrastructure endpoints:
`/api/v1/health/application/`, `/api/v1/health/database/`, `/api/v1/health/redis/`.
Application liveness does not imply dependency readiness.

Celery entry point: `.venv/Scripts/celery -A config worker --loglevel=INFO`.
No background jobs exist; there is no need to start a worker for Stage 0.
Production serving, TLS termination, secrets management and service provisioning
are deployment work beyond this scaffold. Do not use Django runserver in production.

## Frontend

From `frontend/`:

```powershell
npm ci
Copy-Item .env.example .env
npm run dev
npm run lint
npm run format:check
npm test
npm run build
```

Vite environment variables are public bundle configuration, never secrets.
Set VITE_API_BASE_URL explicitly; it must end with `/api/v1/`.
Development CORS allows only the configured frontend origin. Production CORS
is empty by default; explicitly configure trusted origins when needed.
Ruff formats/lints Python; ESLint, TypeScript and Prettier check the frontend.
Dependency pins are in requirements.lock and package-lock.json.

## Infrastructure configuration

Root-level Compose provisions PostgreSQL 16 and Redis 7.4 only. Django and Vite
run on the host. PostgreSQL uses a separate bootstrap administrator and a
non-superuser `relayn` application login owning the `relayn` database. Host ports
are bound to 127.0.0.1:5433 (PostgreSQL) and 127.0.0.1:6380 (Redis). Authentication
is required; these local-only services use plaintext transport, not production TLS.
PostgreSQL data and Redis AOF data use named volumes. Redis AOF retains Celery
broker data across container restarts (every-second fsync may lose the last second).

`python scripts/setup_local_env.py` creates backend/.env and three ignored secret
files with generated values. Compose mounts secrets as files, not credential
values in its environment or rendered configuration. Keep those files private.
Never commit or print them. Existing configuration is not overwritten. If partial
configuration exists, reconcile it with the existing volumes before changing secrets.
Initialization runs only on an empty PostgreSQL volume; changing a secret file
does not rotate a password already stored in PostgreSQL.

Use `docker compose ps` to inspect health. `docker compose down` stops/removes
containers but retains data. Never use `down -v` or delete volumes without explicit
approval. No migration is run automatically. Health checks run authenticated
PostgreSQL SELECT 1 and Redis PING; Django connectivity verifies the application
role separately. Never change PostgreSQL authentication to trust to fix failures.

Settings load `backend/.env` regardless of working directory; existing process
variables take precedence. Remove stale process overrides when changing the file.

Percent-encode special characters in URL usernames/passwords. For PostgreSQL,
URL query parameters such as `sslmode=verify-full`, `sslrootcert`, and
`connect_timeout` are preserved. Supply the server's actual TLS requirements and
CA certificate; never remove SSL requirements just to make a probe pass.
Redis supports `redis://username:password@host:port/0` or `rediss://` for TLS;
authentication and TLS must match the server. Host-run Django connects to a
published container port on localhost; container-run Django uses the service
hostname on its shared network. Do not use container hostnames from host-run Django.

After provisioning, validate with the real configuration (no example URL overrides):

```powershell
# From backend/: these commands do not change the database.
.venv/Scripts/python manage.py check
.venv/Scripts/python manage.py migrate --plan
.venv/Scripts/python manage.py shell -c "from django.db import connection; connection.ensure_connection(); print('PostgreSQL connected')"
.venv/Scripts/python manage.py shell -c "from django.conf import settings; from redis import Redis; client = Redis.from_url(settings.REDIS_URL, socket_connect_timeout=2, socket_timeout=2); print('Redis PING:', client.ping()); client.close()"
```

## Stage 1 API and provisioning

All identity endpoints require Django credentials through HTTP Basic authentication.
Use HTTPS in production. No registration, invitation, login UI, or token service
exists. The reviewed Stage 1 migrations have been applied locally; operators
can provision accounts and organizations through the documented services.

| Method | Path under `/api/v1/` | Behavior |
| --- | --- | --- |
| GET | users/me/ | Current UUID and username |
| GET | organizations/ | Paginated organizations belonging to the actor |
| GET | organizations/<organization UUID>/ | Authorized organization details |
| GET | organizations/<organization UUID>/members/ | Paginated scoped memberships |
| POST | organizations/<organization UUID>/members/ | Add known active account |
| PATCH | organizations/<organization UUID>/members/<membership UUID>/ | Change role |
| DELETE | organizations/<organization UUID>/members/<membership UUID>/ | Remove member |

POST body: `{"user_id": "<account UUID>", "role": "AGENT"}`.
PATCH body: `{"role": "MANAGER"}`. Roles are OWNER, ADMIN, MANAGER, AGENT.
The role/capability and authority matrix is in ARCHITECTURE.md. No tenant context
is inferred; always supply the organization UUID in the path.

Operators can provision accounts with
`get_user_model().objects.create_user(...)` and organizations with
`core.services.create_organization(owner=user, name="...")` in Django shell.
Supply passwords interactively; never put real credentials into shell history.
All membership mutations must use core.services; raw ORM writes bypass the
transactional ownership policy. Do not register writable membership admin views
that bypass these services.

The complete backend suite is `.venv/Scripts/python manage.py test --keepdb`
from backend. It includes real PostgreSQL integration and concurrent ownership
tests. Django is explicitly configured to use `test_relayn`, separate from
`relayn`; the application role remains NOCREATEDB. The test runner requires
`--keepdb` and prior provisioning, and refuses unsafe database names.

Provision the dedicated database from the repository root using the existing
Compose bootstrap administrator (password read inside the container):

```powershell
backend/.venv/Scripts/python scripts/provision_test_database.py
```

If Docker is not on PATH, pass `--docker` with its executable path. The script
creates only `test_relayn`, owned by relayn, revokes PUBLIC database access,
verifies ownership and least privilege, and safely reuses an existing database.
It normalizes shell line endings and never prints administrator credentials.
It does not grant database creation privileges, reset data, or drop databases.
`--keepdb` preserves the test schema; test fixtures are rolled back/flushed only
inside the dedicated test database. Do not store development data there.
