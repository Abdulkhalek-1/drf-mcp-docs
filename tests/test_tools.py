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
        assert len(result) == 8

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
    # --- Existing tests (updated) ---

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

    # --- TypeScript interface tests ---

    def test_typescript_generates_request_interface(self):
        result = json.loads(
            tools.generate_code_snippet("/api/products/", "post", language="typescript", client="fetch")
        )
        code = result["code"]
        # Should have a real interface for the request body (ProductCreate schema)
        assert "interface" in code
        assert "name: string" in code or "name:" in code
        assert "price: number" in code or "price:" in code

    def test_typescript_generates_response_interface(self):
        result = json.loads(
            tools.generate_code_snippet("/api/products/{id}/", "get", language="typescript", client="fetch")
        )
        code = result["code"]
        # Should have a Product interface from the response schema
        assert "interface" in code
        assert "Product" in code

    def test_typescript_return_type(self):
        result = json.loads(tools.generate_code_snippet("/api/products/", "get", language="typescript", client="fetch"))
        code = result["code"]
        assert "Promise<" in code

    def test_query_params_typed(self):
        result = json.loads(tools.generate_code_snippet("/api/products/", "get", language="typescript", client="fetch"))
        code = result["code"]
        # Should generate a query params interface
        assert "Params" in code
        assert "page" in code
        assert "category" in code

    # --- JSDoc tests ---

    def test_jsdoc_included(self):
        result = json.loads(tools.generate_code_snippet("/api/products/", "get", language="javascript", client="fetch"))
        code = result["code"]
        assert "/**" in code
        assert "List all products" in code

    def test_deprecated_warning_in_jsdoc(self):
        result = json.loads(
            tools.generate_code_snippet("/api/products/{id}/", "delete", language="javascript", client="fetch")
        )
        code = result["code"]
        assert "@deprecated" in code

    # --- Import statement tests ---

    def test_import_statement_axios(self):
        result = json.loads(tools.generate_code_snippet("/api/products/", "get", language="javascript", client="axios"))
        code = result["code"]
        assert "import axios from 'axios'" in code

    def test_import_statement_ky(self):
        result = json.loads(tools.generate_code_snippet("/api/products/", "get", language="javascript", client="ky"))
        code = result["code"]
        assert "import ky from 'ky'" in code

    # --- Usage example tests ---

    def test_usage_example_included(self):
        result = json.loads(tools.generate_code_snippet("/api/products/", "get", language="javascript", client="fetch"))
        code = result["code"]
        assert "// Usage:" in code

    # --- Base URL tests ---

    def test_base_url_from_spec(self):
        result = json.loads(tools.generate_code_snippet("/api/products/", "get", language="javascript", client="fetch"))
        code = result["code"]
        assert "BASE_URL" in code
        assert "https://api.example.com/v1" in code

    # --- Auth tests ---

    def test_bearer_auth_header(self):
        result = json.loads(tools.generate_code_snippet("/api/products/", "get", language="javascript", client="fetch"))
        code = result["code"]
        assert "Bearer" in code
        assert "token" in code

    def test_no_auth_endpoint(self):
        result = json.loads(
            tools.generate_code_snippet("/api/categories/", "get", language="javascript", client="fetch")
        )
        code = result["code"]
        assert "Authorization" not in code
        assert result["metadata"]["auth"]["required"] is False

    def test_apikey_auth_header(self):
        result = json.loads(
            tools.generate_code_snippet("/api/categories/{slug}/", "get", language="javascript", client="fetch")
        )
        code = result["code"]
        assert "X-API-Key" in code

    # --- Enriched output metadata tests ---

    def test_enriched_output_metadata(self):
        result = json.loads(tools.generate_code_snippet("/api/products/", "get", language="javascript", client="fetch"))
        assert "metadata" in result
        meta = result["metadata"]
        assert "function_name" in meta
        assert meta["function_name"] == "productsList"
        assert meta["endpoint"]["path"] == "/api/products/"
        assert meta["endpoint"]["method"] == "GET"
        assert meta["endpoint"]["summary"] == "List all products"
        assert meta["endpoint"]["deprecated"] is False
        assert meta["auth"]["required"] is True
        assert len(meta["auth"]["methods"]) > 0
        assert meta["auth"]["methods"][0]["type"] == "bearer"
        assert len(meta["parameters"]["query"]) == 2
        assert meta["response"]["success_status"] == "200"

    def test_metadata_deprecated_endpoint(self):
        result = json.loads(
            tools.generate_code_snippet("/api/products/{id}/", "delete", language="javascript", client="fetch")
        )
        assert result["metadata"]["endpoint"]["deprecated"] is True

    def test_metadata_path_params(self):
        result = json.loads(
            tools.generate_code_snippet("/api/products/{id}/", "get", language="javascript", client="fetch")
        )
        path_params = result["metadata"]["parameters"]["path"]
        assert len(path_params) == 1
        assert path_params[0]["name"] == "id"
        assert path_params[0]["type"] == "integer"

    # --- Python tests ---

    def test_requests_snippet(self):
        result = json.loads(tools.generate_code_snippet("/api/products/", "get", language="python", client="requests"))
        assert result["client"] == "requests"
        code = result["code"]
        assert "import requests" in code
        assert "def products_list" in code
        assert "requests.get" in code
        assert "response.raise_for_status()" in code
        assert "response.json()" in code

    def test_httpx_snippet(self):
        result = json.loads(tools.generate_code_snippet("/api/products/", "get", language="python", client="httpx"))
        assert result["client"] == "httpx"
        code = result["code"]
        assert "import httpx" in code
        assert "async def products_list" in code
        assert "httpx.AsyncClient" in code
        assert "await" in code

    def test_python_type_hints(self):
        result = json.loads(
            tools.generate_code_snippet("/api/products/{id}/", "get", language="python", client="requests")
        )
        code = result["code"]
        assert "id: int" in code

    def test_python_typeddict_for_request_body(self):
        result = json.loads(tools.generate_code_snippet("/api/products/", "post", language="python", client="requests"))
        code = result["code"]
        assert "TypedDict" in code
        assert "name: str" in code

    def test_python_docstring(self):
        result = json.loads(tools.generate_code_snippet("/api/products/", "get", language="python", client="requests"))
        code = result["code"]
        assert '"""' in code
        assert "List all products" in code

    def test_python_usage_example(self):
        result = json.loads(tools.generate_code_snippet("/api/products/", "get", language="python", client="requests"))
        code = result["code"]
        assert "# Usage:" in code

    def test_python_base_url(self):
        result = json.loads(tools.generate_code_snippet("/api/products/", "get", language="python", client="requests"))
        code = result["code"]
        assert "https://api.example.com/v1" in code

    def test_python_bearer_auth(self):
        result = json.loads(tools.generate_code_snippet("/api/products/", "get", language="python", client="requests"))
        code = result["code"]
        assert "Bearer" in code
        assert "token" in code

    def test_python_auto_selects_client(self):
        """When language is python but client is fetch, auto-selects requests."""
        result = json.loads(tools.generate_code_snippet("/api/products/", "get", language="python", client="fetch"))
        assert result["client"] == "requests"

    def test_python_snake_case_function_name(self):
        result = json.loads(tools.generate_code_snippet("/api/products/", "get", language="python", client="requests"))
        assert result["metadata"]["function_name"] == "products_list"

    def test_httpx_async_usage_example(self):
        result = json.loads(tools.generate_code_snippet("/api/products/", "get", language="python", client="httpx"))
        code = result["code"]
        assert "# Usage:" in code
        assert "await" in code


