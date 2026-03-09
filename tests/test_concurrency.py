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
        instance_mod._processor_cached_at = None
        yield
        server_mod._server = None
        instance_mod._processor = None
        instance_mod._processor_cached_at = None

    @patch("drf_mcp_docs.server.instance.get_adapter")
    @patch(
        "drf_mcp_docs.server.instance.get_setting",
        side_effect=lambda name: {
            "CACHE_SCHEMA": True,
            "CACHE_TTL": None,
            "SCHEMA_PATH_PREFIX": "",
            "EXCLUDE_PATHS": [],
        }.get(name),
    )
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

    @patch("drf_mcp_docs.server.instance.get_adapter")
    @patch(
        "drf_mcp_docs.server.instance.get_setting",
        side_effect=lambda name: {
            "CACHE_SCHEMA": True,
            "CACHE_TTL": None,
            "SCHEMA_PATH_PREFIX": "",
            "EXCLUDE_PATHS": [],
        }.get(name),
    )
    def test_invalidate_during_concurrent_reads(self, mock_setting, mock_adapter):
        """Invalidation while threads call get_processor() must not crash."""
        mock_adapter.return_value.get_schema.return_value = {
            "info": {"title": "Test", "version": "1.0"},
            "paths": {},
        }
        from drf_mcp_docs.server.instance import (
            get_processor,
            invalidate_schema_cache,
        )

        # Pre-populate the cache
        get_processor()

        errors = []

        def worker():
            try:
                for _ in range(50):
                    get_processor()
                    invalidate_schema_cache()
                    get_processor()
            except Exception as e:
                errors.append(e)

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(worker) for _ in range(5)]
            for f in futures:
                f.result()

        assert errors == [], f"Errors during concurrent access: {errors}"

    def test_get_mcp_server_thread_safe(self):
        from drf_mcp_docs.server import get_mcp_server

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(get_mcp_server) for _ in range(10)]
            results = [f.result() for f in futures]

        assert all(r is results[0] for r in results)
