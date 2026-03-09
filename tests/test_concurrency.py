from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import pytest


class TestThreadSafety:
    @pytest.fixture(autouse=True)
    def reset_globals(self):
        """Reset global singletons before each test."""
        import drf_mcp_docs.server as server_mod
        import drf_mcp_docs.server.instance as instance_mod

        server_mod._server = None
        instance_mod._processor = None
        yield
        server_mod._server = None
        instance_mod._processor = None

    @patch("drf_mcp_docs.server.instance.get_adapter")
    @patch("drf_mcp_docs.server.instance.get_setting", return_value=True)
    def test_get_processor_thread_safe(self, mock_setting, mock_adapter):
        mock_adapter.return_value.get_schema.return_value = {
            "info": {"title": "Test", "version": "1.0"},
            "paths": {},
        }
        from drf_mcp_docs.server.instance import get_processor

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(get_processor) for _ in range(10)]
            results = [f.result() for f in futures]

        # All threads should get the same instance
        assert all(r is results[0] for r in results)

    def test_get_mcp_server_thread_safe(self):
        from drf_mcp_docs.server import get_mcp_server

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(get_mcp_server) for _ in range(10)]
            results = [f.result() for f in futures]

        assert all(r is results[0] for r in results)
