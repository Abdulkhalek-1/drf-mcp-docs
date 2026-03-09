from __future__ import annotations

import asyncio
import contextlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from drf_mcp_docs.urls import mount_mcp


@contextlib.asynccontextmanager
async def _fake_run():
    yield


def _make_mock_mcp(mcp_app=None):
    """Create a mock MCP server with a properly mocked session manager."""
    mock = MagicMock()
    mock.streamable_http_app.return_value = mcp_app or AsyncMock()
    mock.session_manager.run = _fake_run
    return mock


class TestMountMcp:
    def test_returns_asgi_app(self):
        django_app = AsyncMock()
        mock_mcp = _make_mock_mcp()

        app = mount_mcp(django_app, mcp=mock_mcp)

        assert callable(app)

    def test_uses_default_mcp_server_when_none(self):
        django_app = AsyncMock()

        with patch("drf_mcp_docs.server.get_mcp_server") as mock_get_server:
            mock_server = _make_mock_mcp()
            mock_get_server.return_value = mock_server

            mount_mcp(django_app)

            mock_get_server.assert_called_once()

    @pytest.mark.asyncio
    async def test_routes_mcp_path_to_mcp_app(self):
        django_app = AsyncMock()
        mcp_app = AsyncMock()
        mock_mcp = _make_mock_mcp(mcp_app)

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
        mock_mcp = _make_mock_mcp(mcp_app)

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
        mock_mcp = _make_mock_mcp(mcp_app)

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
        mock_mcp = _make_mock_mcp(mcp_app)

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
        mock_mcp = _make_mock_mcp(mcp_app)

        app = mount_mcp(django_app, mcp=mock_mcp, path="/mcp/")

        scope = {"type": "websocket", "path": "/mcp/ws"}
        receive = AsyncMock()
        send = AsyncMock()

        await app(scope, receive, send)

        django_app.assert_awaited_once()
        mcp_app.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_lifespan_initializes_mcp(self):
        django_app = AsyncMock()
        run_entered = False
        run_exited = False

        @contextlib.asynccontextmanager
        async def fake_run():
            nonlocal run_entered, run_exited
            run_entered = True
            try:
                yield
            finally:
                run_exited = True

        mock_mcp = MagicMock()
        mock_mcp.streamable_http_app.return_value = AsyncMock()
        mock_mcp.session_manager.run = fake_run

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

        assert run_entered
        assert run_exited
        assert "lifespan.startup.complete" in sent_messages
        assert "lifespan.shutdown.complete" in sent_messages

    @pytest.mark.asyncio
    async def test_mcp_works_without_lifespan(self):
        """HTTP requests work without prior lifespan events (Daphne scenario)."""
        django_app = AsyncMock()
        run_entered = False

        @contextlib.asynccontextmanager
        async def fake_run():
            nonlocal run_entered
            run_entered = True
            yield

        mcp_app_handler = AsyncMock()
        mock_mcp = MagicMock()
        mock_mcp.streamable_http_app.return_value = mcp_app_handler
        mock_mcp.session_manager.run = fake_run

        app = mount_mcp(django_app, mcp=mock_mcp, path="/mcp/")

        scope = {"type": "http", "path": "/mcp/messages", "root_path": ""}
        receive = AsyncMock()
        send = AsyncMock()

        await app(scope, receive, send)

        assert run_entered
        mcp_app_handler.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_concurrent_requests_start_session_once(self):
        """Multiple simultaneous requests should only call run() once."""
        django_app = AsyncMock()
        run_count = 0

        @contextlib.asynccontextmanager
        async def fake_run():
            nonlocal run_count
            run_count += 1
            yield

        mcp_app_handler = AsyncMock()
        mock_mcp = MagicMock()
        mock_mcp.streamable_http_app.return_value = mcp_app_handler
        mock_mcp.session_manager.run = fake_run

        app = mount_mcp(django_app, mcp=mock_mcp, path="/mcp/")

        scope = {"type": "http", "path": "/mcp/messages", "root_path": ""}

        tasks = [asyncio.create_task(app(scope, AsyncMock(), AsyncMock())) for _ in range(10)]
        await asyncio.gather(*tasks)

        assert run_count == 1
        assert mcp_app_handler.await_count == 10

    @pytest.mark.asyncio
    async def test_lifespan_startup_failure(self):
        """Lifespan reports failure when session manager fails to start."""
        django_app = AsyncMock()

        @contextlib.asynccontextmanager
        async def failing_run():
            raise RuntimeError("boom")
            yield  # noqa: unreachable

        mock_mcp = MagicMock()
        mock_mcp.streamable_http_app.return_value = AsyncMock()
        mock_mcp.session_manager.run = failing_run

        app = mount_mcp(django_app, mcp=mock_mcp, path="/mcp/")

        scope = {"type": "lifespan"}
        call_count = 0

        async def receive():
            nonlocal call_count
            call_count += 1
            return {"type": "lifespan.startup"}

        sent_messages = []

        async def send(message):
            sent_messages.append(message)

        await asyncio.wait_for(app(scope, receive, send), timeout=5.0)

        assert sent_messages[0]["type"] == "lifespan.startup.failed"

    def test_path_without_leading_slash(self):
        django_app = AsyncMock()
        mock_mcp = _make_mock_mcp()

        # Should not raise — it adds the leading slash
        app = mount_mcp(django_app, mcp=mock_mcp, path="mcp/")

        assert callable(app)
