from __future__ import annotations

import threading
import time

from mcp.server.fastmcp import FastMCP

from drf_mcp_docs.adapters import get_adapter
from drf_mcp_docs.schema.processor import SchemaProcessor
from drf_mcp_docs.settings import get_setting

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
    return {**schema, "paths": filtered}


def get_processor() -> SchemaProcessor:
    """Get the schema processor, creating and caching it as needed."""
    global _processor, _processor_cached_at
    cache = get_setting("CACHE_SCHEMA")
    if _processor is not None and cache and not _is_cache_expired():
        return _processor
    with _processor_lock:
        if _processor is not None and cache and not _is_cache_expired():
            return _processor
        adapter = get_adapter()
        openapi_schema = _filter_paths(adapter.get_schema())
        _processor = SchemaProcessor(openapi_schema)
        _processor_cached_at = time.monotonic()
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


def create_mcp_server() -> FastMCP:
    """Create and configure the MCP server with resources and tools."""
    name = get_setting("SERVER_NAME")
    instructions = get_setting("SERVER_INSTRUCTIONS")

    mcp = FastMCP(
        name=name,
        instructions=instructions
        or (
            "This server provides API documentation for a Django REST Framework project. "
            "Use resources to browse the API structure and tools to search, get details, "
            "and generate code snippets for frontend integration."
        ),
    )

    from drf_mcp_docs.server.resources import register_resources
    from drf_mcp_docs.server.tools import register_tools

    register_resources(mcp)
    register_tools(mcp)

    return mcp
