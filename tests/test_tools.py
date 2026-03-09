import json
from unittest.mock import patch

import pytest

from drf_mcp_docs.schema.processor import SchemaProcessor
from drf_mcp_docs.server import tools
from tests.conftest import SAMPLE_OPENAPI_SCHEMA


@pytest.fixture(autouse=True)
def mock_processor():
    processor = SchemaProcessor(SAMPLE_OPENAPI_SCHEMA)
    with patch("drf_mcp_docs.server.tools.get_processor", return_value=processor):
        yield processor


class TestSearchEndpoints:
    def test_search_by_keyword(self):
        result = json.loads(tools.search_endpoints("product"))
        assert isinstance(result, list)
        assert len(result) == 5

    def test_search_with_method_filter(self):
        result = json.loads(tools.search_endpoints("product", method="POST"))
        assert len(result) == 1

    def test_search_no_results(self):
        result = json.loads(tools.search_endpoints("nonexistent_xyz"))
        assert "message" in result


class TestGetEndpointDetail:
    def test_get_existing_endpoint(self):
        result = json.loads(tools.get_endpoint_detail("/api/products/", "get"))
        assert result["method"] == "GET"
        assert result["operation_id"] == "products_list"
        assert len(result["parameters"]) == 2

    def test_get_nonexistent_endpoint(self):
        result = json.loads(tools.get_endpoint_detail("/nonexistent/", "get"))
        assert "error" in result


class TestGetRequestExample:
    def test_get_example_with_body(self):
        result = json.loads(tools.get_request_example("/api/products/", "post"))
        assert result["method"] == "POST"
        assert "body" in result
        assert "name" in result["body"]
        assert "price" in result["body"]

    def test_get_example_with_params(self):
        result = json.loads(tools.get_request_example("/api/products/", "get"))
        assert "parameters" in result
        assert "page" in result["parameters"]


class TestGetResponseExample:
    def test_get_response_example(self):
        result = json.loads(tools.get_response_example("/api/products/", "get", "200"))
        assert result["status_code"] == "200"
        assert "example" in result

    def test_get_response_not_found(self):
        result = json.loads(tools.get_response_example("/nonexistent/", "get"))
        assert "error" in result


class TestGenerateCodeSnippet:
    def test_fetch_snippet(self):
        result = json.loads(tools.generate_code_snippet("/api/products/", "get", language="javascript", client="fetch"))
        assert result["client"] == "fetch"
        code = result["code"]
        assert "async function" in code
        assert "fetch" in code
        assert "await" in code

    def test_axios_snippet(self):
        result = json.loads(
            tools.generate_code_snippet("/api/products/", "post", language="javascript", client="axios")
        )
        code = result["code"]
        assert "axios" in code

    def test_ky_snippet(self):
        result = json.loads(tools.generate_code_snippet("/api/products/", "get", language="javascript", client="ky"))
        code = result["code"]
        assert "ky" in code

    def test_typescript_snippet(self):
        result = json.loads(
            tools.generate_code_snippet("/api/products/{id}/", "get", language="typescript", client="fetch")
        )
        code = result["code"]
        assert "number" in code

    def test_snippet_with_path_params(self):
        result = json.loads(
            tools.generate_code_snippet("/api/products/{id}/", "put", language="javascript", client="fetch")
        )
        code = result["code"]
        assert "${id}" in code
        assert "data" in code

    def test_snippet_not_found(self):
        result = json.loads(tools.generate_code_snippet("/nonexistent/", "get"))
        assert "error" in result


class TestListSchemas:
    def test_list_schemas(self):
        result = json.loads(tools.list_schemas())
        assert isinstance(result, list)
        assert len(result) == 3
        names = [s["name"] for s in result]
        assert "Product" in names


class TestGetSchemaDetail:
    def test_get_schema(self):
        result = json.loads(tools.get_schema_detail("Product"))
        assert result["name"] == "Product"
        assert "name" in result["properties"]

    def test_get_schema_not_found(self):
        result = json.loads(tools.get_schema_detail("Nonexistent"))
        assert "error" in result


class TestInputValidation:
    def test_invalid_path_no_leading_slash(self):
        result = json.loads(tools.get_endpoint_detail("no-slash", "get"))
        assert "error" in result
        assert "must start with '/'" in result["error"]

    def test_invalid_http_method(self):
        result = json.loads(tools.get_endpoint_detail("/api/test", "INVALID"))
        assert "error" in result
        assert "Invalid HTTP method" in result["error"]

    def test_search_invalid_method(self):
        result = json.loads(tools.search_endpoints("test", method="INVALID"))
        assert "error" in result
        assert "Invalid HTTP method" in result["error"]

    def test_request_example_invalid_path(self):
        result = json.loads(tools.get_request_example("bad-path", "get"))
        assert "error" in result

    def test_response_example_invalid_method(self):
        result = json.loads(tools.get_response_example("/api/test", "BOGUS"))
        assert "error" in result

    def test_code_snippet_invalid_path(self):
        result = json.loads(tools.generate_code_snippet("bad", "get"))
        assert "error" in result


class TestCodeSanitization:
    def test_sanitize_identifier_strips_dangerous_chars(self):
        from drf_mcp_docs.server.tools import _sanitize_identifier

        assert _sanitize_identifier("test`inject") == "test_inject"
        assert _sanitize_identifier("foo'bar") == "foo_bar"
        assert _sanitize_identifier("normal_name") == "normal_name"

    def test_sanitize_string_literal_escapes(self):
        from drf_mcp_docs.server.tools import _sanitize_string_literal

        assert "\\`" in _sanitize_string_literal("test`value")
        assert "\\'" in _sanitize_string_literal("test'value")
        assert "\\${" in _sanitize_string_literal("test${inject}")

    def test_operation_id_with_special_chars(self):
        """Code generation with special chars in operation_id produces safe output."""
        result = json.loads(tools.generate_code_snippet("/api/products/", "get"))
        code = result["code"]
        assert "function " in code
