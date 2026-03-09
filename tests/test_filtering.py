from __future__ import annotations

from unittest.mock import patch

from drf_mcp_docs.server.instance import _filter_paths

SAMPLE_SCHEMA = {
    "info": {"title": "Test API", "version": "1.0"},
    "paths": {
        "/api/products/": {"get": {"summary": "List products"}},
        "/api/products/{id}/": {"get": {"summary": "Get product"}},
        "/api/internal/debug/": {"get": {"summary": "Debug info"}},
        "/api/internal/health/": {"get": {"summary": "Health check"}},
        "/admin/dashboard/": {"get": {"summary": "Admin dashboard"}},
        "/docs/": {"get": {"summary": "API docs"}},
    },
}


class TestFilterPaths:
    @patch("drf_mcp_docs.server.instance.get_setting")
    def test_filter_by_prefix(self, mock_get_setting):
        mock_get_setting.side_effect = lambda name: {
            "SCHEMA_PATH_PREFIX": "/api/",
            "EXCLUDE_PATHS": [],
        }[name]

        result = _filter_paths(SAMPLE_SCHEMA)
        paths = list(result["paths"].keys())

        assert "/api/products/" in paths
        assert "/api/products/{id}/" in paths
        assert "/api/internal/debug/" in paths
        assert "/api/internal/health/" in paths
        assert "/admin/dashboard/" not in paths
        assert "/docs/" not in paths

    @patch("drf_mcp_docs.server.instance.get_setting")
    def test_exclude_paths(self, mock_get_setting):
        mock_get_setting.side_effect = lambda name: {
            "SCHEMA_PATH_PREFIX": "/api/",
            "EXCLUDE_PATHS": ["/api/internal/"],
        }[name]

        result = _filter_paths(SAMPLE_SCHEMA)
        paths = list(result["paths"].keys())

        assert "/api/products/" in paths
        assert "/api/products/{id}/" in paths
        assert "/api/internal/debug/" not in paths
        assert "/api/internal/health/" not in paths

    @patch("drf_mcp_docs.server.instance.get_setting")
    def test_exclude_multiple_paths(self, mock_get_setting):
        mock_get_setting.side_effect = lambda name: {
            "SCHEMA_PATH_PREFIX": "",
            "EXCLUDE_PATHS": ["/admin/", "/docs/"],
        }[name]

        result = _filter_paths(SAMPLE_SCHEMA)
        paths = list(result["paths"].keys())

        assert "/api/products/" in paths
        assert "/admin/dashboard/" not in paths
        assert "/docs/" not in paths

    @patch("drf_mcp_docs.server.instance.get_setting")
    def test_no_filtering_when_empty(self, mock_get_setting):
        mock_get_setting.side_effect = lambda name: {
            "SCHEMA_PATH_PREFIX": "",
            "EXCLUDE_PATHS": [],
        }[name]

        result = _filter_paths(SAMPLE_SCHEMA)

        assert result["paths"] == SAMPLE_SCHEMA["paths"]

    @patch("drf_mcp_docs.server.instance.get_setting")
    def test_combined_prefix_and_exclude(self, mock_get_setting):
        mock_get_setting.side_effect = lambda name: {
            "SCHEMA_PATH_PREFIX": "/api/",
            "EXCLUDE_PATHS": ["/api/internal/"],
        }[name]

        result = _filter_paths(SAMPLE_SCHEMA)
        paths = list(result["paths"].keys())

        assert paths == ["/api/products/", "/api/products/{id}/"]

    @patch("drf_mcp_docs.server.instance.get_setting")
    def test_preserves_non_path_schema_keys(self, mock_get_setting):
        mock_get_setting.side_effect = lambda name: {
            "SCHEMA_PATH_PREFIX": "/api/",
            "EXCLUDE_PATHS": [],
        }[name]

        result = _filter_paths(SAMPLE_SCHEMA)

        assert result["info"] == SAMPLE_SCHEMA["info"]

    @patch("drf_mcp_docs.server.instance.get_setting")
    def test_does_not_mutate_original_schema(self, mock_get_setting):
        mock_get_setting.side_effect = lambda name: {
            "SCHEMA_PATH_PREFIX": "/api/",
            "EXCLUDE_PATHS": ["/api/internal/"],
        }[name]

        original_paths = dict(SAMPLE_SCHEMA["paths"])
        _filter_paths(SAMPLE_SCHEMA)

        assert SAMPLE_SCHEMA["paths"] == original_paths
