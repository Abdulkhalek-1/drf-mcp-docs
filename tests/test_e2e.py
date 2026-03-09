"""End-to-end tests exercising the full pipeline without mocking get_processor.

Pipeline: Django views -> adapter -> schema generation -> processor -> MCP resources/tools

These tests catch missing transitive dependencies (e.g. uritemplate, inflection)
and integration issues that unit tests with mocked processors cannot detect.
"""

from __future__ import annotations

import json
import time

import pytest

import drf_mcp_docs.server.instance as instance_module
from drf_mcp_docs.adapters.drf import DRFBuiltinAdapter
from drf_mcp_docs.server import resources, tools
from drf_mcp_docs.server.instance import get_processor, invalidate_schema_cache

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_path_containing(paths: dict | list, substring: str) -> str | None:
    """Find first path (key or dict value) containing the given substring."""
    if isinstance(paths, dict):
        for path in paths:
            if substring in path:
                return path
    else:
        for item in paths:
            p = item if isinstance(item, str) else item.get("path", "")
            if substring in p:
                return p
    return None


def _parse(json_str: str):
    return json.loads(json_str)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_processor():
    """Clear the cached processor singleton before and after each test."""
    instance_module._processor = None
    instance_module._processor_cached_at = None
    yield
    instance_module._processor = None
    instance_module._processor_cached_at = None


@pytest.fixture()
def drf_builtin_settings(settings):
    settings.DRF_MCP_DOCS = {
        "SCHEMA_ADAPTER": "drf_mcp_docs.adapters.drf.DRFBuiltinAdapter",
        "SCHEMA_PATH_PREFIX": "/api/",
        "EXCLUDE_PATHS": [],
        "CACHE_SCHEMA": False,
    }
    settings.REST_FRAMEWORK = {
        "DEFAULT_SCHEMA_CLASS": "rest_framework.schemas.openapi.AutoSchema",
    }
    return settings


