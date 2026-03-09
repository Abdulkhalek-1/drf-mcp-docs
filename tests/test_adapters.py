from unittest.mock import MagicMock, patch

import pytest

from drf_mcp_docs.adapters import get_adapter
from drf_mcp_docs.adapters.base import BaseSchemaAdapter
from drf_mcp_docs.adapters.drf import DRFBuiltinAdapter
from drf_mcp_docs.adapters.spectacular import SpectacularAdapter
from drf_mcp_docs.adapters.yasg import YasgAdapter


class TestSpectacularAdapter:
    def test_is_available_when_installed_and_configured(self, settings):
        settings.REST_FRAMEWORK = {
            "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
        }
        with patch.dict("sys.modules", {"drf_spectacular": MagicMock()}):
            assert SpectacularAdapter.is_available() is True

    def test_is_not_available_when_installed_but_not_configured(self, settings):
        settings.REST_FRAMEWORK = {
            "DEFAULT_SCHEMA_CLASS": "rest_framework.schemas.openapi.AutoSchema",
        }
        with patch.dict("sys.modules", {"drf_spectacular": MagicMock()}):
            assert SpectacularAdapter.is_available() is False

    def test_is_not_available_when_not_installed(self, settings):
        settings.REST_FRAMEWORK = {
            "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
        }
        with patch.dict("sys.modules", {"drf_spectacular": None}):
            assert SpectacularAdapter.is_available() is False

    @pytest.mark.django_db
    @pytest.mark.skipif(
        not SpectacularAdapter.is_available(),
        reason="drf-spectacular not installed or not configured",
    )
    def test_get_schema(self, settings):
        settings.REST_FRAMEWORK = {
            "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
        }
        adapter = SpectacularAdapter()
        schema = adapter.get_schema()
        assert isinstance(schema, dict)
        assert "openapi" in schema


class TestYasgAdapter:
    def test_is_available_when_installed(self):
        with patch.dict("sys.modules", {"drf_yasg": MagicMock()}):
            assert YasgAdapter.is_available() is True

    def test_swagger_to_openapi_conversion(self):
        adapter = YasgAdapter()
        swagger = {
            "swagger": "2.0",
            "info": {"title": "Test", "version": "1.0"},
            "host": "api.example.com",
            "basePath": "/v1",
            "schemes": ["https"],
            "definitions": {
                "Item": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "name": {"type": "string"},
                    },
                    "required": ["name"],
                }
            },
            "securityDefinitions": {
                "basic": {"type": "basic"},
                "apiKey": {"type": "apiKey", "name": "X-API-Key", "in": "header"},
            },
            "paths": {
                "/items/": {
                    "get": {
                        "summary": "List items",
                        "operationId": "list_items",
                        "parameters": [
                            {
                                "name": "page",
                                "in": "query",
                                "type": "integer",
                                "required": False,
                            }
                        ],
                        "responses": {
                            "200": {
                                "description": "OK",
                                "schema": {
                                    "type": "array",
                                    "items": {"$ref": "#/definitions/Item"},
                                },
                            }
                        },
                    },
                    "post": {
                        "summary": "Create item",
                        "parameters": [
                            {
                                "name": "body",
                                "in": "body",
                                "required": True,
                                "schema": {"$ref": "#/definitions/Item"},
                            }
                        ],
                        "responses": {
                            "201": {"description": "Created"},
                        },
                    },
                },
            },
        }
        result = adapter._convert_swagger_to_openapi3(swagger)

        assert result["openapi"] == "3.0.3"
        assert result["info"]["title"] == "Test"
        assert result["servers"][0]["url"] == "https://api.example.com/v1"

        # Schemas converted
        assert "Item" in result["components"]["schemas"]
        schema = result["components"]["schemas"]["Item"]
        assert "name" in schema["properties"]
        assert schema["required"] == ["name"]

        # Security schemes converted
        assert "basic" in result["components"]["securitySchemes"]
        assert result["components"]["securitySchemes"]["basic"]["type"] == "http"
        assert result["components"]["securitySchemes"]["basic"]["scheme"] == "basic"

        assert "apiKey" in result["components"]["securitySchemes"]
        assert result["components"]["securitySchemes"]["apiKey"]["name"] == "X-API-Key"

        # Paths converted
        assert "/items/" in result["paths"]
        get_op = result["paths"]["/items/"]["get"]
        assert get_op["summary"] == "List items"
        assert len(get_op["parameters"]) == 1
        assert get_op["parameters"][0]["name"] == "page"

        # Response schema refs updated
        response_schema = get_op["responses"]["200"]["content"]["application/json"]["schema"]
        assert response_schema["items"]["$ref"] == "#/components/schemas/Item"

        # Body parameter → requestBody
        post_op = result["paths"]["/items/"]["post"]
        assert "requestBody" in post_op
        assert post_op["requestBody"]["required"] is True


class TestDRFBuiltinAdapter:
    def test_is_available(self):
        assert DRFBuiltinAdapter.is_available() is True

    @pytest.mark.django_db
    def test_get_schema(self):
        adapter = DRFBuiltinAdapter()
        schema = adapter.get_schema()
        assert isinstance(schema, dict)
        assert "openapi" in schema


class TestGetAdapter:
    @pytest.mark.django_db
    def test_auto_detection_returns_adapter(self):
        adapter = get_adapter()
        assert isinstance(adapter, BaseSchemaAdapter)

    def test_settings_override(self):
        with patch("drf_mcp_docs.adapters.get_setting") as mock_setting:
            mock_setting.return_value = "drf_mcp_docs.adapters.drf.DRFBuiltinAdapter"
            adapter = get_adapter()
            assert isinstance(adapter, DRFBuiltinAdapter)

    def test_settings_override_bad_module(self):
        with patch("drf_mcp_docs.adapters.get_setting") as mock_setting:
            mock_setting.return_value = "nonexistent.module.Adapter"
            with pytest.raises(ImportError, match="Could not import module"):
                get_adapter()

    def test_settings_override_bad_class(self):
        with patch("drf_mcp_docs.adapters.get_setting") as mock_setting:
            mock_setting.return_value = "drf_mcp_docs.adapters.drf.NonexistentClass"
            with pytest.raises(ImportError, match="has no class"):
                get_adapter()


class TestYasgAdapterLogging:
    def test_unknown_param_location_logs_warning(self, caplog):
        import logging

        swagger = {
            "swagger": "2.0",
            "info": {"title": "Test", "version": "1.0"},
            "basePath": "/api",
            "paths": {
                "/test": {
                    "get": {
                        "parameters": [
                            {"name": "x", "in": "unknown_location", "type": "string"},
                        ],
                        "responses": {"200": {"description": "OK"}},
                    }
                }
            },
        }
        adapter = YasgAdapter()
        with caplog.at_level(logging.WARNING, logger="drf_mcp_docs.adapters.yasg"):
            adapter._convert_swagger_to_openapi3(swagger)
        assert "Unknown parameter location" in caplog.text
        assert "unknown_location" in caplog.text
