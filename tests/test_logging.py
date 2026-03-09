"""Tests for structured debug logging throughout the pipeline."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import SAMPLE_OPENAPI_SCHEMA


class TestAdapterSelectionLogging:
    """Verify adapter selection logs at correct levels."""

    def test_auto_detection_logs_probing(self, caplog):
        from drf_mcp_docs.adapters import get_adapter

        with caplog.at_level(logging.DEBUG, logger="drf_mcp_docs.adapters"):
            get_adapter()
        assert "Probing adapter" in caplog.text
        assert "Auto-detected adapter" in caplog.text

    def test_override_adapter_logs_info(self, caplog, settings):
        settings.DRF_MCP_DOCS = {
            "SCHEMA_ADAPTER": "drf_mcp_docs.adapters.spectacular.SpectacularAdapter",
        }
        from drf_mcp_docs.adapters import get_adapter

        with caplog.at_level(logging.INFO, logger="drf_mcp_docs.adapters"):
            get_adapter()
        assert "adapter override" in caplog.text

    def test_bad_override_logs_error(self, caplog, settings):
        settings.DRF_MCP_DOCS = {
            "SCHEMA_ADAPTER": "nonexistent.module.Adapter",
        }
        from drf_mcp_docs.adapters import get_adapter

        with (
            caplog.at_level(logging.ERROR, logger="drf_mcp_docs.adapters"),
            pytest.raises(ImportError),
        ):
            get_adapter()
        assert "Failed to import" in caplog.text

    def test_bad_class_logs_error(self, caplog, settings):
        settings.DRF_MCP_DOCS = {
            "SCHEMA_ADAPTER": "drf_mcp_docs.adapters.drf.NonexistentClass",
        }
        from drf_mcp_docs.adapters import get_adapter

        with (
            caplog.at_level(logging.ERROR, logger="drf_mcp_docs.adapters"),
            pytest.raises(ImportError),
        ):
            get_adapter()
        assert "not found" in caplog.text


class TestProcessorCacheLogging:
    """Verify cache hit/miss/expiry logs."""

    @pytest.fixture(autouse=True)
    def _reset_processor(self):
        import drf_mcp_docs.server.instance as inst

        old_processor = inst._processor
        old_cached_at = inst._processor_cached_at
        inst._processor = None
        inst._processor_cached_at = None
        yield
        inst._processor = old_processor
        inst._processor_cached_at = old_cached_at

    def test_cache_miss_logs(self, caplog):
        with patch("drf_mcp_docs.server.instance.get_adapter") as mock_adapter:
            mock_adapter.return_value.get_schema.return_value = SAMPLE_OPENAPI_SCHEMA
            with caplog.at_level(logging.DEBUG, logger="drf_mcp_docs.server.instance"):
                from drf_mcp_docs.server.instance import get_processor

                get_processor()
        assert "cache miss" in caplog.text

    def test_cache_hit_logs(self, caplog, settings):
        settings.DRF_MCP_DOCS = {"CACHE_SCHEMA": True}
        with patch("drf_mcp_docs.server.instance.get_adapter") as mock_adapter:
            mock_adapter.return_value.get_schema.return_value = SAMPLE_OPENAPI_SCHEMA
            from drf_mcp_docs.server.instance import get_processor

            get_processor()  # populate cache
            with caplog.at_level(logging.DEBUG, logger="drf_mcp_docs.server.instance"):
                get_processor()  # should be cache hit
        assert "cache hit" in caplog.text

    def test_build_timing_logs(self, caplog):
        with patch("drf_mcp_docs.server.instance.get_adapter") as mock_adapter:
            mock_adapter.return_value.get_schema.return_value = SAMPLE_OPENAPI_SCHEMA
            with caplog.at_level(logging.INFO, logger="drf_mcp_docs.server.instance"):
                from drf_mcp_docs.server.instance import get_processor

                get_processor()
        assert "Schema processor built in" in caplog.text
        assert "paths" in caplog.text

    def test_cache_invalidation_logs(self, caplog):
        with caplog.at_level(logging.INFO, logger="drf_mcp_docs.server.instance"):
            from drf_mcp_docs.server.instance import invalidate_schema_cache

            invalidate_schema_cache()
        assert "invalidated" in caplog.text

    def test_path_filtering_logs(self, caplog):
        schema = {**SAMPLE_OPENAPI_SCHEMA}
        with caplog.at_level(logging.DEBUG, logger="drf_mcp_docs.server.instance"):
            from drf_mcp_docs.server.instance import _filter_paths

            _filter_paths(schema)
        assert "Path filtering" in caplog.text


class TestToolInvocationLogging:
    """Verify tool calls emit DEBUG logs with args."""

    @pytest.fixture(autouse=True)
    def _mock_processor(self):
        from drf_mcp_docs.schema.processor import SchemaProcessor

        processor = SchemaProcessor(SAMPLE_OPENAPI_SCHEMA)
        with patch("drf_mcp_docs.server.tools.get_processor", return_value=processor):
            yield

    def test_search_endpoints_logs(self, caplog):
        from drf_mcp_docs.server import tools

        with caplog.at_level(logging.DEBUG, logger="drf_mcp_docs.server.tools"):
            tools.search_endpoints("product")
        assert "search_endpoints" in caplog.text
        assert "product" in caplog.text

    def test_search_endpoints_result_count(self, caplog):
        from drf_mcp_docs.server import tools

        with caplog.at_level(logging.DEBUG, logger="drf_mcp_docs.server.tools"):
            tools.search_endpoints("product")
        assert "result(s)" in caplog.text

    def test_get_endpoint_detail_logs(self, caplog):
        from drf_mcp_docs.server import tools

        with caplog.at_level(logging.DEBUG, logger="drf_mcp_docs.server.tools"):
            tools.get_endpoint_detail("/api/products/", "get")
        assert "get_endpoint_detail" in caplog.text

    def test_get_endpoint_detail_not_found(self, caplog):
        from drf_mcp_docs.server import tools

        with caplog.at_level(logging.DEBUG, logger="drf_mcp_docs.server.tools"):
            tools.get_endpoint_detail("/api/nonexistent/", "get")
        assert "not found" in caplog.text

    def test_get_request_example_logs(self, caplog):
        from drf_mcp_docs.server import tools

        with caplog.at_level(logging.DEBUG, logger="drf_mcp_docs.server.tools"):
            tools.get_request_example("/api/products/", "post")
        assert "get_request_example" in caplog.text

    def test_get_response_example_logs(self, caplog):
        from drf_mcp_docs.server import tools

        with caplog.at_level(logging.DEBUG, logger="drf_mcp_docs.server.tools"):
            tools.get_response_example("/api/products/", "get")
        assert "get_response_example" in caplog.text

    def test_generate_code_snippet_logs(self, caplog):
        from drf_mcp_docs.server import tools

        with caplog.at_level(logging.DEBUG, logger="drf_mcp_docs.server.tools"):
            tools.generate_code_snippet("/api/products/", "get")
        assert "generate_code_snippet" in caplog.text

    def test_list_schemas_logs(self, caplog):
        from drf_mcp_docs.server import tools

        with caplog.at_level(logging.DEBUG, logger="drf_mcp_docs.server.tools"):
            tools.list_schemas()
        assert "list_schemas" in caplog.text
        assert "schema(s)" in caplog.text

    def test_get_schema_detail_logs(self, caplog):
        from drf_mcp_docs.server import tools

        with caplog.at_level(logging.DEBUG, logger="drf_mcp_docs.server.tools"):
            tools.get_schema_detail("Product")
        assert "get_schema_detail" in caplog.text
        assert "found" in caplog.text

    def test_get_schema_detail_not_found(self, caplog):
        from drf_mcp_docs.server import tools

        with caplog.at_level(logging.DEBUG, logger="drf_mcp_docs.server.tools"):
            tools.get_schema_detail("Nonexistent")
        assert "not found" in caplog.text

    def test_validate_inputs_invalid_path(self, caplog):
        from drf_mcp_docs.server import tools

        with caplog.at_level(logging.DEBUG, logger="drf_mcp_docs.server.tools"):
            tools.get_endpoint_detail("no-slash", "get")
        assert "validation failed" in caplog.text

    def test_validate_inputs_invalid_method(self, caplog):
        from drf_mcp_docs.server import tools

        with caplog.at_level(logging.DEBUG, logger="drf_mcp_docs.server.tools"):
            tools.get_endpoint_detail("/api/products/", "INVALID")
        assert "validation failed" in caplog.text


class TestResourceAccessLogging:
    """Verify resource access emits DEBUG logs."""

    @pytest.fixture(autouse=True)
    def _mock_processor(self):
        from drf_mcp_docs.schema.processor import SchemaProcessor

        processor = SchemaProcessor(SAMPLE_OPENAPI_SCHEMA)
        with patch("drf_mcp_docs.server.resources.get_processor", return_value=processor):
            yield

    def test_overview_resource_logs(self, caplog):
        from drf_mcp_docs.server import resources

        with caplog.at_level(logging.DEBUG, logger="drf_mcp_docs.server.resources"):
            resources.api_overview()
        assert "api://overview" in caplog.text

    def test_endpoints_resource_logs(self, caplog):
        from drf_mcp_docs.server import resources

        with caplog.at_level(logging.DEBUG, logger="drf_mcp_docs.server.resources"):
            resources.api_endpoints()
        assert "api://endpoints" in caplog.text

    def test_endpoint_detail_resource_logs(self, caplog):
        from drf_mcp_docs.server import resources

        with caplog.at_level(logging.DEBUG, logger="drf_mcp_docs.server.resources"):
            resources.api_endpoint_detail("get", "/api/products/")
        assert "api://endpoints" in caplog.text

    def test_schemas_resource_logs(self, caplog):
        from drf_mcp_docs.server import resources

        with caplog.at_level(logging.DEBUG, logger="drf_mcp_docs.server.resources"):
            resources.api_schemas()
        assert "api://schemas" in caplog.text

    def test_schema_detail_resource_logs(self, caplog):
        from drf_mcp_docs.server import resources

        with caplog.at_level(logging.DEBUG, logger="drf_mcp_docs.server.resources"):
            resources.api_schema_detail("Product")
        assert "api://schemas/Product" in caplog.text

    def test_auth_resource_logs(self, caplog):
        from drf_mcp_docs.server import resources

        with caplog.at_level(logging.DEBUG, logger="drf_mcp_docs.server.resources"):
            resources.api_auth()
        assert "api://auth" in caplog.text


class TestSchemaProcessorLogging:
    """Verify schema processor logging."""

    def test_init_logs(self, caplog):
        from drf_mcp_docs.schema.processor import SchemaProcessor

        with caplog.at_level(logging.DEBUG, logger="drf_mcp_docs.schema.processor"):
            SchemaProcessor(SAMPLE_OPENAPI_SCHEMA)
        assert "SchemaProcessor initialized" in caplog.text
        assert "paths" in caplog.text

    def test_schema_not_found_logs(self, caplog):
        from drf_mcp_docs.schema.processor import SchemaProcessor

        processor = SchemaProcessor(SAMPLE_OPENAPI_SCHEMA)
        with caplog.at_level(logging.DEBUG, logger="drf_mcp_docs.schema.processor"):
            processor.get_schema_definition("Nonexistent")
        assert "not found" in caplog.text

    def test_search_endpoints_logs(self, caplog):
        from drf_mcp_docs.schema.processor import SchemaProcessor

        processor = SchemaProcessor(SAMPLE_OPENAPI_SCHEMA)
        with caplog.at_level(logging.DEBUG, logger="drf_mcp_docs.schema.processor"):
            processor.search_endpoints("product")
        assert "match(es)" in caplog.text

    def test_ref_depth_limit_logs(self, caplog):
        from drf_mcp_docs.schema.processor import SchemaProcessor

        processor = SchemaProcessor(SAMPLE_OPENAPI_SCHEMA)
        with caplog.at_level(logging.WARNING, logger="drf_mcp_docs.schema.processor"):
            processor.resolve_ref("#/components/schemas/Product", _depth=0)
        assert "depth limit" in caplog.text


class TestMountLogging:
    """Verify ASGI mount logs configuration."""

    def test_mount_mcp_logs_path(self, caplog):
        mock_mcp = MagicMock()
        mock_mcp.streamable_http_app.return_value = MagicMock()
        mock_django = MagicMock()

        with caplog.at_level(logging.INFO, logger="drf_mcp_docs.urls"):
            from drf_mcp_docs.urls import mount_mcp

            mount_mcp(mock_django, mcp=mock_mcp, path="/mcp/")
        assert "/mcp/" in caplog.text


class TestSettingsLogging:
    """Verify settings resolution logging."""

    def test_get_all_settings_logs(self, caplog):
        from drf_mcp_docs.settings import get_all_settings

        with caplog.at_level(logging.DEBUG, logger="drf_mcp_docs.settings"):
            get_all_settings()
        assert "Resolved settings" in caplog.text
