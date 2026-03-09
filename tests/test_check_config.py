from __future__ import annotations

from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
from django.core.management import call_command

from tests.conftest import SAMPLE_OPENAPI_SCHEMA

_DEFAULT_SETTINGS = {
    "SERVER_NAME": "test",
    "SERVER_INSTRUCTIONS": "",
    "SCHEMA_ADAPTER": None,
    "SCHEMA_PATH_PREFIX": "/api/",
    "EXCLUDE_PATHS": [],
    "CACHE_SCHEMA": True,
    "CACHE_TTL": None,
    "TRANSPORT": "streamable-http",
    "MCP_ENDPOINT": "/mcp/",
    "DEFAULT_CODE_LANGUAGE": "javascript",
    "DEFAULT_HTTP_CLIENT": "fetch",
}


def _make_get_setting(**overrides):
    merged = {**_DEFAULT_SETTINGS, **overrides}
    return lambda name: merged.get(name, name)


def _run(**overrides):
    """Run checkmcpconfig with patched adapter and optional settings overrides."""
    mock_adapter = MagicMock()
    mock_adapter.get_schema.return_value = SAMPLE_OPENAPI_SCHEMA

    out = StringIO()
    with (
        patch(
            "drf_mcp_docs.management.commands.checkmcpconfig.get_setting",
            side_effect=_make_get_setting(**overrides),
        ),
        patch(
            "drf_mcp_docs.management.commands.checkmcpconfig.django_settings",
        ) as mock_settings,
        patch(
            "drf_mcp_docs.management.commands.checkmcpconfig.get_adapter",
            return_value=mock_adapter,
        ),
    ):
        mock_settings.DRF_MCP_DOCS = overrides
        call_command("checkmcpconfig", stdout=out)
    return out.getvalue()


def _run_expect_exit(**overrides):
    """Run checkmcpconfig expecting SystemExit(1)."""
    mock_adapter = MagicMock()
    mock_adapter.get_schema.return_value = SAMPLE_OPENAPI_SCHEMA

    out = StringIO()
    with (
        patch(
            "drf_mcp_docs.management.commands.checkmcpconfig.get_setting",
            side_effect=_make_get_setting(**overrides),
        ),
        patch(
            "drf_mcp_docs.management.commands.checkmcpconfig.django_settings",
        ) as mock_settings,
        patch(
            "drf_mcp_docs.management.commands.checkmcpconfig.get_adapter",
            return_value=mock_adapter,
        ),
        pytest.raises(SystemExit, match="1"),
    ):
        mock_settings.DRF_MCP_DOCS = overrides
        call_command("checkmcpconfig", stdout=out)
    return out.getvalue()


class TestCheckSettings:
    def test_valid_settings_no_errors(self):
        output = _run()
        assert "All checks passed" in output

    def test_unknown_setting_key_warns(self):
        output = _run(**{"SCHEMA_ADAPTOR": None})
        assert "WARNING" in output
        assert "Unknown setting" in output
        assert "SCHEMA_ADAPTOR" in output
        assert "SCHEMA_ADAPTER" in output  # did-you-mean hint

    def test_invalid_transport_errors(self):
        output = _run_expect_exit(TRANSPORT="websocket")
        assert "ERROR" in output
        assert "TRANSPORT" in output

    def test_invalid_code_language_errors(self):
        output = _run_expect_exit(DEFAULT_CODE_LANGUAGE="ruby")
        assert "ERROR" in output
        assert "DEFAULT_CODE_LANGUAGE" in output

    def test_invalid_http_client_errors(self):
        output = _run_expect_exit(DEFAULT_HTTP_CLIENT="curl")
        assert "ERROR" in output
        assert "DEFAULT_HTTP_CLIENT" in output

    def test_mismatched_client_and_language_warns(self):
        output = _run(DEFAULT_CODE_LANGUAGE="python", DEFAULT_HTTP_CLIENT="fetch")
        assert "WARNING" in output
        assert "auto-corrected" in output

    def test_invalid_cache_ttl_negative(self):
        output = _run_expect_exit(CACHE_TTL=-5)
        assert "ERROR" in output
        assert "CACHE_TTL" in output

    def test_invalid_cache_ttl_zero(self):
        output = _run_expect_exit(CACHE_TTL=0)
        assert "ERROR" in output
        assert "CACHE_TTL" in output

    def test_invalid_cache_ttl_string(self):
        output = _run_expect_exit(CACHE_TTL="60")
        assert "ERROR" in output
        assert "CACHE_TTL" in output

    def test_cache_ttl_none_ok(self):
        output = _run(CACHE_TTL=None)
        assert "CACHE_TTL = None" in output
        assert "All checks passed" in output

    def test_cache_ttl_positive_ok(self):
        output = _run(CACHE_TTL=300)
        assert "CACHE_TTL = 300" in output
        assert "All checks passed" in output

    def test_schema_path_prefix_no_slash_errors(self):
        output = _run_expect_exit(SCHEMA_PATH_PREFIX="api/")
        assert "ERROR" in output
        assert "SCHEMA_PATH_PREFIX" in output

    def test_mcp_endpoint_no_slash_errors(self):
        output = _run_expect_exit(MCP_ENDPOINT="mcp/")
        assert "ERROR" in output
        assert "MCP_ENDPOINT" in output

    def test_exclude_paths_not_list_errors(self):
        output = _run_expect_exit(EXCLUDE_PATHS="/admin/")
        assert "ERROR" in output
        assert "EXCLUDE_PATHS" in output