class TestListSchemas:
    def test_list_schemas(self):
        result = json.loads(tools.list_schemas())
        assert isinstance(result, list)
        assert len(result) == 6
        names = [s["name"] for s in result]
        assert "Product" in names

    def test_list_schemas_only_name_and_description(self):
        result = json.loads(tools.list_schemas())
        for schema in result:
            assert set(schema.keys()) == {"name", "description"}


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


class TestPaginationDetection:
    def test_detects_page_number_pagination(self):
        result = json.loads(
            tools.generate_code_snippet("/api/products/paginated/", "get", language="javascript", client="fetch")
        )
        meta = result["metadata"]["pagination"]
        assert meta is not None
        assert meta["style"] == "page_number"
        assert meta["has_count"] is True
        assert meta["results_field"] == "results"

    def test_detects_limit_offset_pagination(self):
        result = json.loads(
            tools.generate_code_snippet("/api/products/offset/", "get", language="javascript", client="fetch")
        )
        meta = result["metadata"]["pagination"]
        assert meta is not None
        assert meta["style"] == "limit_offset"
        assert meta["has_count"] is True

    def test_detects_cursor_pagination(self):
        result = json.loads(
            tools.generate_code_snippet("/api/products/cursor/", "get", language="javascript", client="fetch")
        )
        meta = result["metadata"]["pagination"]
        assert meta is not None
        assert meta["style"] == "cursor"
        assert meta["has_count"] is False

    def test_no_pagination_for_non_paginated_endpoint(self):
        result = json.loads(
            tools.generate_code_snippet("/api/categories/", "get", language="javascript", client="fetch")
        )
        assert result["metadata"]["pagination"] is None

    def test_no_pagination_for_post_endpoint(self):
        result = json.loads(
            tools.generate_code_snippet("/api/products/", "post", language="javascript", client="fetch")
        )
        assert result["metadata"]["pagination"] is None


