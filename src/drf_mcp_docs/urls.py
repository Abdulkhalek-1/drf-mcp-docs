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
    session_manager = mcp.session_manager

    # Session manager lifecycle state (shared via closure)
    _ready = asyncio.Event()
    _shutdown = asyncio.Event()
    _failed = False
    _mcp_task = None
    _init_lock = asyncio.Lock()

    async def _ensure_session_manager_running():
        """Start the MCP session manager if not already running.

        This is called both from the lifespan handler (normal ASGI servers)
        and before MCP HTTP requests (fallback for servers like Daphne that
        do not send lifespan events).
        """
        nonlocal _failed, _mcp_task

        if _ready.is_set():
            return

        async with _init_lock:
            if _ready.is_set():
                return

            async def _run():
                nonlocal _failed
                try:
                    async with session_manager.run():
                        logger.debug("MCP session manager started")
                        _ready.set()
                        await _shutdown.wait()
                except Exception:
                    logger.exception("MCP session manager failed to start")
                    _failed = True
                    _ready.set()

            _mcp_task = asyncio.create_task(_run())
            await _ready.wait()

    async def _handle_lifespan(scope, receive, send):
        """Handle lifespan events for the MCP app."""
        await _ensure_session_manager_running()

        if _failed:
            await send({"type": "lifespan.startup.failed", "message": "MCP server failed to start"})
            return

        await send({"type": "lifespan.startup.complete"})

        # Wait for shutdown signal from the ASGI server
        while True:
            message = await receive()
            if message["type"] == "lifespan.shutdown":
                break

        # Signal MCP to shut down gracefully, then cancel if it doesn't exit
        _shutdown.set()
        if _mcp_task is not None:
            try:
                await asyncio.wait_for(asyncio.shield(_mcp_task), timeout=5.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                _mcp_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await _mcp_task

        logger.debug("MCP lifespan shutdown complete")
        await send({"type": "lifespan.shutdown.complete"})

    async def asgi_app(scope, receive, send):
        scope_type = scope["type"]
        if scope_type == "http" and scope["path"].startswith(mcp_path.rstrip("/")):
            await _ensure_session_manager_running()
            logger.debug("Routing request to MCP: %s", scope["path"])
            await mcp_app(scope, receive, send)
        elif scope_type == "lifespan":
            await _handle_lifespan(scope, receive, send)
        else:
            await django_app(scope, receive, send)

    return asgi_app