class TestCheckAdapters:
    def test_reports_adapter_availability(self):
        output = _run()
        assert "SpectacularAdapter:" in output
        assert "DRFBuiltinAdapter:" in output

    def test_active_adapter_reported(self):
        output = _run()
        assert "Active adapter:" in output
        assert "OK" in output

    def test_no_adapter_available_errors(self):
        out = StringIO()
        mock_adapter_error = RuntimeError("No schema adapter available")
        with (
            patch(
                "drf_mcp_docs.management.commands.checkmcpconfig.get_setting",
                side_effect=_make_get_setting(),
            ),
            patch(
                "drf_mcp_docs.management.commands.checkmcpconfig.django_settings",
            ) as mock_settings,
            patch(
                "drf_mcp_docs.management.commands.checkmcpconfig.get_adapter",
                side_effect=mock_adapter_error,
            ),
            pytest.raises(SystemExit, match="1"),
        ):
            mock_settings.DRF_MCP_DOCS = {}
            call_command("checkmcpconfig", stdout=out)


class TestCheckSchema:
    def test_schema_generation_success(self):
        output = _run()
        assert "Schema generated successfully" in output
        assert "endpoint(s) after path filtering" in output
        assert "schema definition(s) found" in output

    def test_schema_generation_failure(self):
        mock_adapter = MagicMock()
        mock_adapter.get_schema.side_effect = Exception("connection error")

        out = StringIO()
        with (
            patch(
                "drf_mcp_docs.management.commands.checkmcpconfig.get_setting",
                side_effect=_make_get_setting(),
            ),
            patch(
                "drf_mcp_docs.management.commands.checkmcpconfig.django_settings",
            ) as mock_settings,
            patch(
                "drf_mcp_docs.management.commands.checkmcpconfig.get_adapter",
                return_value=mock_adapter,
            ),
            pytest.raises(SystemExit, match="1"),
        ):
            mock_settings.DRF_MCP_DOCS = {}
            call_command("checkmcpconfig", stdout=out)
        output = out.getvalue()
        assert "Schema generation failed" in output
        assert "connection error" in output

    def test_empty_schema_warns(self):
        mock_adapter = MagicMock()
        mock_adapter.get_schema.return_value = {
            "openapi": "3.0.3",
            "info": {"title": "API", "version": "0.1.0"},
            "paths": {},
        }

        out = StringIO()
        with (
            patch(
                "drf_mcp_docs.management.commands.checkmcpconfig.get_setting",
                side_effect=_make_get_setting(),
            ),
            patch(
                "drf_mcp_docs.management.commands.checkmcpconfig.django_settings",
            ) as mock_settings,
            patch(
                "drf_mcp_docs.management.commands.checkmcpconfig.get_adapter",
                return_value=mock_adapter,
            ),
        ):
            mock_settings.DRF_MCP_DOCS = {}
            call_command("checkmcpconfig", stdout=out)
        output = out.getvalue()
        assert "0 endpoint" in output
        assert "WARNING" in output
        assert "0 endpoints" in output

    def test_filtering_reduces_to_zero_warns(self):
        mock_adapter = MagicMock()
        mock_adapter.get_schema.return_value = SAMPLE_OPENAPI_SCHEMA

        def filter_v2(schema):
            """Simulate _filter_paths with prefix /v2/ — removes all /api/ paths."""
            return {**schema, "paths": {}}

        out = StringIO()
        with (
            patch(
                "drf_mcp_docs.management.commands.checkmcpconfig.get_setting",
                side_effect=_make_get_setting(SCHEMA_PATH_PREFIX="/v2/"),
            ),
            patch(
                "drf_mcp_docs.management.commands.checkmcpconfig.django_settings",
            ) as mock_settings,
            patch(
                "drf_mcp_docs.management.commands.checkmcpconfig.get_adapter",
                return_value=mock_adapter,
            ),
            patch(
                "drf_mcp_docs.management.commands.checkmcpconfig._filter_paths",
                side_effect=filter_v2,
            ),
        ):
            mock_settings.DRF_MCP_DOCS = {}
            call_command("checkmcpconfig", stdout=out)
        output = out.getvalue()
        assert "reduced" in output
        assert "WARNING" in output


class TestExitCode:
    def test_exit_code_0_on_success(self):
        # Should not raise SystemExit
        _run()

    def test_exit_code_1_on_errors(self):
        _run_expect_exit(TRANSPORT="invalid")
