from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

_server: FastMCP | None = None
_server_lock = threading.Lock()


def get_mcp_server() -> FastMCP:
    """Get or create the singleton MCP server instance."""
    global _server
    if _server is None:
        with _server_lock:
            if _server is None:
                logger.info("Initializing MCP server singleton")
                from drf_mcp_docs.server.instance import create_mcp_server

                _server = create_mcp_server()
    else:
        logger.debug("Returning cached MCP server")
    return _server


from drf_mcp_docs.server.instance import invalidate_schema_cache  # noqa: E402, F401
