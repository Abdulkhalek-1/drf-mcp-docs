from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from drf_mcp_docs.urls import mount_mcp


class TestMountMcp:
    def test_returns_asgi_app(self):
        django_app = AsyncMock()
        mock_mcp = MagicMock()
        mock_mcp.streamable_http_app.return_value = AsyncMock()

        app = mount_mcp(django_app, mcp=mock_mcp)

        assert callable(app)

    def test_uses_default_mcp_server_when_none(self):
        django_app = AsyncMock()

        with patch("drf_mcp_docs.server.get_mcp_server") as mock_get_server:
            mock_server = MagicMock()
            mock_server.streamable_http_app.return_value = AsyncMock()
            mock_get_server.return_value = mock_server

            mount_mcp(django_app)

            mock_get_server.assert_called_once()

    @pytest.mark.asyncio
    async def test_routes_mcp_path_to_mcp_app(self):
        django_app = AsyncMock()
        mcp_app = AsyncMock()
        mock_mcp = MagicMock()
        mock_mcp.streamable_http_app.return_value = mcp_app

        app = mount_mcp(django_app, mcp=mock_mcp, path="/mcp/")

        scope = {"type": "http", "path": "/mcp/messages", "root_path": ""}
        receive = AsyncMock()
        send = AsyncMock()

        await app(scope, receive, send)

        mcp_app.assert_awaited_once()
        django_app.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_routes_non_mcp_path_to_django(self):
        django_app = AsyncMock()
        mcp_app = AsyncMock()
        mock_mcp = MagicMock()
        mock_mcp.streamable_http_app.return_value = mcp_app

        app = mount_mcp(django_app, mcp=mock_mcp, path="/mcp/")

        scope = {"type": "http", "path": "/api/products/", "root_path": ""}
        receive = AsyncMock()
        send = AsyncMock()

        await app(scope, receive, send)

        django_app.assert_awaited_once()
        mcp_app.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_strips_mcp_prefix_for_mcp_app(self):
        django_app = AsyncMock()
        mcp_app = AsyncMock()
        mock_mcp = MagicMock()
        mock_mcp.streamable_http_app.return_value = mcp_app

        app = mount_mcp(django_app, mcp=mock_mcp, path="/mcp/")

        scope = {"type": "http", "path": "/mcp/messages", "root_path": ""}
        receive = AsyncMock()
        send = AsyncMock()

        await app(scope, receive, send)

        called_scope = mcp_app.call_args[0][0]
        assert called_scope["path"] == "/messages"
        assert called_scope["root_path"] == "/mcp"

    @pytest.mark.asyncio
    async def test_custom_path(self):
        django_app = AsyncMock()
        mcp_app = AsyncMock()
        mock_mcp = MagicMock()
        mock_mcp.streamable_http_app.return_value = mcp_app

        app = mount_mcp(django_app, mcp=mock_mcp, path="/api-docs-mcp/")

        scope = {"type": "http", "path": "/api-docs-mcp/sse", "root_path": ""}
        receive = AsyncMock()
        send = AsyncMock()

        await app(scope, receive, send)

        mcp_app.assert_awaited_once()
        django_app.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_non_http_scope_goes_to_django(self):
        django_app = AsyncMock()
        mcp_app = AsyncMock()
        mock_mcp = MagicMock()
        mock_mcp.streamable_http_app.return_value = mcp_app

        app = mount_mcp(django_app, mcp=mock_mcp, path="/mcp/")

        scope = {"type": "websocket", "path": "/mcp/ws"}
        receive = AsyncMock()
        send = AsyncMock()

        await app(scope, receive, send)

        django_app.assert_awaited_once()
        mcp_app.assert_not_awaited()

    def test_path_without_leading_slash(self):
        django_app = AsyncMock()
        mock_mcp = MagicMock()
        mock_mcp.streamable_http_app.return_value = AsyncMock()

        # Should not raise — it adds the leading slash
        app = mount_mcp(django_app, mcp=mock_mcp, path="mcp/")

        assert callable(app)
