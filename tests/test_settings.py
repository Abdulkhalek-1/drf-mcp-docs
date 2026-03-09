from __future__ import annotations

from unittest.mock import patch

from drf_mcp_docs.settings import DEFAULTS, get_all_settings, get_setting


class TestGetSetting:
    @patch("drf_mcp_docs.settings.settings")
    def test_returns_defaults_when_no_user_config(self, mock_settings):
        mock_settings.DRF_MCP_DOCS = {}
        mock_settings.DEBUG = False

        assert get_setting("SERVER_NAME") == "drf-mcp-docs"
        assert get_setting("TRANSPORT") == "streamable-http"
        assert get_setting("DEFAULT_CODE_LANGUAGE") == "javascript"
        assert get_setting("DEFAULT_HTTP_CLIENT") == "fetch"
        assert get_setting("SCHEMA_ADAPTER") is None
        assert get_setting("SCHEMA_PATH_PREFIX") == "/api/"
        assert get_setting("EXCLUDE_PATHS") == []
        assert get_setting("MCP_ENDPOINT") == "/mcp/"
        assert get_setting("SERVER_INSTRUCTIONS") == ""

    @patch("drf_mcp_docs.settings.settings")
    def test_user_overrides(self, mock_settings):
        mock_settings.DRF_MCP_DOCS = {
            "SERVER_NAME": "my-api",
            "TRANSPORT": "stdio",
            "DEFAULT_CODE_LANGUAGE": "typescript",
        }
        mock_settings.DEBUG = False

        assert get_setting("SERVER_NAME") == "my-api"
        assert get_setting("TRANSPORT") == "stdio"
        assert get_setting("DEFAULT_CODE_LANGUAGE") == "typescript"
        # Non-overridden settings still return defaults
        assert get_setting("DEFAULT_HTTP_CLIENT") == "fetch"

    @patch("drf_mcp_docs.settings.settings")
    def test_cache_schema_defaults_to_not_debug(self, mock_settings):
        mock_settings.DRF_MCP_DOCS = {}

        mock_settings.DEBUG = False
        assert get_setting("CACHE_SCHEMA") is True

        mock_settings.DEBUG = True
        assert get_setting("CACHE_SCHEMA") is False

    @patch("drf_mcp_docs.settings.settings")
    def test_cache_schema_user_override_takes_precedence(self, mock_settings):
        mock_settings.DEBUG = True
        mock_settings.DRF_MCP_DOCS = {"CACHE_SCHEMA": True}

        assert get_setting("CACHE_SCHEMA") is True

    @patch("drf_mcp_docs.settings.settings")
    def test_no_drf_mcp_docs_attribute(self, mock_settings):
        del mock_settings.DRF_MCP_DOCS
        mock_settings.DEBUG = False

        assert get_setting("SERVER_NAME") == "drf-mcp-docs"


class TestGetAllSettings:
    @patch("drf_mcp_docs.settings.settings")
    def test_returns_all_settings(self, mock_settings):
        mock_settings.DRF_MCP_DOCS = {}
        mock_settings.DEBUG = False

        result = get_all_settings()

        assert set(result.keys()) == set(DEFAULTS.keys())
        assert result["SERVER_NAME"] == "drf-mcp-docs"
        assert result["CACHE_SCHEMA"] is True

    @patch("drf_mcp_docs.settings.settings")
    def test_includes_user_overrides(self, mock_settings):
        mock_settings.DRF_MCP_DOCS = {"SERVER_NAME": "custom-api"}
        mock_settings.DEBUG = False

        result = get_all_settings()

        assert result["SERVER_NAME"] == "custom-api"
        assert result["DEFAULT_HTTP_CLIENT"] == "fetch"
