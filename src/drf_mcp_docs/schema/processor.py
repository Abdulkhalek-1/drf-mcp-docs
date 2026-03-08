from __future__ import annotations

from drf_mcp_docs.schema.types import (
    APIOverview,
    AuthMethod,
    Endpoint,
    Parameter,
    RequestBody,
    Response,
    SchemaDefinition,
    Tag,
)


class SchemaProcessor:
    """Transforms an OpenAPI 3.x dict into structured, AI-friendly data."""

    def __init__(self, openapi_schema: dict):
        self.schema = openapi_schema

    def resolve_ref(self, ref: str) -> dict:
        """Resolve a $ref pointer like '#/components/schemas/Pet'."""
        if not ref.startswith("#/"):
            return {}
        parts = ref.lstrip("#/").split("/")
        node = self.schema
        for part in parts:
            if isinstance(node, dict):
                node = node.get(part, {})
            else:
                return {}
        return dict(node) if isinstance(node, dict) else {}

    def _resolve_schema(self, schema: dict) -> dict:
        """Resolve a schema, following $ref if present."""
        if "$ref" in schema:
            resolved = self.resolve_ref(schema["$ref"])
            return resolved
        return schema

    def get_overview(self) -> APIOverview:
        info = self.schema.get("info", {})
        servers = self.schema.get("servers", [])
        base_url = servers[0]["url"] if servers else ""

        tags = []
        for tag_info in self.schema.get("tags", []):
            tags.append(
                Tag(
                    name=tag_info.get("name", ""),
                    description=tag_info.get("description", ""),
                )
            )

        # Count endpoints
        endpoint_count = 0
        for methods in self.schema.get("paths", {}).values():
            for method in methods:
                if method.lower() in ("get", "post", "put", "patch", "delete", "options", "head"):
                    endpoint_count += 1

        # If no explicit tags, derive from paths
        if not tags:
            tag_names = set()
            for methods in self.schema.get("paths", {}).values():
                for _method, operation in methods.items():
                    if isinstance(operation, dict):
                        for t in operation.get("tags", []):
                            tag_names.add(t)
            tags = [Tag(name=t) for t in sorted(tag_names)]

        return APIOverview(
            title=info.get("title", ""),
            description=info.get("description", ""),
            version=info.get("version", ""),
            base_url=base_url,
            auth_methods=self.get_auth_methods(),
            tags=tags,
            endpoint_count=endpoint_count,
        )

    def get_auth_methods(self) -> list[AuthMethod]:
        schemes = self.schema.get("components", {}).get("securitySchemes", {})
        result = []
        for name, scheme in schemes.items():
            auth_type = scheme.get("type", "")
            auth = AuthMethod(name=name, type=auth_type)

            if auth_type == "http":
                auth.scheme = scheme.get("scheme", "")
                if auth.scheme == "bearer":
                    auth.type = "bearer"
                    auth.description = f"Bearer token ({scheme.get('bearerFormat', 'JWT')})"
                else:
                    auth.type = auth.scheme
                    auth.description = f"HTTP {auth.scheme} authentication"
            elif auth_type == "apiKey":
                auth.header_name = scheme.get("name", "")
                location = scheme.get("in", "header")
                auth.description = f"API key in {location}: {auth.header_name}"
            elif auth_type == "oauth2":
                auth.description = "OAuth 2.0"
            else:
                auth.description = scheme.get("description", auth_type)

            result.append(auth)
        return result

    def get_endpoints(self, tag: str | None = None) -> list[Endpoint]:
        endpoints = []
        for path, methods in self.schema.get("paths", {}).items():
            for method, operation in methods.items():
                if method.lower() not in ("get", "post", "put", "patch", "delete", "options", "head"):
                    continue
                if not isinstance(operation, dict):
                    continue
                if tag and tag not in operation.get("tags", []):
                    continue
                endpoints.append(self._parse_endpoint(path, method, operation))
        return endpoints

    def get_endpoint(self, path: str, method: str) -> Endpoint | None:
        method = method.lower()
        path_data = self.schema.get("paths", {}).get(path, {})
        operation = path_data.get(method)
        if not operation or not isinstance(operation, dict):
            return None
        return self._parse_endpoint(path, method, operation)

    def _parse_endpoint(self, path: str, method: str, operation: dict) -> Endpoint:
        # Parse parameters
        parameters = []
        for param in operation.get("parameters", []):
            parameters.append(
                Parameter(
                    name=param.get("name", ""),
                    location=param.get("in", "query"),
                    required=param.get("required", False),
                    schema=self._resolve_schema(param.get("schema", {})),
                    description=param.get("description", ""),
                )
            )

        # Parse request body
        request_body = None
        rb = operation.get("requestBody")
        if rb and isinstance(rb, dict):
            content = rb.get("content", {})
            for content_type, media in content.items():
                schema = self._resolve_schema(media.get("schema", {}))
                request_body = RequestBody(
                    content_type=content_type,
                    schema=schema,
                    required=rb.get("required", False),
                    example=media.get("example") or schema.get("example"),
                )
                break  # Take first content type

        # Parse responses
        responses = {}
        for status_code, resp_data in operation.get("responses", {}).items():
            schema = None
            example = None
            content = resp_data.get("content", {})
            for _ct, media in content.items():
                schema = self._resolve_schema(media.get("schema", {}))
                example = media.get("example") or (schema.get("example") if schema else None)
                break
            responses[str(status_code)] = Response(
                status_code=str(status_code),
                description=resp_data.get("description", ""),
                schema=schema,
                example=example,
            )

        # Determine auth
        security = operation.get("security", self.schema.get("security", []))
        auth_methods = []
        for sec_req in security:
            auth_methods.extend(sec_req.keys())
        auth_required = bool(auth_methods)

        return Endpoint(
            path=path,
            method=method.upper(),
            operation_id=operation.get("operationId", ""),
            summary=operation.get("summary", ""),
            description=operation.get("description", ""),
            tags=operation.get("tags", []),
            parameters=parameters,
            request_body=request_body,
            responses=responses,
            auth_required=auth_required,
            auth_methods=auth_methods,
            deprecated=operation.get("deprecated", False),
        )

    def get_schemas(self) -> list[SchemaDefinition]:
        schemas = self.schema.get("components", {}).get("schemas", {})
        result = []
        for name, schema_data in schemas.items():
            result.append(self._parse_schema_definition(name, schema_data))
        return result

    def get_schema_definition(self, name: str) -> SchemaDefinition | None:
        schemas = self.schema.get("components", {}).get("schemas", {})
        schema_data = schemas.get(name)
        if schema_data is None:
            return None
        return self._parse_schema_definition(name, schema_data)

    def _parse_schema_definition(self, name: str, schema_data: dict) -> SchemaDefinition:
        properties = {}
        for prop_name, prop_data in schema_data.get("properties", {}).items():
            resolved = self._resolve_schema(prop_data)
            properties[prop_name] = {
                "type": resolved.get("type", ""),
                "format": resolved.get("format", ""),
                "description": resolved.get("description", ""),
                "nullable": resolved.get("nullable", False),
                "readOnly": resolved.get("readOnly", False),
                "enum": resolved.get("enum"),
            }
            # Clean up None/empty values
            properties[prop_name] = {k: v for k, v in properties[prop_name].items() if v}

        return SchemaDefinition(
            name=name,
            type=schema_data.get("type", "object"),
            properties=properties,
            required=schema_data.get("required", []),
            description=schema_data.get("description", ""),
        )

    def search_endpoints(
        self,
        query: str,
        method: str | None = None,
        tag: str | None = None,
    ) -> list[Endpoint]:
        """Search endpoints by keyword in path, summary, description, or operationId."""
        query_lower = query.lower()
        results = []
        for endpoint in self.get_endpoints(tag=tag):
            if method and endpoint.method.upper() != method.upper():
                continue
            searchable = " ".join(
                [
                    endpoint.path,
                    endpoint.summary,
                    endpoint.description,
                    endpoint.operation_id,
                    " ".join(endpoint.tags),
                ]
            ).lower()
            if query_lower in searchable:
                results.append(endpoint)
        return results

    def generate_example_from_schema(self, schema: dict) -> dict | list | str | None:
        """Generate an example value from a JSON schema."""
        if "example" in schema:
            return schema["example"]

        if "$ref" in schema:
            resolved = self.resolve_ref(schema["$ref"])
            return self.generate_example_from_schema(resolved)

        schema_type = schema.get("type", "object")

        if schema_type == "object":
            result = {}
            for prop_name, prop_schema in schema.get("properties", {}).items():
                if prop_schema.get("readOnly"):
                    continue
                result[prop_name] = self._generate_example_value(prop_name, prop_schema)
            return result

        if schema_type == "array":
            items = schema.get("items", {})
            return [self.generate_example_from_schema(items)]

        return self._generate_example_value("value", schema)

    def _generate_example_value(self, name: str, schema: dict):
        """Generate a plausible example value for a single field."""
        if "example" in schema:
            return schema["example"]
        if "default" in schema:
            return schema["default"]
        if "enum" in schema:
            return schema["enum"][0]

        if "$ref" in schema:
            resolved = self.resolve_ref(schema["$ref"])
            return self.generate_example_from_schema(resolved)

        field_type = schema.get("type", "string")
        fmt = schema.get("format", "")

        type_examples = {
            "integer": 1,
            "number": 1.0,
            "boolean": True,
            "string": self._string_example(name, fmt),
        }

        if field_type == "array":
            items = schema.get("items", {})
            return [self._generate_example_value(name, items)]

        if field_type == "object":
            return self.generate_example_from_schema(schema)

        return type_examples.get(field_type, "string")

    def _string_example(self, name: str, fmt: str) -> str:
        format_examples = {
            "date": "2024-01-15",
            "date-time": "2024-01-15T10:30:00Z",
            "email": "user@example.com",
            "uri": "https://example.com",
            "url": "https://example.com",
            "uuid": "550e8400-e29b-41d4-a716-446655440000",
            "ipv4": "192.168.1.1",
            "ipv6": "::1",
        }
        if fmt in format_examples:
            return format_examples[fmt]

        name_lower = name.lower()
        name_examples = {
            "email": "user@example.com",
            "name": "Example Name",
            "title": "Example Title",
            "description": "A description",
            "url": "https://example.com",
            "phone": "+1234567890",
            "password": "SecurePass123!",
            "username": "johndoe",
            "slug": "example-slug",
        }
        for key, val in name_examples.items():
            if key in name_lower:
                return val

        return "string"
