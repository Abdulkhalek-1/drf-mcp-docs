"""Integration tests: real MCP client <-> real MCP server over streamable HTTP.

These tests boot a uvicorn server in a background thread, connect the MCP SDK's
streamable_http_client + ClientSession, and exercise tools/resources over the wire.
This catches transport-level issues that unit tests with mocked processors cannot detect.
"""

from __future__ import annotations

import json
import socket
import threading
import time

import pytest
import uvicorn
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client

import drf_mcp_docs.server as server_module
import drf_mcp_docs.server.instance as instance_module

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_free_port() -> int:
    """Bind to port 0 and return the OS-assigned free port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


async def _connect(url: str):
    """Connect an MCP client and return an initialized session context.

    Returns an async context manager that yields a ClientSession.
    The caller must use ``async with _connect(url) as session:``.
    """
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _session():
        async with streamable_http_client(url) as (read, write, _), ClientSession(read, write) as session:
            await session.initialize()
            yield session

    return _session()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _mcp_test_settings(settings):
    """Configure Django settings for the MCP integration test."""
    settings.DRF_MCP_DOCS = {
        "SCHEMA_ADAPTER": "drf_mcp_docs.adapters.drf.DRFBuiltinAdapter",
        "SCHEMA_PATH_PREFIX": "/api/",
        "EXCLUDE_PATHS": [],
        "CACHE_SCHEMA": False,
        "MCP_ENDPOINT": "/mcp/",
    }
    settings.REST_FRAMEWORK = {
        "DEFAULT_SCHEMA_CLASS": "rest_framework.schemas.openapi.AutoSchema",
    }


@pytest.fixture(autouse=True)
def _reset_singletons():
    """Clear cached MCP server and schema processor singletons."""
    server_module._server = None
    instance_module._processor = None
    instance_module._processor_cached_at = None
    yield
    server_module._server = None
    instance_module._processor = None
    instance_module._processor_cached_at = None


@pytest.fixture()
def mcp_server_url():
    """Start a uvicorn server with the MCP ASGI app, yield its URL, then shut down."""
    from django.core.asgi import get_asgi_application

    from drf_mcp_docs.urls import mount_mcp

    django_app = get_asgi_application()
    asgi_app = mount_mcp(django_app)

    port = _find_free_port()
    config = uvicorn.Config(
        app=asgi_app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
    )
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    # Wait for server to be ready
    deadline = time.monotonic() + 10.0
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.05)
    if not server.started:
        raise RuntimeError("Uvicorn server did not start within 10 seconds")

    yield f"http://127.0.0.1:{port}/mcp"

    server.should_exit = True
    thread.join(timeout=5.0)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestMCPIntegration:
    """End-to-end tests exercising the MCP protocol over real HTTP."""

    async def test_list_tools(self, mcp_server_url):
        async with await _connect(mcp_server_url) as session:
            result = await session.list_tools()
            tool_names = {t.name for t in result.tools}
            expected = {
                "search_endpoints",
                "get_endpoint_detail",
                "get_request_example",
                "get_response_example",
                "generate_code_snippet",
                "list_schemas",
                "get_schema_detail",
            }
            assert expected <= tool_names

    async def test_list_resources(self, mcp_server_url):
        async with await _connect(mcp_server_url) as session:
            result = await session.list_resources()
            uris = {str(r.uri) for r in result.resources}
            for expected_uri in ["api://overview", "api://endpoints", "api://schemas", "api://auth"]:
                assert expected_uri in uris

    async def test_list_resource_templates(self, mcp_server_url):
        async with await _connect(mcp_server_url) as session:
            result = await session.list_resource_templates()
            uris = {str(t.uriTemplate) for t in result.resourceTemplates}
            assert "api://endpoints/{method}/{path}" in uris
            assert "api://schemas/{name}" in uris

    async def test_read_resource_overview(self, mcp_server_url):
        async with await _connect(mcp_server_url) as session:
            result = await session.read_resource("api://overview")
            data = json.loads(result.contents[0].text)
            assert "title" in data
            assert data["endpoint_count"] > 0

    async def test_read_resource_endpoints(self, mcp_server_url):
        async with await _connect(mcp_server_url) as session:
            result = await session.read_resource("api://endpoints")
            data = json.loads(result.contents[0].text)
            assert isinstance(data, list)
            assert len(data) > 0
            assert any("products" in ep["path"] for ep in data)

    async def test_call_tool_search_endpoints(self, mcp_server_url):
        async with await _connect(mcp_server_url) as session:
            result = await session.call_tool("search_endpoints", {"query": "product"})
            data = json.loads(result.content[0].text)
            assert isinstance(data, list)
            assert len(data) > 0
            assert any("products" in ep["path"] for ep in data)

    async def test_call_tool_generate_code_snippet(self, mcp_server_url):
        async with await _connect(mcp_server_url) as session:
            # Discover a real endpoint first
            search = await session.call_tool("search_endpoints", {"query": "product"})
            endpoints = json.loads(search.content[0].text)
            ep = next(e for e in endpoints if e["method"] == "GET")

            result = await session.call_tool(
                "generate_code_snippet",
                {
                    "path": ep["path"],
                    "method": "GET",
                    "language": "javascript",
                    "client": "fetch",
                },
            )
            data = json.loads(result.content[0].text)
            assert "code" in data
            assert "fetch" in data["code"]

    async def test_call_tool_get_endpoint_detail(self, mcp_server_url):
        async with await _connect(mcp_server_url) as session:
            search = await session.call_tool("search_endpoints", {"query": "product"})
            endpoints = json.loads(search.content[0].text)
            ep = next(e for e in endpoints if e["method"] == "GET")

            result = await session.call_tool(
                "get_endpoint_detail",
                {"path": ep["path"], "method": ep["method"]},
            )
            data = json.loads(result.content[0].text)
            assert "error" not in data
            assert "path" in data

    async def test_call_tool_search_no_results(self, mcp_server_url):
        async with await _connect(mcp_server_url) as session:
            result = await session.call_tool("search_endpoints", {"query": "zzz_nonexistent_xyz"})
            data = json.loads(result.content[0].text)
            assert "message" in data
