from drf_mcp_docs.schema.processor import SchemaProcessor
from drf_mcp_docs.schema.types import APIOverview, Endpoint, SchemaDefinition


class TestSchemaProcessorOverview:
    def test_get_overview(self, processor):
        overview = processor.get_overview()
        assert isinstance(overview, APIOverview)
        assert overview.title == "Test API"
        assert overview.description == "A test API for drf-mcp-docs"
        assert overview.version == "1.0.0"
        assert overview.base_url == "https://api.example.com/v1"
        assert overview.endpoint_count == 6  # GET/POST products, GET/PUT/DELETE product, GET categories

    def test_overview_tags(self, processor):
        overview = processor.get_overview()
        tag_names = [t.name for t in overview.tags]
        assert "products" in tag_names
        assert "categories" in tag_names

    def test_overview_auth_methods(self, processor):
        overview = processor.get_overview()
        assert len(overview.auth_methods) == 1
        assert overview.auth_methods[0].name == "bearerAuth"
        assert overview.auth_methods[0].type == "bearer"

    def test_overview_server_without_url_key(self):
        schema = {
            "info": {"title": "Test", "version": "1.0"},
            "servers": [{"description": "no url"}],
            "paths": {},
        }
        proc = SchemaProcessor(schema)
        overview = proc.get_overview()
        assert overview.base_url == ""


class TestSchemaProcessorEndpoints:
    def test_get_all_endpoints(self, processor):
        endpoints = processor.get_endpoints()
        assert len(endpoints) == 6

    def test_get_endpoints_by_tag(self, processor):
        products = processor.get_endpoints(tag="products")
        assert len(products) == 5
        categories = processor.get_endpoints(tag="categories")
        assert len(categories) == 1

    def test_get_single_endpoint(self, processor):
        endpoint = processor.get_endpoint("/api/products/", "get")
        assert endpoint is not None
        assert isinstance(endpoint, Endpoint)
        assert endpoint.method == "GET"
        assert endpoint.operation_id == "products_list"
        assert endpoint.summary == "List all products"

    def test_endpoint_not_found(self, processor):
        endpoint = processor.get_endpoint("/nonexistent/", "get")
        assert endpoint is None

    def test_endpoint_parameters(self, processor):
        endpoint = processor.get_endpoint("/api/products/", "get")
        assert len(endpoint.parameters) == 2
        page_param = next(p for p in endpoint.parameters if p.name == "page")
        assert page_param.location == "query"
        assert page_param.required is False

    def test_endpoint_path_parameters(self, processor):
        endpoint = processor.get_endpoint("/api/products/{id}/", "get")
        id_param = next(p for p in endpoint.parameters if p.name == "id")
        assert id_param.location == "path"
        assert id_param.required is True

    def test_endpoint_request_body(self, processor):
        endpoint = processor.get_endpoint("/api/products/", "post")
        assert endpoint.request_body is not None
        assert endpoint.request_body.required is True
        assert endpoint.request_body.content_type == "application/json"
        assert "properties" in endpoint.request_body.schema

    def test_endpoint_responses(self, processor):
        endpoint = processor.get_endpoint("/api/products/", "post")
        assert "201" in endpoint.responses
        assert "400" in endpoint.responses
        assert endpoint.responses["201"].description == "Created"

    def test_endpoint_auth(self, processor):
        endpoint = processor.get_endpoint("/api/products/", "get")
        assert endpoint.auth_required is True
        assert "bearerAuth" in endpoint.auth_methods

    def test_endpoint_no_auth(self, processor):
        endpoint = processor.get_endpoint("/api/categories/", "get")
        assert endpoint.auth_required is False

    def test_endpoint_deprecated(self, processor):
        endpoint = processor.get_endpoint("/api/products/{id}/", "delete")
        assert endpoint.deprecated is True


class TestSchemaProcessorSchemas:
    def test_get_all_schemas(self, processor):
        schemas = processor.get_schemas()
        assert len(schemas) == 3
        names = [s.name for s in schemas]
        assert "Product" in names
        assert "ProductCreate" in names
        assert "Category" in names

    def test_get_schema_definition(self, processor):
        schema = processor.get_schema_definition("Product")
        assert isinstance(schema, SchemaDefinition)
        assert schema.name == "Product"
        assert schema.type == "object"
        assert "name" in schema.properties
        assert "price" in schema.properties
        assert schema.required == ["name", "price", "category"]

    def test_schema_not_found(self, processor):
        schema = processor.get_schema_definition("NonExistent")
        assert schema is None


class TestSchemaProcessorSearch:
    def test_search_by_keyword(self, processor):
        results = processor.search_endpoints("product")
        assert len(results) == 5

    def test_search_by_method(self, processor):
        results = processor.search_endpoints("product", method="POST")
        assert len(results) == 1
        assert results[0].method == "POST"

    def test_search_by_tag(self, processor):
        results = processor.search_endpoints("list", tag="categories")
        assert len(results) == 1

    def test_search_no_results(self, processor):
        results = processor.search_endpoints("nonexistent_xyz")
        assert len(results) == 0