@pytest.fixture()
def spectacular_settings(settings):
    pytest.importorskip("drf_spectacular")
    settings.DRF_MCP_DOCS = {
        "SCHEMA_ADAPTER": "drf_mcp_docs.adapters.spectacular.SpectacularAdapter",
        "SCHEMA_PATH_PREFIX": "/api/",
        "EXCLUDE_PATHS": [],
        "CACHE_SCHEMA": False,
    }
    settings.REST_FRAMEWORK = {
        "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    }
    settings.SPECTACULAR_SETTINGS = {
        "TITLE": "Test API",
        "VERSION": "1.0.0",
    }
    return settings


@pytest.fixture()
def yasg_settings(settings):
    pytest.importorskip("drf_yasg")
    settings.DRF_MCP_DOCS = {
        "SCHEMA_ADAPTER": "drf_mcp_docs.adapters.yasg.YasgAdapter",
        "SCHEMA_PATH_PREFIX": "",
        "EXCLUDE_PATHS": [],
        "CACHE_SCHEMA": False,
    }
    settings.REST_FRAMEWORK = {
        "DEFAULT_SCHEMA_CLASS": "rest_framework.schemas.openapi.AutoSchema",
    }
    return settings


# ---------------------------------------------------------------------------
# 1. Adapter schema generation
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestAdapterSchemaGeneration:
    """Verify adapters produce valid schemas from real testapp views."""

    def test_drf_builtin_generates_valid_schema(self, drf_builtin_settings):
        adapter = DRFBuiltinAdapter()
        schema = adapter.get_schema()

        assert "openapi" in schema
        assert schema["paths"], "Schema should have non-empty paths"
        assert _find_path_containing(schema["paths"], "products")
        assert _find_path_containing(schema["paths"], "categories")

    def test_spectacular_generates_valid_schema(self, spectacular_settings):
        from drf_mcp_docs.adapters.spectacular import SpectacularAdapter

        adapter = SpectacularAdapter()
        schema = adapter.get_schema()

        assert "openapi" in schema
        assert schema["paths"], "Schema should have non-empty paths"
        assert _find_path_containing(schema["paths"], "products")
        assert _find_path_containing(schema["paths"], "categories")
        assert "components" in schema

    def test_yasg_generates_valid_schema(self, yasg_settings):
        from drf_mcp_docs.adapters.yasg import YasgAdapter

        adapter = YasgAdapter()
        schema = adapter.get_schema()

        assert schema.get("openapi", "").startswith("3.0")
        assert schema["paths"], "Schema should have non-empty paths"

    def test_drf_builtin_schema_contains_custom_action(self, drf_builtin_settings):
        adapter = DRFBuiltinAdapter()
        schema = adapter.get_schema()

        assert _find_path_containing(schema["paths"], "in_stock"), (
            "Custom 'in_stock' action should appear in schema paths"
        )

    def test_spectacular_schema_contains_custom_action(self, spectacular_settings):
        from drf_mcp_docs.adapters.spectacular import SpectacularAdapter

        adapter = SpectacularAdapter()
        schema = adapter.get_schema()

        assert _find_path_containing(schema["paths"], "in_stock"), (
            "Custom 'in_stock' action should appear in schema paths"
        )

    def test_schema_has_expected_methods(self, drf_builtin_settings):
        adapter = DRFBuiltinAdapter()
        schema = adapter.get_schema()

        products_path = _find_path_containing(schema["paths"], "products")
        assert products_path is not None
        # The list endpoint should support GET and POST
        path_item = schema["paths"][products_path]
        # Find the list path (no path params)
        if "{" not in products_path:
            assert "get" in path_item, "Products list should support GET"
            assert "post" in path_item, "Products list should support POST"


# ---------------------------------------------------------------------------
# 2. Full resource pipeline
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestFullResourcePipeline:
    """Call resource functions through the real pipeline (no mocked processor)."""

    def test_api_overview(self, drf_builtin_settings):
        result = _parse(resources.api_overview())

        assert "title" in result
        assert result["endpoint_count"] > 0

    def test_api_endpoints(self, drf_builtin_settings):
        result = _parse(resources.api_endpoints())

        assert isinstance(result, list)
        assert len(result) > 0
        for ep in result:
            assert "path" in ep
            assert "method" in ep

        paths = [ep["path"] for ep in result]
        assert any("products" in p for p in paths)
        assert any("categories" in p for p in paths)

    def test_api_endpoint_detail(self, drf_builtin_settings):
        # Discover a real endpoint path first
        endpoints = _parse(resources.api_endpoints())
        product_ep = next(ep for ep in endpoints if "products" in ep["path"] and ep["method"] == "GET")

        result = _parse(resources.api_endpoint_detail(product_ep["method"], product_ep["path"]))

        assert "error" not in result
        assert result["method"] == "GET"
        assert "products" in result["path"]

    def test_api_endpoint_detail_not_found(self, drf_builtin_settings):
        result = _parse(resources.api_endpoint_detail("get", "/nonexistent/path/"))

        assert "error" in result

    def test_api_schemas(self, drf_builtin_settings):
        result = _parse(resources.api_schemas())

        assert isinstance(result, list)
        # DRF builtin may or may not generate component schemas,
        # but if it does, they should have the expected structure
        if result:
            assert "name" in result[0]
            assert "fields" in result[0]

    def test_api_schema_detail(self, spectacular_settings):
        # Spectacular generates richer component schemas
        result = _parse(resources.api_schemas())

        assert len(result) > 0, "Spectacular should produce component schemas"
        schema_name = result[0]["name"]

        detail = _parse(resources.api_schema_detail(schema_name))
        assert "name" in detail
        assert "properties" in detail

    def test_api_schema_detail_not_found(self, drf_builtin_settings):
        result = _parse(resources.api_schema_detail("CompletelyFakeSchema"))

        assert "error" in result

    def test_api_auth(self, drf_builtin_settings):
        result = _parse(resources.api_auth())

        assert isinstance(result, list)
        # Default testapp has no auth configured
        assert result == []

    def test_api_overview_with_spectacular(self, spectacular_settings):
        result = _parse(resources.api_overview())

        assert result["endpoint_count"] > 0
        assert "title" in result


# ---------------------------------------------------------------------------
# 3. Full tool pipeline
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestFullToolPipeline:
    """Call tool functions through the real pipeline (no mocked processor)."""

    def test_search_endpoints(self, drf_builtin_settings):
        result = _parse(tools.search_endpoints("product"))

        assert isinstance(result, list)
        assert len(result) > 0
        assert any("products" in ep["path"] for ep in result)

    def test_search_endpoints_with_method_filter(self, drf_builtin_settings):
        result = _parse(tools.search_endpoints("product", method="GET"))

        assert isinstance(result, list)
        for ep in result:
            assert ep["method"] == "GET"

    def test_search_endpoints_no_results(self, drf_builtin_settings):
        result = _parse(tools.search_endpoints("zzz_nonexistent_xyz"))

        assert "message" in result

    def test_get_endpoint_detail(self, drf_builtin_settings):
        # Discover real path
        endpoints = _parse(resources.api_endpoints())
        product_ep = next(ep for ep in endpoints if "products" in ep["path"] and ep["method"] == "GET")

        result = _parse(tools.get_endpoint_detail(product_ep["path"], product_ep["method"]))

        assert "error" not in result
        assert result["method"] == "GET"
        assert "products" in result["path"]

    def test_get_request_example_post(self, drf_builtin_settings):
        # Find the products list POST endpoint
        endpoints = _parse(resources.api_endpoints())
        post_ep = next(
            (ep for ep in endpoints if "products" in ep["path"] and ep["method"] == "POST" and "{" not in ep["path"]),
            None,
        )
        if post_ep is None:
            pytest.skip("No POST endpoint found for products list")

        result = _parse(tools.get_request_example(post_ep["path"], post_ep["method"]))

        assert result["method"] == "POST"
        assert "body" in result
        assert "name" in result["body"]

    def test_get_response_example(self, drf_builtin_settings):
        endpoints = _parse(resources.api_endpoints())
        get_ep = next(ep for ep in endpoints if "products" in ep["path"] and ep["method"] == "GET")

        result = _parse(tools.get_response_example(get_ep["path"], get_ep["method"]))

        # Should have a status_code or a message about no response definition
        assert "status_code" in result or "message" in result

    def test_generate_code_snippet_fetch(self, drf_builtin_settings):
        endpoints = _parse(resources.api_endpoints())
        get_ep = next(ep for ep in endpoints if "products" in ep["path"] and ep["method"] == "GET")

        result = _parse(
            tools.generate_code_snippet(get_ep["path"], get_ep["method"], language="javascript", client="fetch")
        )

        assert "code" in result
        assert "fetch" in result["code"]
        assert "async function" in result["code"]

    def test_generate_code_snippet_axios(self, drf_builtin_settings):
        endpoints = _parse(resources.api_endpoints())
        get_ep = next(ep for ep in endpoints if "products" in ep["path"] and ep["method"] == "GET")

        result = _parse(
            tools.generate_code_snippet(get_ep["path"], get_ep["method"], language="javascript", client="axios")
        )

        assert "code" in result
        assert "axios" in result["code"]

    def test_generate_code_snippet_ky(self, drf_builtin_settings):
        endpoints = _parse(resources.api_endpoints())
        get_ep = next(ep for ep in endpoints if "products" in ep["path"] and ep["method"] == "GET")

        result = _parse(
            tools.generate_code_snippet(get_ep["path"], get_ep["method"], language="javascript", client="ky")
        )

        assert "code" in result
        assert "ky" in result["code"]

    def test_generate_code_snippet_typescript(self, drf_builtin_settings):
        endpoints = _parse(resources.api_endpoints())
        get_ep = next(ep for ep in endpoints if "products" in ep["path"] and ep["method"] == "GET")

        result = _parse(
            tools.generate_code_snippet(get_ep["path"], get_ep["method"], language="typescript", client="fetch")
        )

        assert "code" in result
        assert result["language"] == "typescript"

    def test_list_schemas(self, spectacular_settings):
        result = _parse(tools.list_schemas())

        assert isinstance(result, list)
        assert len(result) > 0
        for schema in result:
            assert "name" in schema
            assert "description" in schema

    def test_get_schema_detail(self, spectacular_settings):
        schemas = _parse(tools.list_schemas())
        assert len(schemas) > 0

        result = _parse(tools.get_schema_detail(schemas[0]["name"]))

        assert "name" in result
        assert "properties" in result


# ---------------------------------------------------------------------------
# 4. Path filtering integration
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPathFilteringIntegration:
    """Test SCHEMA_PATH_PREFIX and EXCLUDE_PATHS through the real pipeline."""

    def test_prefix_filters_to_products_only(self, settings):
        settings.DRF_MCP_DOCS = {
            "SCHEMA_ADAPTER": "drf_mcp_docs.adapters.drf.DRFBuiltinAdapter",
            "SCHEMA_PATH_PREFIX": "/api/products/",
            "EXCLUDE_PATHS": [],
            "CACHE_SCHEMA": False,
        }
        settings.REST_FRAMEWORK = {
            "DEFAULT_SCHEMA_CLASS": "rest_framework.schemas.openapi.AutoSchema",
        }

        processor = get_processor()
        endpoints = processor.get_endpoints()

        assert len(endpoints) > 0
        for ep in endpoints:
            assert "products" in ep.path
            assert "categories" not in ep.path

    def test_exclude_products(self, settings):
        settings.DRF_MCP_DOCS = {
            "SCHEMA_ADAPTER": "drf_mcp_docs.adapters.drf.DRFBuiltinAdapter",
            "SCHEMA_PATH_PREFIX": "/api/",
            "EXCLUDE_PATHS": ["/api/products/"],
            "CACHE_SCHEMA": False,
        }
        settings.REST_FRAMEWORK = {
            "DEFAULT_SCHEMA_CLASS": "rest_framework.schemas.openapi.AutoSchema",
        }

        processor = get_processor()
        endpoints = processor.get_endpoints()

        assert len(endpoints) > 0
        for ep in endpoints:
            assert "products" not in ep.path

    def test_exclude_multiple_paths(self, settings):
        settings.DRF_MCP_DOCS = {
            "SCHEMA_ADAPTER": "drf_mcp_docs.adapters.drf.DRFBuiltinAdapter",
            "SCHEMA_PATH_PREFIX": "/api/",
            "EXCLUDE_PATHS": ["/api/products/", "/api/categories/"],
            "CACHE_SCHEMA": False,
        }
        settings.REST_FRAMEWORK = {
            "DEFAULT_SCHEMA_CLASS": "rest_framework.schemas.openapi.AutoSchema",
        }

        processor = get_processor()
        endpoints = processor.get_endpoints()

        assert len(endpoints) == 0

    def test_prefix_no_match_yields_empty(self, settings):
        settings.DRF_MCP_DOCS = {
            "SCHEMA_ADAPTER": "drf_mcp_docs.adapters.drf.DRFBuiltinAdapter",
            "SCHEMA_PATH_PREFIX": "/nonexistent/",
            "EXCLUDE_PATHS": [],
            "CACHE_SCHEMA": False,
        }
        settings.REST_FRAMEWORK = {
            "DEFAULT_SCHEMA_CLASS": "rest_framework.schemas.openapi.AutoSchema",
        }

        processor = get_processor()
        endpoints = processor.get_endpoints()

        assert len(endpoints) == 0

        overview = _parse(resources.api_overview())
        assert overview["endpoint_count"] == 0


# ---------------------------------------------------------------------------
# 5. Schema caching
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestSchemaCaching:
    """Test processor singleton caching behavior."""

    def test_cache_true_returns_same_instance(self, settings):
        settings.DRF_MCP_DOCS = {
            "SCHEMA_ADAPTER": "drf_mcp_docs.adapters.drf.DRFBuiltinAdapter",
            "SCHEMA_PATH_PREFIX": "/api/",
            "EXCLUDE_PATHS": [],
            "CACHE_SCHEMA": True,
        }
        settings.REST_FRAMEWORK = {
            "DEFAULT_SCHEMA_CLASS": "rest_framework.schemas.openapi.AutoSchema",
        }

        proc1 = get_processor()
        proc2 = get_processor()

        assert proc1 is proc2

    def test_cache_false_returns_new_instance(self, settings):
        settings.DRF_MCP_DOCS = {
            "SCHEMA_ADAPTER": "drf_mcp_docs.adapters.drf.DRFBuiltinAdapter",
            "SCHEMA_PATH_PREFIX": "/api/",
            "EXCLUDE_PATHS": [],
            "CACHE_SCHEMA": False,
        }
        settings.REST_FRAMEWORK = {
            "DEFAULT_SCHEMA_CLASS": "rest_framework.schemas.openapi.AutoSchema",
        }

        proc1 = get_processor()
        proc2 = get_processor()

        assert proc1 is not proc2

    def test_cache_default_depends_on_debug(self, settings):
        settings.DRF_MCP_DOCS = {
            "SCHEMA_ADAPTER": "drf_mcp_docs.adapters.drf.DRFBuiltinAdapter",
            "SCHEMA_PATH_PREFIX": "/api/",
            "EXCLUDE_PATHS": [],
            # CACHE_SCHEMA intentionally omitted — defaults to `not DEBUG`
        }
        settings.REST_FRAMEWORK = {
            "DEFAULT_SCHEMA_CLASS": "rest_framework.schemas.openapi.AutoSchema",
        }

        # DEBUG=True -> caching off -> different instances
        settings.DEBUG = True
        proc1 = get_processor()
        proc2 = get_processor()
        assert proc1 is not proc2

        # DEBUG=False -> caching on -> same instance
        instance_module._processor = None
        instance_module._processor_cached_at = None
        settings.DEBUG = False
        proc3 = get_processor()
        proc4 = get_processor()
        assert proc3 is proc4

    def test_cache_ttl_none_caches_forever(self, settings):
        """CACHE_TTL=None (default) preserves current behavior: cache forever."""
        settings.DRF_MCP_DOCS = {
            "SCHEMA_ADAPTER": "drf_mcp_docs.adapters.drf.DRFBuiltinAdapter",
            "SCHEMA_PATH_PREFIX": "/api/",
            "EXCLUDE_PATHS": [],
            "CACHE_SCHEMA": True,
            "CACHE_TTL": None,
        }
        settings.REST_FRAMEWORK = {
            "DEFAULT_SCHEMA_CLASS": "rest_framework.schemas.openapi.AutoSchema",
        }
        proc1 = get_processor()
        proc2 = get_processor()
        assert proc1 is proc2

    def test_cache_ttl_expired_rebuilds(self, settings):
        """When TTL has elapsed, get_processor() returns a new instance."""
        settings.DRF_MCP_DOCS = {
            "SCHEMA_ADAPTER": "drf_mcp_docs.adapters.drf.DRFBuiltinAdapter",
            "SCHEMA_PATH_PREFIX": "/api/",
            "EXCLUDE_PATHS": [],
            "CACHE_SCHEMA": True,
            "CACHE_TTL": 60,
        }
        settings.REST_FRAMEWORK = {
            "DEFAULT_SCHEMA_CLASS": "rest_framework.schemas.openapi.AutoSchema",
        }
        proc1 = get_processor()

        # Simulate TTL expiration by backdating the timestamp
        instance_module._processor_cached_at = time.monotonic() - 120

        proc2 = get_processor()
        assert proc1 is not proc2

    def test_cache_ttl_not_expired_returns_same(self, settings):
        """When TTL has NOT elapsed, get_processor() returns the cached instance."""
        settings.DRF_MCP_DOCS = {
            "SCHEMA_ADAPTER": "drf_mcp_docs.adapters.drf.DRFBuiltinAdapter",
            "SCHEMA_PATH_PREFIX": "/api/",
            "EXCLUDE_PATHS": [],
            "CACHE_SCHEMA": True,
            "CACHE_TTL": 3600,
        }
        settings.REST_FRAMEWORK = {
            "DEFAULT_SCHEMA_CLASS": "rest_framework.schemas.openapi.AutoSchema",
        }
        proc1 = get_processor()
        proc2 = get_processor()
        assert proc1 is proc2

    def test_invalidate_schema_cache_clears_processor(self, settings):
        """invalidate_schema_cache() forces rebuild on next get_processor() call."""
        settings.DRF_MCP_DOCS = {
            "SCHEMA_ADAPTER": "drf_mcp_docs.adapters.drf.DRFBuiltinAdapter",
            "SCHEMA_PATH_PREFIX": "/api/",
            "EXCLUDE_PATHS": [],
            "CACHE_SCHEMA": True,
        }
        settings.REST_FRAMEWORK = {
            "DEFAULT_SCHEMA_CLASS": "rest_framework.schemas.openapi.AutoSchema",
        }
        proc1 = get_processor()
        invalidate_schema_cache()
        proc2 = get_processor()
        assert proc1 is not proc2

    def test_invalidate_schema_cache_importable_from_top_level(self):
        """The function should be importable from drf_mcp_docs directly."""
        from drf_mcp_docs import invalidate_schema_cache as fn

        assert callable(fn)


# ---------------------------------------------------------------------------
# 6. Edge cases
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestEdgeCases:
    """Test error handling through the real pipeline."""

    def test_empty_schema_overview(self, settings):
        settings.DRF_MCP_DOCS = {
            "SCHEMA_ADAPTER": "drf_mcp_docs.adapters.drf.DRFBuiltinAdapter",
            "SCHEMA_PATH_PREFIX": "/nonexistent/",
            "EXCLUDE_PATHS": [],
            "CACHE_SCHEMA": False,
        }
        settings.REST_FRAMEWORK = {
            "DEFAULT_SCHEMA_CLASS": "rest_framework.schemas.openapi.AutoSchema",
        }

        overview = _parse(resources.api_overview())
        assert overview["endpoint_count"] == 0

        endpoints = _parse(resources.api_endpoints())
        assert endpoints == []

        search = _parse(tools.search_endpoints("anything"))
        assert "message" in search

    def test_schema_detail_nonexistent(self, drf_builtin_settings):
        result = _parse(tools.get_schema_detail("CompletelyFakeSchema"))

        assert "error" in result

    def test_endpoint_detail_nonexistent(self, drf_builtin_settings):
        result = _parse(tools.get_endpoint_detail("/api/nonexistent/", "get"))

        assert "error" in result

    def test_response_example_nonexistent_status(self, drf_builtin_settings):
        endpoints = _parse(resources.api_endpoints())
        get_ep = next(ep for ep in endpoints if "products" in ep["path"] and ep["method"] == "GET")

        result = _parse(tools.get_response_example(get_ep["path"], get_ep["method"], status_code="999"))

        # Should either fall back to a real status code or return a message
        assert "status_code" in result or "message" in result


# ---------------------------------------------------------------------------
# 7. Cross-adapter consistency
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCrossAdapterConsistency:
    """Verify all available adapters produce structurally compatible output."""

    def _get_adapter_configs(self, settings):
        configs = [
            (
                "drf_builtin",
                {
                    "SCHEMA_ADAPTER": "drf_mcp_docs.adapters.drf.DRFBuiltinAdapter",
                    "SCHEMA_PATH_PREFIX": "/api/",
                    "EXCLUDE_PATHS": [],
                    "CACHE_SCHEMA": False,
                },
                {"DEFAULT_SCHEMA_CLASS": "rest_framework.schemas.openapi.AutoSchema"},
            ),
        ]
        try:
            import drf_spectacular  # noqa: F401

            configs.append(
                (
                    "spectacular",
                    {
                        "SCHEMA_ADAPTER": "drf_mcp_docs.adapters.spectacular.SpectacularAdapter",
                        "SCHEMA_PATH_PREFIX": "/api/",
                        "EXCLUDE_PATHS": [],
                        "CACHE_SCHEMA": False,
                    },
                    {"DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema"},
                )
            )
        except ImportError:
            pass
        return configs

    def test_all_adapters_find_product_endpoints(self, settings):
        for name, mcp_settings, rf_settings in self._get_adapter_configs(settings):
            instance_module._processor = None
            instance_module._processor_cached_at = None
            settings.DRF_MCP_DOCS = mcp_settings
            settings.REST_FRAMEWORK = rf_settings

            processor = get_processor()
            endpoints = processor.get_endpoints()
            paths = [ep.path for ep in endpoints]

            assert any("products" in p for p in paths), (
                f"Adapter '{name}' did not find product endpoints. Paths: {paths}"
            )

    def test_all_adapters_produce_schemas(self, settings):
        for name, mcp_settings, rf_settings in self._get_adapter_configs(settings):
            instance_module._processor = None
            instance_module._processor_cached_at = None
            settings.DRF_MCP_DOCS = mcp_settings
            settings.REST_FRAMEWORK = rf_settings

            processor = get_processor()
            schemas = processor.get_schemas()

            # DRF builtin may not produce component schemas, so only assert for adapters that do
            if name != "drf_builtin":
                assert len(schemas) > 0, f"Adapter '{name}' should produce component schemas"
                assert any(len(s.properties) > 0 for s in schemas), f"Adapter '{name}' schemas should have properties"
