from __future__ import annotations

import logging

from drf_mcp_docs.adapters.base import BaseSchemaAdapter

logger = logging.getLogger(__name__)


class YasgAdapter(BaseSchemaAdapter):
    """Adapter for drf-yasg (Swagger 2.0 → OpenAPI 3.0 conversion)."""

    @classmethod
    def is_available(cls) -> bool:
        try:
            import drf_yasg  # noqa: F401

            return True
        except ImportError:
            return False

    def get_schema(self) -> dict:
        from drf_yasg import openapi
        from drf_yasg.generators import OpenAPISchemaGenerator

        info = openapi.Info(title="API", default_version="v1")
        generator = OpenAPISchemaGenerator(info=info)
        swagger = generator.get_schema(public=True)
        swagger_dict = swagger.as_odict()
        return self._convert_swagger_to_openapi3(swagger_dict)

    def _convert_swagger_to_openapi3(self, swagger: dict) -> dict:
        """Convert Swagger 2.0 dict to OpenAPI 3.0 structure."""
        openapi_schema = {
            "openapi": "3.0.3",
            "info": dict(swagger.get("info", {})),
            "paths": {},
            "components": {"schemas": {}, "securitySchemes": {}},
        }

        host = swagger.get("host", "localhost")
        base_path = swagger.get("basePath", "/")
        schemes = swagger.get("schemes", ["https"])
        scheme = schemes[0] if schemes else "https"
        openapi_schema["servers"] = [{"url": f"{scheme}://{host}{base_path}"}]

        # Convert definitions → components/schemas
        for name, definition in swagger.get("definitions", {}).items():
            openapi_schema["components"]["schemas"][name] = self._convert_schema(definition, swagger)

        # Convert securityDefinitions → components/securitySchemes
        for name, sec_def in swagger.get("securityDefinitions", {}).items():
            openapi_schema["components"]["securitySchemes"][name] = self._convert_security_scheme(sec_def)

        # Convert paths
        for path, methods in swagger.get("paths", {}).items():
            openapi_schema["paths"][path] = {}
            for method, operation in methods.items():
                if method in ("get", "post", "put", "patch", "delete", "options", "head"):
                    openapi_schema["paths"][path][method] = self._convert_operation(operation, swagger)

        return openapi_schema

    def _convert_schema(self, schema: dict, swagger: dict) -> dict:
        """Convert a Swagger 2.0 schema to OpenAPI 3.0."""
        result = {}
        for key in (
            "type",
            "format",
            "description",
            "enum",
            "default",
            "minimum",
            "maximum",
            "minLength",
            "maxLength",
            "pattern",
            "required",
            "title",
        ):
            if key in schema:
                result[key] = schema[key]

        if "$ref" in schema:
            ref = schema["$ref"]
            result["$ref"] = ref.replace("#/definitions/", "#/components/schemas/")

        if "properties" in schema:
            result["properties"] = {}
            for prop_name, prop_schema in schema["properties"].items():
                result["properties"][prop_name] = self._convert_schema(prop_schema, swagger)

        if "items" in schema:
            result["items"] = self._convert_schema(schema["items"], swagger)

        if "allOf" in schema:
            result["allOf"] = [self._convert_schema(s, swagger) for s in schema["allOf"]]

        return result

    def _convert_security_scheme(self, sec_def: dict) -> dict:
        """Convert Swagger 2.0 security definition to OpenAPI 3.0."""
        sec_type = sec_def.get("type", "")
        if sec_type == "basic":
            return {"type": "http", "scheme": "basic"}
        if sec_type == "apiKey":
            return {
                "type": "apiKey",
                "name": sec_def.get("name", ""),
                "in": sec_def.get("in", "header"),
            }
        if sec_type == "oauth2":
            flow = sec_def.get("flow", "implicit")
            flows = {}
            flow_obj = {}
            if "authorizationUrl" in sec_def:
                flow_obj["authorizationUrl"] = sec_def["authorizationUrl"]
            if "tokenUrl" in sec_def:
                flow_obj["tokenUrl"] = sec_def["tokenUrl"]
            flow_obj["scopes"] = sec_def.get("scopes", {})
            flows[flow] = flow_obj
            return {"type": "oauth2", "flows": flows}
        return {"type": sec_type}

    def _convert_operation(self, operation: dict, swagger: dict) -> dict:
        """Convert a Swagger 2.0 operation to OpenAPI 3.0."""
        result = {}
        for key in ("summary", "description", "operationId", "tags", "deprecated", "security"):
            if key in operation:
                result[key] = operation[key]

        # Convert parameters
        params = []
        request_body_schema = None
        for param in operation.get("parameters", []):
            if param.get("in") == "body":
                schema = param.get("schema", {})
                if "$ref" in schema:
                    schema = {"$ref": schema["$ref"].replace("#/definitions/", "#/components/schemas/")}
                request_body_schema = {
                    "required": param.get("required", False),
                    "content": {"application/json": {"schema": schema}},
                }
            elif param.get("in") == "formData":
                if request_body_schema is None:
                    request_body_schema = {
                        "content": {
                            "application/x-www-form-urlencoded": {"schema": {"type": "object", "properties": {}}}
                        }
                    }
                form_schema = request_body_schema["content"]["application/x-www-form-urlencoded"]["schema"]
                form_schema["properties"][param["name"]] = {
                    k: v for k, v in param.items() if k in ("type", "format", "description", "enum", "default")
                }
            else:
                param_in = param.get("in", "query")
                if param_in not in ("path", "query", "header", "cookie"):
                    logger.warning(
                        "Unknown parameter location '%s' for parameter '%s'",
                        param_in,
                        param.get("name", ""),
                    )
                p = {
                    "name": param.get("name", ""),
                    "in": param_in,
                    "required": param.get("required", False),
                }
                if "description" in param:
                    p["description"] = param["description"]
                p["schema"] = {
                    k: v for k, v in param.items() if k in ("type", "format", "enum", "default", "minimum", "maximum")
                }
                params.append(p)

        if params:
            result["parameters"] = params
        if request_body_schema:
            result["requestBody"] = request_body_schema

        # Convert responses
        if "responses" in operation:
            result["responses"] = {}
            for status, response in operation["responses"].items():
                resp = {"description": response.get("description", "")}
                if "schema" in response:
                    schema = self._convert_schema(response["schema"], swagger)
                    resp["content"] = {"application/json": {"schema": schema}}
                result["responses"][str(status)] = resp

        return result
