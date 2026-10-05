from django.core.exceptions import ImproperlyConfigured
from django.db import connections
from django.test.runner import DiscoverRunner


class ProvisionedDatabaseRunner(DiscoverRunner):
    """Reuse the explicitly provisioned database without CREATE/DROP privileges."""

    def setup_databases(self, **kwargs):
        if not self.keepdb:
            raise ImproperlyConfigured("Run tests with --keepdb after provisioning test_relayn.")
        database = connections["default"]
        if (
            database.vendor != "postgresql"
            or database.settings_dict["TEST"]["NAME"] != "test_relayn"
            or database.settings_dict["NAME"] == "test_relayn"
        ):
            raise ImproperlyConfigured("Tests require a separate PostgreSQL test_relayn database.")
        with database.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", ["test_relayn"])
            if cursor.fetchone() is None:
                raise ImproperlyConfigured("Provision test_relayn before running tests.")
        return super().setup_databases(**kwargs)
