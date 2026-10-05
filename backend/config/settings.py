from pathlib import Path
from urllib.parse import urlsplit

import environ
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
env = environ.Env()
# Local convenience only; existing process environment always wins.
environ.Env.read_env(BASE_DIR / ".env", overwrite=False)
ENVIRONMENT = env("DJANGO_ENV", default="production")
if ENVIRONMENT not in {"development", "production"}:
    raise ImproperlyConfigured("DJANGO_ENV must be development or production")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
SECRET_KEY = env("DJANGO_SECRET_KEY")
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS")
if not SECRET_KEY or not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS:
    raise ImproperlyConfigured("Provide a secret key and explicit DJANGO_ALLOWED_HOSTS")
if ENVIRONMENT == "production" and (
    DEBUG or len(SECRET_KEY) < 50 or SECRET_KEY.startswith("django-insecure-")
):
    raise ImproperlyConfigured(
        "Production requires DEBUG=false and a strong secret key (50+ chars)"
    )
DATABASES = {"default": env.db("DATABASE_URL")}
if DATABASES["default"]["ENGINE"] != "django.db.backends.postgresql":
    raise ImproperlyConfigured("DATABASE_URL must use PostgreSQL; SQLite is not supported")
if not DATABASES["default"].get("NAME") or not DATABASES["default"].get("HOST"):
    raise ImproperlyConfigured("DATABASE_URL must include an explicit database name and host")
DATABASES["default"].setdefault("OPTIONS", {}).setdefault("connect_timeout", 5)
DATABASES["default"]["CONN_MAX_AGE"] = 60
REDIS_URL = env("REDIS_URL")
if urlsplit(REDIS_URL).scheme not in {"redis", "rediss"} or not urlsplit(REDIS_URL).hostname:
    raise ImproperlyConfigured("REDIS_URL must be a valid redis:// or rediss:// URL")
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "rest_framework",
    "corsheaders",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"
USE_TZ = True
TIME_ZONE = "UTC"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
CORS_URLS_REGEX = r"^/api/.*$"
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
}
CELERY_BROKER_URL = REDIS_URL
CELERY_TASK_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_RESULT_SERIALIZER = "json"
CELERY_TASK_IGNORE_RESULT = True
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
SECURE_SSL_REDIRECT = ENVIRONMENT == "production"
SESSION_COOKIE_SECURE = ENVIRONMENT == "production"
CSRF_COOKIE_SECURE = ENVIRONMENT == "production"
SECURE_HSTS_SECONDS = 31536000 if ENVIRONMENT == "production" else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = ENVIRONMENT == "production"
SECURE_HSTS_PRELOAD = ENVIRONMENT == "production"
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"json": {"()": "infrastructure.logging.JsonFormatter"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "json"}},
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", default="INFO")},
    "loggers": {"django": {"handlers": ["console"], "level": "INFO", "propagate": False}},
}
