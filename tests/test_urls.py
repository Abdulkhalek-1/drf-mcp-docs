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
    async def test_forwards_full_path_to_mcp_app(self):
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
        assert called_scope["path"] == "/mcp/messages"

    @pytest.mark.asyncio
    async def test_custom_path(self):
        django_app = AsyncMock()
        mcp_app = AsyncMock()
        mock_mcp = MagicMock()
        mock_mcp.streamable_http_app.return_value = mcp_app

        app = mount_mcp(django_app, mcp=mock_mcp, path="/api-docs-mcp/")

        # Verify the internal streamable_http_path is aligned with mount path
        assert mock_mcp.settings.streamable_http_path == "/api-docs-mcp"

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

    @pytest.mark.asyncio
    async def test_lifespan_initializes_mcp(self):
        import asyncio

        django_app = AsyncMock()
        mcp_started = False
        mcp_shutdown = False

        async def fake_mcp_app(scope, receive, send):
            nonlocal mcp_started, mcp_shutdown
            # Simulate Starlette lifespan protocol
            msg = await receive()
            assert msg["type"] == "lifespan.startup"
            await send({"type": "lifespan.startup.complete"})
            mcp_started = True
            # Wait for shutdown signal
            msg = await receive()
            assert msg["type"] == "lifespan.shutdown"
            mcp_shutdown = True
            await send({"type": "lifespan.shutdown.complete"})

        mock_mcp = MagicMock()
        mock_mcp.streamable_http_app.return_value = fake_mcp_app

        app = mount_mcp(django_app, mcp=mock_mcp, path="/mcp/")

        scope = {"type": "lifespan"}
        call_count = 0

        async def receive():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {"type": "lifespan.startup"}
            await asyncio.sleep(0.05)
            return {"type": "lifespan.shutdown"}

        sent_messages = []

        async def send(message):
            sent_messages.append(message["type"])

        await asyncio.wait_for(app(scope, receive, send), timeout=5.0)

        assert mcp_started
        assert mcp_shutdown
        assert "lifespan.startup.complete" in sent_messages
        assert "lifespan.shutdown.complete" in sent_messages

    def test_path_without_leading_slash(self):
        django_app = AsyncMock()
        mock_mcp = MagicMock()
        mock_mcp.streamable_http_app.return_value = AsyncMock()

        # Should not raise — it adds the leading slash
        app = mount_mcp(django_app, mcp=mock_mcp, path="mcp/")

        assert callable(app)
