"""URL configuration for drf-mcp-docs.

For streamable-http transport, mount the MCP server in your ASGI application
rather than using Django URL patterns:

    # asgi.py
    from django.core.asgi import get_asgi_application
    from drf_mcp_docs.urls import mount_mcp

    django_app = get_asgi_application()
    application = mount_mcp(django_app)
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import TYPE_CHECKING

from drf_mcp_docs.settings import get_setting

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Empty URL patterns - MCP uses its own ASGI app
urlpatterns = []


def mount_mcp(django_app, mcp=None, path: str | None = None):
    """Mount the MCP server alongside a Django ASGI application.

    Args:
        django_app: The Django ASGI application.
        mcp: Optional FastMCP server instance. If None, uses get_mcp_server().
        path: URL path prefix for MCP endpoint. Defaults to settings.

    Returns:
        An ASGI application that routes MCP requests to the MCP server
        and everything else to Django.
    """
    if mcp is None:
        from drf_mcp_docs.server import get_mcp_server

        mcp = get_mcp_server()

    mcp_path = path or get_setting("MCP_ENDPOINT")
    if not mcp_path.startswith("/"):
        mcp_path = "/" + mcp_path

    logger.info("Mounting MCP server at '%s'", mcp_path)

    # Align the MCP SDK's internal route with the mount path
    mcp.settings.streamable_http_path = mcp_path.rstrip("/") or "/"

    mcp_app = mcp.streamable_http_app()

    async def _handle_lifespan(scope, receive, send):
        """Handle lifespan events for the MCP app."""
        startup_complete = asyncio.Event()
        shutdown_event = asyncio.Event()
        mcp_failed = asyncio.Event()
        first_receive = True

        async def mcp_lifespan():
            nonlocal first_receive

            async def mcp_receive():
                nonlocal first_receive
                if first_receive:
                    first_receive = False
                    return {"type": "lifespan.startup"}
                # Block until shutdown is signaled
                await shutdown_event.wait()
                return {"type": "lifespan.shutdown"}

            async def mcp_send(message):
                if message["type"] == "lifespan.startup.complete":
                    logger.debug("MCP lifespan startup complete")
                    startup_complete.set()
                elif message["type"] == "lifespan.startup.failed":
                    logger.warning("MCP lifespan startup failed")
                    mcp_failed.set()
                    startup_complete.set()

            try:
                await mcp_app(scope, mcp_receive, mcp_send)
            except asyncio.CancelledError:
                pass
            except Exception:
                if not startup_complete.is_set():
                    mcp_failed.set()
                    startup_complete.set()

        mcp_task = asyncio.create_task(mcp_lifespan())
        await startup_complete.wait()

        if mcp_failed.is_set():
            await send({"type": "lifespan.startup.failed", "message": "MCP server failed to start"})
            return

        await send({"type": "lifespan.startup.complete"})

        # Wait for shutdown signal from uvicorn
        while True:
            message = await receive()
            if message["type"] == "lifespan.shutdown":
                break

        # Signal MCP to shut down gracefully, then cancel if it doesn't exit
        shutdown_event.set()
        try:
            await asyncio.wait_for(asyncio.shield(mcp_task), timeout=5.0)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            mcp_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await mcp_task

        logger.debug("MCP lifespan shutdown complete")
        await send({"type": "lifespan.shutdown.complete"})

    async def asgi_app(scope, receive, send):
        scope_type = scope["type"]
        if scope_type == "http" and scope["path"].startswith(mcp_path.rstrip("/")):
            logger.debug("Routing request to MCP: %s", scope["path"])
            await mcp_app(scope, receive, send)
        elif scope_type == "lifespan":
            await _handle_lifespan(scope, receive, send)
        else:
            await django_app(scope, receive, send)

    return asgi_app
