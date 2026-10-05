import json
import logging
from unittest.mock import MagicMock, patch

from django.db import OperationalError
from django.test import SimpleTestCase
from redis.exceptions import ConnectionError

from infrastructure.logging import JsonFormatter


class HealthTests(SimpleTestCase):
    def test_application(self):
        response = self.client.get("/api/v1/health/application/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    @patch("infrastructure.health.connection")
    def test_database_success(self, database):
        response = self.client.get("/api/v1/health/database/")
        self.assertEqual(response.status_code, 200)
        database.cursor.return_value.__enter__.return_value.execute.assert_called_once_with(
            "SELECT 1"
        )

    @patch("infrastructure.health.connection")
    def test_database_failure_is_sanitized(self, database):
        database.cursor.side_effect = OperationalError("secret-password")
        response = self.client.get("/api/v1/health/database/")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"status": "unavailable"})

    @patch("infrastructure.health.Redis.from_url")
    def test_redis_success(self, factory):
        factory.return_value.__enter__.return_value = MagicMock()
        self.assertEqual(self.client.get("/api/v1/health/redis/").status_code, 200)

    @patch("infrastructure.health.Redis.from_url")
    def test_redis_failure(self, factory):
        factory.side_effect = ConnectionError("secret-password")
        response = self.client.get("/api/v1/health/redis/")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"status": "unavailable"})

    def test_logs_are_json(self):
        record = logging.LogRecord("health", logging.INFO, "", 0, "probe", (), None)
        self.assertEqual(json.loads(JsonFormatter().format(record))["message"], "probe")

    def test_cors_only_trusted_origin(self):
        allowed = self.client.get(
            "/api/v1/health/application/", HTTP_ORIGIN="http://localhost:5173"
        )
        denied = self.client.get(
            "/api/v1/health/application/", HTTP_ORIGIN="https://untrusted.example"
        )
        self.assertEqual(allowed["Access-Control-Allow-Origin"], "http://localhost:5173")
        self.assertNotIn("Access-Control-Allow-Origin", denied)
