import json
from unittest.mock import patch

import pytest

from drf_mcp_docs.schema.processor import SchemaProcessor
from tests.conftest import SAMPLE_OPENAPI_SCHEMA


@pytest.fixture(autouse=True)
def mock_processor():
    processor = SchemaProcessor(SAMPLE_OPENAPI_SCHEMA)
    with patch("drf_mcp_docs.server.resources.get_processor", return_value=processor):
        yield processor


class TestResources:
    def test_api_overview_resource(self):
        from drf_mcp_docs.server.resources import api_overview

        result = json.loads(api_overview())
        assert result["title"] == "Test API"
        assert result["endpoint_count"] == 6
        assert result["version"] == "1.0.0"

    def test_api_endpoints_resource(self):
        from drf_mcp_docs.server.resources import api_endpoints

        result = json.loads(api_endpoints())
        assert isinstance(result, list)
        assert len(result) == 6
        for ep in result:
            assert "path" in ep
            assert "method" in ep
            assert "summary" in ep

    def test_api_schemas_resource(self):
        from drf_mcp_docs.server.resources import api_schemas

        result = json.loads(api_schemas())
        assert isinstance(result, list)
        names = [s["name"] for s in result]
        assert "Product" in names
        assert "Category" in names

    def test_api_schema_detail_resource(self):
        from drf_mcp_docs.server.resources import api_schema_detail

        result = json.loads(api_schema_detail("Product"))
        assert result["name"] == "Product"
        assert "name" in result["properties"]

    def test_api_schema_detail_not_found(self):
        from drf_mcp_docs.server.resources import api_schema_detail

        result = json.loads(api_schema_detail("NonExistent"))
        assert "error" in result

    def test_api_auth_resource(self):
        from drf_mcp_docs.server.resources import api_auth

        result = json.loads(api_auth())
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["name"] == "bearerAuth"
        assert result[0]["type"] == "bearer"

    def test_api_endpoint_detail_resource(self):
        from drf_mcp_docs.server.resources import api_endpoint_detail

        result = json.loads(api_endpoint_detail("get", "api/products/"))
        assert result["method"] == "GET"
        assert result["operation_id"] == "products_list"