class TestSchemaProcessorExamples:
    def test_generate_example_from_schema(self, processor):
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "price": {"type": "number"},
                "in_stock": {"type": "boolean"},
            },
        }
        example = processor.generate_example_from_schema(schema)
        assert isinstance(example, dict)
        assert "name" in example
        assert "price" in example
        assert isinstance(example["in_stock"], bool)

    def test_generate_example_with_ref(self, processor):
        schema = {"$ref": "#/components/schemas/ProductCreate"}
        example = processor.generate_example_from_schema(schema)
        assert isinstance(example, dict)
        assert "name" in example
        assert "price" in example

    def test_generate_example_with_enum(self, processor):
        schema = {"type": "string", "enum": ["active", "inactive", "pending"]}
        example = processor.generate_example_from_schema(schema)
        assert example == "active"

    def test_generate_example_with_empty_enum(self, processor):
        schema = {"type": "string", "enum": []}
        result = processor.generate_example_value("status", schema)
        assert result is None

    def test_generate_example_string_formats(self, processor):
        assert processor._string_example("email", "") == "user@example.com"
        assert processor._string_example("x", "date") == "2024-01-15"
        assert processor._string_example("x", "email") == "user@example.com"
        assert processor._string_example("x", "uuid") == "550e8400-e29b-41d4-a716-446655440000"


class TestSchemaProcessorRefResolution:
    def test_resolve_ref_caching(self, processor):
        """resolve_ref caches results for repeated calls."""
        result1 = processor.resolve_ref("#/components/schemas/Product")
        result2 = processor.resolve_ref("#/components/schemas/Product")
        assert result1 == result2
        assert "#/components/schemas/Product" in processor._ref_cache

    def test_resolve_ref(self, processor):
        resolved = processor.resolve_ref("#/components/schemas/Product")
        assert "properties" in resolved
        assert "name" in resolved["properties"]

    def test_resolve_invalid_ref(self, processor):
        resolved = processor.resolve_ref("#/nonexistent/path")
        assert resolved == {}

    def test_resolve_non_hash_ref(self, processor):
        resolved = processor.resolve_ref("external.json#/Foo")
        assert resolved == {}

    def test_resolve_circular_ref(self):
        """Circular $ref chains should not cause RecursionError."""
        schema = {
            "components": {
                "schemas": {
                    "A": {"$ref": "#/components/schemas/B"},
                    "B": {"$ref": "#/components/schemas/A"},
                }
            },
            "info": {"title": "Test", "version": "1.0"},
            "paths": {},
        }
        from drf_mcp_docs.schema.processor import SchemaProcessor

        proc = SchemaProcessor(schema)
        result = proc.resolve_ref("#/components/schemas/A")
        assert isinstance(result, dict)

    def test_resolve_deep_ref_chain(self):
        """Deeply nested $ref chains stop at depth limit."""
        schemas = {}
        for i in range(15):
            schemas[f"Level{i}"] = {"$ref": f"#/components/schemas/Level{i + 1}"}
        schemas["Level15"] = {"type": "object", "properties": {"id": {"type": "integer"}}}
        schema = {
            "components": {"schemas": schemas},
            "info": {"title": "Test", "version": "1.0"},
            "paths": {},
        }
        from drf_mcp_docs.schema.processor import SchemaProcessor

        proc = SchemaProcessor(schema)
        # Default depth=10 should stop before reaching Level15
        result = proc.resolve_ref("#/components/schemas/Level0")
        assert isinstance(result, dict)

    def test_circular_ref_example_generation(self):
        """generate_example_from_schema handles circular refs gracefully."""
        schema = {
            "components": {
                "schemas": {
                    "Node": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "child": {"$ref": "#/components/schemas/Node"},
                        },
                    }
                }
            },
            "info": {"title": "Test", "version": "1.0"},
            "paths": {},
        }
        from drf_mcp_docs.schema.processor import SchemaProcessor

        proc = SchemaProcessor(schema)
        result = proc.generate_example_from_schema({"$ref": "#/components/schemas/Node"})
        assert isinstance(result, dict)
        assert "name" in result


class TestSchemaProcessorEdgeCases:
    def test_schema_with_no_servers(self):
        proc = SchemaProcessor({"info": {"title": "T", "version": "1"}, "paths": {}})
        overview = proc.get_overview()
        assert overview.base_url == ""

    def test_schema_with_no_paths(self):
        proc = SchemaProcessor({"info": {"title": "T", "version": "1"}})
        endpoints = proc.get_endpoints()
        assert endpoints == []

    def test_schema_with_no_components(self):
        proc = SchemaProcessor({"info": {"title": "T", "version": "1"}, "paths": {}})
        schemas = proc.get_schemas()
        assert schemas == []
        assert proc.get_auth_methods() == []

    def test_malformed_operation_non_dict(self):
        proc = SchemaProcessor(
            {
                "info": {"title": "T", "version": "1"},
                "paths": {"/test": {"get": "not-a-dict", "post": {"summary": "ok"}}},
            }
        )
        endpoints = proc.get_endpoints()
        assert len(endpoints) == 1
        assert endpoints[0].method == "POST"

    def test_frozen_dataclass_immutability(self, processor):
        endpoint = processor.get_endpoints()[0]
        with __import__("pytest").raises(AttributeError):
            endpoint.path = "/mutated"
