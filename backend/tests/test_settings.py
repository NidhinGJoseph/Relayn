import os
import subprocess
import sys

from django.test import SimpleTestCase


class ConfigurationTests(SimpleTestCase):
    def check_settings(self, code="import config.settings", **changes):
        environment = os.environ.copy()
        environment.update(changes)
        return subprocess.run(
            [sys.executable, "-c", code],
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_missing_secret_fails(self):
        result = self.check_settings(DJANGO_SECRET_KEY="")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Provide a secret key", result.stderr)

    def test_sqlite_rejected(self):
        result = self.check_settings(DATABASE_URL="sqlite:///db.sqlite3")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("PostgreSQL", result.stderr)

    def test_production_debug_rejected(self):
        result = self.check_settings(DJANGO_ENV="production", DJANGO_DEBUG="true")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Production requires", result.stderr)

    def test_invalid_redis_rejected(self):
        result = self.check_settings(REDIS_URL="https://localhost")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("REDIS_URL", result.stderr)

    def test_incomplete_database_url_rejected(self):
        result = self.check_settings(DATABASE_URL="postgresql://localhost")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("database name and host", result.stderr)

    def test_database_tls_options_are_preserved(self):
        result = self.check_settings(
            code=(
                "from config.settings import DATABASES; "
                "options = DATABASES['default']['OPTIONS']; "
                "assert options['sslmode'] == 'verify-full'; "
                "assert options['sslrootcert'] == 'root.crt'; "
                "assert options['connect_timeout'] == 9"
            ),
            DATABASE_URL=(
                "postgresql://relayn:example@localhost:5432/relayn"
                "?sslmode=verify-full&sslrootcert=root.crt&connect_timeout=9"
            ),
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_default_database_timeout_is_applied(self):
        result = self.check_settings(
            code=(
                "from config.settings import DATABASES; "
                "assert DATABASES['default']['OPTIONS']['connect_timeout'] == 5"
            ),
            DATABASE_URL="postgresql://relayn:example@localhost:5432/relayn",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
