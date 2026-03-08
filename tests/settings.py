SECRET_KEY = "test-secret-key-for-drf-mcp-docs"
DEBUG = True

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "rest_framework",
    "drf_spectacular",
    "drf_mcp_docs",
    "tests.testapp",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

ROOT_URLCONF = "tests.testapp.urls"

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "rest_framework.schemas.openapi.AutoSchema",
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

DRF_MCP_DOCS = {
    "SERVER_NAME": "test-mcp",
    "CACHE_SCHEMA": False,
}
