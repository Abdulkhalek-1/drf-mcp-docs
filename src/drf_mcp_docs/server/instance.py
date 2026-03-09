from __future__ import annotations

import logging
import threading
import time

from mcp.server.fastmcp import FastMCP

from drf_mcp_docs.adapters import get_adapter
from drf_mcp_docs.schema.processor import SchemaProcessor
from drf_mcp_docs.settings import get_setting

logger = logging.getLogger(__name__)

_processor: SchemaProcessor | None = None
_processor_cached_at: float | None = None
_processor_lock = threading.Lock()


def _is_cache_expired() -> bool:
    """Check whether the cached processor has exceeded its TTL."""
    if _processor_cached_at is None:
        return False
    ttl = get_setting("CACHE_TTL")
    if ttl is None:
        return False
    return (time.monotonic() - _processor_cached_at) >= ttl


def _filter_paths(schema: dict) -> dict:
    """Filter schema paths by SCHEMA_PATH_PREFIX and EXCLUDE_PATHS settings."""
    prefix = get_setting("SCHEMA_PATH_PREFIX")
    exclude = get_setting("EXCLUDE_PATHS")
    paths = schema.get("paths", {})
    if not prefix and not exclude:
        return schema
    filtered = {}
    for path, data in paths.items():
        if prefix and not path.startswith(prefix):
            continue
        if any(path.startswith(ep) for ep in exclude):
            continue
        filtered[path] = data
    logger.debug("Path filtering: %d -> %d paths", len(paths), len(filtered))
    return {**schema, "paths": filtered}


def get_processor() -> SchemaProcessor:
    """Get the schema processor, creating and caching it as needed."""
    global _processor, _processor_cached_at
    cache = get_setting("CACHE_SCHEMA")
    if _processor is not None and cache and not _is_cache_expired():
        logger.debug(
            "Schema processor cache hit (age: %.1fs)",
            time.monotonic() - _processor_cached_at,
        )
        return _processor
    with _processor_lock:
        if _processor is not None and cache and not _is_cache_expired():
            logger.debug(
                "Schema processor cache hit (age: %.1fs)",
                time.monotonic() - _processor_cached_at,
            )
            return _processor

        if _processor is not None and _is_cache_expired():
            logger.debug(
                "Schema processor cache expired (age: %.1fs, TTL: %s)",
                time.monotonic() - _processor_cached_at,
                get_setting("CACHE_TTL"),
            )
        elif _processor is None:
            logger.debug("Schema processor cache miss, building")
        else:
            logger.debug("Schema caching disabled, rebuilding")

        t0 = time.monotonic()
        adapter = get_adapter()
        openapi_schema = _filter_paths(adapter.get_schema())
        _processor = SchemaProcessor(openapi_schema)
        _processor_cached_at = time.monotonic()
        elapsed = _processor_cached_at - t0
        path_count = len(openapi_schema.get("paths", {}))
        schema_count = len(openapi_schema.get("components", {}).get("schemas", {}))
        logger.info(
            "Schema processor built in %.3fs (%d paths, %d schemas)",
            elapsed,
            path_count,
            schema_count,
        )
        return _processor


def invalidate_schema_cache() -> None:
    """Force-clear the cached schema processor.

    The next call to ``get_processor()`` will rebuild the processor from
    scratch.  This is safe to call from any thread (e.g., a Django signal
    handler or management command).
    """
    global _processor, _processor_cached_at
    with _processor_lock:
        _processor = None
        _processor_cached_at = None
    logger.info("Schema cache invalidated")


def create_mcp_server() -> FastMCP:
    """Create and configure the MCP server with resources and tools."""
    name = get_setting("SERVER_NAME")
    instructions = get_setting("SERVER_INSTRUCTIONS")

    logger.info("Creating MCP server '%s'", name)

    mcp = FastMCP(
        name=name,
        instructions=instructions
        or (
            "This server provides API documentation for a Django REST Framework project.\n"
            "\n"
            "## Recommended workflow\n"
            "1. Start with the `api://overview` resource to understand the API "
            "(title, version, base URL, auth methods, endpoint count).\n"
            "2. Browse `api://endpoints` to list all endpoints, or call "
            "`search_endpoints` to find endpoints by keyword, HTTP method, or tag.\n"
            "3. Get full details for a specific endpoint with `get_endpoint_detail` "
            "or the `api://endpoints/{method}/{path}` resource.\n"
            "4. Use `get_request_example` and `get_response_example` "
            "to see example request/response payloads.\n"
            "5. Generate ready-to-use integration code with `generate_code_snippet` "
            "(supports javascript/typescript/python with fetch/axios/ky/requests/httpx).\n"
            "6. Check `api://auth` for authentication requirements.\n"
            "\n"
            "## Additional resources\n"
            "- `api://schemas` lists all data model schemas\n"
            "- `api://schemas/{name}` returns a full schema definition\n"
            "- `list_schemas` and `get_schema_detail` tools provide programmatic schema access"
        ),
    )

    from drf_mcp_docs.server.resources import register_resources
    from drf_mcp_docs.server.tools import register_tools

    register_resources(mcp)
    register_tools(mcp)

    return mcp