class TestPaginationCodeGeneration:
    def test_fetch_pagination_helper(self):
        result = json.loads(
            tools.generate_code_snippet("/api/products/paginated/", "get", language="javascript", client="fetch")
        )
        code = result["code"]
        assert "async function* fetchAll" in code
        assert "yield*" in code

    def test_axios_pagination_helper(self):
        result = json.loads(
            tools.generate_code_snippet("/api/products/paginated/", "get", language="javascript", client="axios")
        )
        code = result["code"]
        assert "async function* fetchAll" in code

    def test_requests_pagination_helper(self):
        result = json.loads(
            tools.generate_code_snippet("/api/products/paginated/", "get", language="python", client="requests")
        )
        code = result["code"]
        assert "def fetch_all_" in code
        assert "yield from" in code

    def test_httpx_pagination_helper_async(self):
        result = json.loads(
            tools.generate_code_snippet("/api/products/paginated/", "get", language="python", client="httpx")
        )
        code = result["code"]
        assert "async def fetch_all_" in code
        assert "yield item" in code

    def test_no_pagination_helper_for_non_paginated(self):
        result = json.loads(
            tools.generate_code_snippet("/api/categories/", "get", language="javascript", client="fetch")
        )
        code = result["code"]
        assert "fetchAll" not in code

    def test_cursor_pagination_follows_next_url(self):
        result = json.loads(
            tools.generate_code_snippet("/api/products/cursor/", "get", language="javascript", client="fetch")
        )
        code = result["code"]
        assert "data.next" in code

    def test_limit_offset_pagination(self):
        result = json.loads(
            tools.generate_code_snippet("/api/products/offset/", "get", language="python", client="requests")
        )
        code = result["code"]
        assert "offset" in code
        assert "limit" in code


class TestCurlSnippet:
    def test_curl_get_basic(self):
        result = json.loads(tools.generate_code_snippet("/api/categories/", "get", language="curl"))
        assert result["language"] == "curl"
        assert result["client"] == "curl"
        code = result["code"]
        assert "curl -X GET" in code
        assert "/api/categories/" in code

    def test_curl_post_with_body(self):
        result = json.loads(tools.generate_code_snippet("/api/products/", "post", language="curl"))
        code = result["code"]
        assert "-X POST" in code
        assert "-d " in code
        assert "Content-Type: application/json" in code

    def test_curl_with_path_params(self):
        result = json.loads(tools.generate_code_snippet("/api/products/{id}/", "get", language="curl"))
        code = result["code"]
        # Path params should be substituted in the curl URL (not in comment lines)
        for line in code.splitlines():
            if line.startswith("curl") or line.strip().startswith("'http"):
                assert "{id}" not in line

    def test_curl_with_bearer_auth(self):
        result = json.loads(tools.generate_code_snippet("/api/products/", "get", language="curl"))
        code = result["code"]
        assert "Authorization: Bearer YOUR_TOKEN" in code

    def test_curl_with_apikey_auth(self):
        result = json.loads(tools.generate_code_snippet("/api/categories/{slug}/", "get", language="curl"))
        code = result["code"]
        assert "X-API-Key: YOUR_API_KEY" in code

    def test_curl_delete(self):
        result = json.loads(tools.generate_code_snippet("/api/products/{id}/", "delete", language="curl"))
        code = result["code"]
        assert "-X DELETE" in code

    def test_curl_metadata(self):
        result = json.loads(tools.generate_code_snippet("/api/products/", "get", language="curl"))
        assert result["language"] == "curl"
        assert result["client"] == "curl"
        assert "metadata" in result

    def test_curl_aliases(self):
        for lang in ("shell", "sh", "bash"):
            result = json.loads(tools.generate_code_snippet("/api/products/", "get", language=lang))
            assert result["client"] == "curl"

    def test_curl_no_auth_endpoint(self):
        result = json.loads(tools.generate_code_snippet("/api/categories/", "get", language="curl"))
        code = result["code"]
        assert "Authorization" not in code

    def test_curl_deprecated_endpoint(self):
        result = json.loads(tools.generate_code_snippet("/api/products/{id}/", "delete", language="curl"))
        code = result["code"]
        assert "deprecated" in code.lower()

    def test_curl_pagination_comment(self):
        result = json.loads(tools.generate_code_snippet("/api/products/paginated/", "get", language="curl"))
        code = result["code"]
        assert "Pagination" in code
