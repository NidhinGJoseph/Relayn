import logging

from django.conf import settings
from django.db import DatabaseError, connection
from redis import Redis
from redis.exceptions import RedisError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)


class ApplicationHealth(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"status": "ok"})


class DatabaseHealth(ApplicationHealth):
    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except DatabaseError:
            logger.error(
                "Dependency health check failed", extra={"dependency": "database"}, exc_info=True
            )
            return Response({"status": "unavailable"}, status=503)
        return Response({"status": "ok"})


class RedisHealth(ApplicationHealth):
    def get(self, request):
        try:
            with Redis.from_url(
                settings.REDIS_URL, socket_connect_timeout=2, socket_timeout=2
            ) as client:
                if not client.ping():
                    return Response({"status": "unavailable"}, status=503)
        except RedisError:
            logger.error(
                "Dependency health check failed", extra={"dependency": "redis"}, exc_info=True
            )
            return Response({"status": "unavailable"}, status=503)
        return Response({"status": "ok"})
