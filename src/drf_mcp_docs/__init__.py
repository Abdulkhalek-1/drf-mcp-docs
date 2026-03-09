"""drf-mcp-docs: Expose DRF API documentation via MCP for AI coding agents."""

__version__ = "0.1.1"

from drf_mcp_docs.server.instance import invalidate_schema_cache

__all__ = ["invalidate_schema_cache"]
