from __future__ import annotations

import threading

from mcp.server.fastmcp import FastMCP

from drf_mcp_docs.adapters import get_adapter
from drf_mcp_docs.schema.processor import SchemaProcessor
from drf_mcp_docs.settings import get_setting

_processor: SchemaProcessor | None = None
_processor_lock = threading.Lock()


def get_processor() -> SchemaProcessor:
    """Get the schema processor, creating and caching it as needed."""
    global _processor
    cache = get_setting("CACHE_SCHEMA")
    if _processor is not None and cache:
        return _processor
    with _processor_lock:
        if _processor is not None and cache:
            return _processor
        adapter = get_adapter()
        openapi_schema = adapter.get_schema()
        _processor = SchemaProcessor(openapi_schema)
        return _processor


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
