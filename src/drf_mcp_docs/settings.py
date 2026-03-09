import logging

from django.conf import settings

logger = logging.getLogger(__name__)

DEFAULTS = {
    # Server
    "SERVER_NAME": "drf-mcp-docs",
    "SERVER_INSTRUCTIONS": "",
    # Schema
    "SCHEMA_ADAPTER": None,
    "SCHEMA_PATH_PREFIX": "/api/",
    "EXCLUDE_PATHS": [],
    "CACHE_SCHEMA": True,
    "CACHE_TTL": None,
    # Transport
    "TRANSPORT": "streamable-http",
    "MCP_ENDPOINT": "/mcp/",
    # Code generation
    "DEFAULT_CODE_LANGUAGE": "javascript",
    "DEFAULT_HTTP_CLIENT": "fetch",
}


def get_setting(name: str):
    user_settings = getattr(settings, "DRF_MCP_DOCS", {})
    if name in user_settings:
        return user_settings[name]
    if name == "CACHE_SCHEMA" and name not in user_settings:
        return not getattr(settings, "DEBUG", False)
    return DEFAULTS[name]


def get_all_settings() -> dict:
    result = {}
    for key in DEFAULTS:
        result[key] = get_setting(key)
    logger.debug("Resolved settings: %s", result)
    return result
