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

from typing import TYPE_CHECKING

from drf_mcp_docs.settings import get_setting

if TYPE_CHECKING:
    pass

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

    mcp_app = mcp.streamable_http_app()

    async def asgi_app(scope, receive, send):
        if scope["type"] == "http" and scope["path"].startswith(mcp_path):
            # Strip the prefix for the MCP app
            scope = dict(scope)
            scope["path"] = scope["path"][len(mcp_path.rstrip("/")) :] or "/"
            scope["root_path"] = scope.get("root_path", "") + mcp_path.rstrip("/")
            await mcp_app(scope, receive, send)
        else:
            await django_app(scope, receive, send)

    return asgi_app
