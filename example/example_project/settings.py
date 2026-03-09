from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "example-insecure-key-change-in-production"
DEBUG = True
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "rest_framework",
    "drf_spectacular",
    "drf_mcp_docs",
    "books",
]

MIDDLEWARE = [
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "example_project.urls"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Django REST Framework ---------------------------------------------------

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Bookstore API",
    "DESCRIPTION": "A simple bookstore API for demonstrating drf-mcp-docs.",
    "VERSION": "1.0.0",
}

# --- drf-mcp-docs ------------------------------------------------------------

DRF_MCP_DOCS = {
    "SERVER_NAME": "bookstore-api",
    "SERVER_INSTRUCTIONS": (
        "This is a simple bookstore API with Author and Book models. Books belong to authors via a foreign key."
    ),
    "CACHE_SCHEMA": False,  # Always refresh during development
}
