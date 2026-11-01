"""Generate local Compose secrets once; never replace existing credentials."""

import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
FILES = [
    BACKEND / ".env",
    BACKEND / ".env.postgres-admin-password",
    BACKEND / ".env.postgres-app-password",
    BACKEND / ".env.redis-password",
]


def main():
    if any(path.exists() for path in FILES):
        raise SystemExit(
            "Existing local configuration found; no secrets changed. "
            "Check the existing configuration and Docker volumes before making changes."
        )
    admin_password = secrets.token_hex(32)
    app_password = secrets.token_hex(32)
    redis_password = secrets.token_hex(32)
    secret_key = secrets.token_urlsafe(64)
    contents = [
        (
            "DJANGO_ENV=development\nDJANGO_DEBUG=true\n"
            f"DJANGO_SECRET_KEY={secret_key}\n"
            "DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1\n"
            f"DATABASE_URL=postgresql://relayn:{app_password}@127.0.0.1:5433/relayn\n"
            f"REDIS_URL=redis://:{redis_password}@127.0.0.1:6380/0\n"
            "CORS_ALLOWED_ORIGINS=http://localhost:5173\nLOG_LEVEL=INFO\n"
        ),
        admin_password + "\n",
        app_password + "\n",
        redis_password + "\n",
    ]
    for path, content in zip(FILES, contents, strict=True):
        with path.open("x", encoding="utf-8", newline="\n") as output:
            output.write(content)
        path.chmod(0o600)
    print("Local environment and Compose secret files created; no values displayed.")


if __name__ == "__main__":
    main()
