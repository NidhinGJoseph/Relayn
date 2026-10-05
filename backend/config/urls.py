from django.urls import include, path

from infrastructure.health import ApplicationHealth, DatabaseHealth, RedisHealth

urlpatterns = [
    path("api/v1/", include("core.urls")),
    path("api/v1/health/application/", ApplicationHealth.as_view()),
    path("api/v1/health/database/", DatabaseHealth.as_view()),
    path("api/v1/health/redis/", RedisHealth.as_view()),
]
