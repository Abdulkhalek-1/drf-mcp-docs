from __future__ import annotations

import json
import re
from dataclasses import asdict

from mcp.server.fastmcp import FastMCP

from drf_mcp_docs.server.instance import get_processor
from drf_mcp_docs.settings import get_setting

_VALID_HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"}


def _validate_inputs(path: str, method: str) -> str | None:
    """Return an error JSON string if inputs are invalid, else None."""
    if not path.startswith("/"):
        return json.dumps({"error": f"Invalid path '{path}': must start with '/'"})
    if method.upper() not in _VALID_HTTP_METHODS:
        return json.dumps({"error": f"Invalid HTTP method '{method}'"})
    return None


def search_endpoints(
    query: str,
    method: str | None = None,
    tag: str | None = None,
) -> str:
    """Search API endpoints by keyword. Matches path, summary, description, and operationId."""
    if method and method.upper() not in _VALID_HTTP_METHODS:
        return json.dumps({"error": f"Invalid HTTP method '{method}'"})
    processor = get_processor()
    results = processor.search_endpoints(query, method=method, tag=tag)
    compact = [
        {
            "path": ep.path,
            "method": ep.method,
            "summary": ep.summary,
            "tags": ep.tags,
        }
        for ep in results
    ]
    if not compact:
        return json.dumps({"message": f"No endpoints found matching '{query}'"})
    return json.dumps(compact, indent=2)


def get_endpoint_detail(path: str, method: str) -> str:
    """Get full documentation for a specific endpoint including parameters, request body, responses, and auth."""
    if err := _validate_inputs(path, method):
        return err
    processor = get_processor()
    endpoint = processor.get_endpoint(path, method)
    if endpoint is None:
        return json.dumps({"error": f"Endpoint {method.upper()} {path} not found"})
    return json.dumps(asdict(endpoint), indent=2, default=str)


def get_request_example(
    path: str,
    method: str,
) -> str:
    """Generate an example request for an endpoint (body and/or parameters)."""
    if err := _validate_inputs(path, method):
        return err
    processor = get_processor()
    endpoint = processor.get_endpoint(path, method)
    if endpoint is None:
        return json.dumps({"error": f"Endpoint {method.upper()} {path} not found"})

    result: dict = {"method": endpoint.method, "path": endpoint.path}

    if endpoint.parameters:
        params = {}
        for p in endpoint.parameters:
            params[p.name] = processor.generate_example_value(p.name, p.schema)
        result["parameters"] = params

    if endpoint.request_body:
        body = processor.generate_example_from_schema(endpoint.request_body.schema)
        result["body"] = body
        result["content_type"] = endpoint.request_body.content_type

    return json.dumps(result, indent=2, default=str)


def get_response_example(
    path: str,
    method: str,
    status_code: str = "200",
) -> str:
    """Generate an example response for an endpoint."""
    if err := _validate_inputs(path, method):
        return err
    processor = get_processor()
    endpoint = processor.get_endpoint(path, method)
    if endpoint is None:
        return json.dumps({"error": f"Endpoint {method.upper()} {path} not found"})

    response = endpoint.responses.get(status_code)
    if response is None:
        for code in ("200", "201", "204"):
            if code in endpoint.responses:
                response = endpoint.responses[code]
                break

    if response is None:
        return json.dumps({"message": f"No response definition for status {status_code}"})

    result = {
        "status_code": response.status_code,
        "description": response.description,
    }
    if response.example:
        result["example"] = response.example
    elif response.schema:
        result["example"] = processor.generate_example_from_schema(response.schema)

    return json.dumps(result, indent=2, default=str)


def generate_code_snippet(
    path: str,
    method: str,
    language: str = "",
    client: str = "",
) -> str:
    """Generate a frontend code snippet for calling an API endpoint.

    Supported languages: javascript, typescript
    Supported clients: fetch, axios, ky
    """
    if err := _validate_inputs(path, method):
        return err

    lang = language or get_setting("DEFAULT_CODE_LANGUAGE")
    http_client = client or get_setting("DEFAULT_HTTP_CLIENT")

    processor = get_processor()
    endpoint = processor.get_endpoint(path, method)
    if endpoint is None:
        return json.dumps({"error": f"Endpoint {method.upper()} {path} not found"})

    generators = {
        "fetch": _generate_fetch_snippet,
        "axios": _generate_axios_snippet,
        "ky": _generate_ky_snippet,
    }
    generator = generators.get(http_client, _generate_fetch_snippet)
    use_ts = lang.lower() in ("typescript", "ts")

    code = generator(endpoint, processor, use_typescript=use_ts)
    return json.dumps({"language": lang, "client": http_client, "code": code})


def list_schemas() -> str:
    """List all data model schemas with their names, types, and field counts."""
    processor = get_processor()
    schemas = processor.get_schemas()
    result = [
        {
            "name": s.name,
            "type": s.type,
            "field_count": len(s.properties),
            "required_fields": s.required,
            "description": s.description,
        }
        for s in schemas
    ]
    return json.dumps(result, indent=2)


def get_schema_detail(name: str) -> str:
    """Get full details of a data model schema including all properties, types, and constraints."""
    processor = get_processor()
    schema = processor.get_schema_definition(name)
    if schema is None:
        return json.dumps({"error": f"Schema '{name}' not found"})
    return json.dumps(asdict(schema), indent=2, default=str)


def register_tools(mcp: FastMCP):
    mcp.tool()(search_endpoints)
    mcp.tool()(get_endpoint_detail)
    mcp.tool()(get_request_example)
    mcp.tool()(get_response_example)
    mcp.tool()(generate_code_snippet)
    mcp.tool()(list_schemas)
    mcp.tool()(get_schema_detail)


# --- Code snippet generators ---


def _sanitize_identifier(value: str) -> str:
    """Sanitize a value for use as a JS/TS identifier."""
    return re.sub(r"[^a-zA-Z0-9_$]", "_", value)


def _sanitize_string_literal(value: str) -> str:
    """Escape a value for safe inclusion in a JS string literal."""
    return (
        value.replace("\\", "\\\\").replace("'", "\\'").replace("`", "\\`").replace("${", "\\${").replace("\n", "\\n")
    )


def _build_path_with_params(endpoint) -> str:
    path = endpoint.path
    path_params = [p for p in endpoint.parameters if p.location == "path"]
    if path_params:
        for p in path_params:
            safe_name = _sanitize_identifier(p.name)
            path = path.replace(f"{{{p.name}}}", f"${{{safe_name}}}")
        return f"`{path}`"
    return f"'{_sanitize_string_literal(endpoint.path)}'"


def _get_query_params(endpoint) -> list:
    return [p for p in endpoint.parameters if p.location == "query"]


def _operation_to_func_name(endpoint) -> str:
    if endpoint.operation_id:
        parts = endpoint.operation_id.replace("-", "_").split("_")
        name = parts[0].lower() + "".join(p.capitalize() for p in parts[1:])
        return _sanitize_identifier(name)
    method = endpoint.method.lower()
    segments = [s for s in endpoint.path.split("/") if s and not s.startswith("{")]
    return _sanitize_identifier(method + "".join(s.capitalize() for s in segments))


def _schema_to_ts_type(schema: dict) -> str:
    type_map = {
        "integer": "number",
        "number": "number",
        "string": "string",
        "boolean": "boolean",
        "array": "any[]",
        "object": "Record<string, any>",
    }
    return type_map.get(schema.get("type", "string"), "any")


def _generate_fetch_snippet(endpoint, processor, use_typescript: bool = False) -> str:
    lines = []
    path_expr = _build_path_with_params(endpoint)
    method = endpoint.method.upper()
    has_body = endpoint.request_body is not None
    query_params = _get_query_params(endpoint)
    path_params = [p for p in endpoint.parameters if p.location == "path"]

    func_name = _operation_to_func_name(endpoint)
    params = []

    if use_typescript:
        if path_params:
            for p in path_params:
                ts_type = _schema_to_ts_type(p.schema)
                params.append(f"{_sanitize_identifier(p.name)}: {ts_type}")
        if has_body:
            params.append("data: RequestData")
        if query_params:
            params.append("params?: QueryParams")
        sig = f"async function {func_name}({', '.join(params)})" + " {"
    else:
        if path_params:
            params.extend(_sanitize_identifier(p.name) for p in path_params)
        if has_body:
            params.append("data")
        if query_params:
            params.append("params = {}")
        sig = f"async function {func_name}({', '.join(params)})" + " {"

    lines.append(sig)

    if query_params:
        lines.append("  const queryString = new URLSearchParams(params).toString();")
        lines.append(f"  const url = {path_expr} + (queryString ? `?${{queryString}}` : '');")
    else:
        lines.append(f"  const url = {path_expr};")

    lines.append("")
    lines.append("  const response = await fetch(url, {")
    lines.append(f"    method: '{method}',")

    headers = ["'Content-Type': 'application/json'"] if has_body else []
    if endpoint.auth_required:
        headers.append("'Authorization': `Bearer ${token}`")
    if headers:
        lines.append("    headers: {")
        for h in headers:
            lines.append(f"      {h},")
        lines.append("    },")

    if has_body:
        lines.append("    body: JSON.stringify(data),")

    lines.append("  });")
    lines.append("")
    lines.append("  if (!response.ok) {")
    lines.append("    throw new Error(`HTTP ${response.status}: ${response.statusText}`);")
    lines.append("  }")
    lines.append("")
    if method == "DELETE":
        lines.append("  return response;")
    else:
        lines.append("  return response.json();")
    lines.append("}")

    return "\n".join(lines)


def _generate_axios_snippet(endpoint, processor, use_typescript: bool = False) -> str:
    lines = []
    path_expr = _build_path_with_params(endpoint)
    method = endpoint.method.lower()
    has_body = endpoint.request_body is not None
    query_params = _get_query_params(endpoint)
    path_params = [p for p in endpoint.parameters if p.location == "path"]

    func_name = _operation_to_func_name(endpoint)
    params = []

    if use_typescript:
        if path_params:
            for p in path_params:
                ts_type = _schema_to_ts_type(p.schema)
                params.append(f"{_sanitize_identifier(p.name)}: {ts_type}")
        if has_body:
            params.append("data: RequestData")
        if query_params:
            params.append("params?: QueryParams")
        sig = f"async function {func_name}({', '.join(params)})" + " {"
    else:
        if path_params:
            params.extend(_sanitize_identifier(p.name) for p in path_params)
        if has_body:
            params.append("data")
        if query_params:
            params.append("params = {}")
        sig = f"async function {func_name}({', '.join(params)})" + " {"

    lines.append(sig)
    lines.append(f"  const response = await axios.{method}({path_expr}")

    if has_body and method in ("post", "put", "patch"):
        lines[-1] += ", data"

    config_parts = []
    if query_params:
        config_parts.append("params")
    if endpoint.auth_required:
        config_parts.append("headers: { Authorization: `Bearer ${token}` }")

    if config_parts:
        lines[-1] += ", { " + ", ".join(config_parts) + " }"

    lines[-1] += ");"
    lines.append("  return response.data;")
    lines.append("}")

    return "\n".join(lines)


def _generate_ky_snippet(endpoint, processor, use_typescript: bool = False) -> str:
    lines = []
    method = endpoint.method.lower()
    has_body = endpoint.request_body is not None
    query_params = _get_query_params(endpoint)
    path_params = [p for p in endpoint.parameters if p.location == "path"]
    path_expr = _build_path_with_params(endpoint)

    func_name = _operation_to_func_name(endpoint)
    params = []

    if use_typescript:
        if path_params:
            for p in path_params:
                ts_type = _schema_to_ts_type(p.schema)
                params.append(f"{_sanitize_identifier(p.name)}: {ts_type}")
        if has_body:
            params.append("data: RequestData")
        if query_params:
            params.append("params?: QueryParams")
        sig = f"async function {func_name}({', '.join(params)})" + " {"
    else:
        if path_params:
            params.extend(_sanitize_identifier(p.name) for p in path_params)
        if has_body:
            params.append("data")
        if query_params:
            params.append("params = {}")
        sig = f"async function {func_name}({', '.join(params)})" + " {"

    lines.append(sig)

    opts = []
    if has_body:
        opts.append("json: data")
    if query_params:
        opts.append("searchParams: params")
    if endpoint.auth_required:
        opts.append("headers: { Authorization: `Bearer ${token}` }")

    if opts:
        lines.append(f"  const response = await ky.{method}({path_expr}, {{")
        for opt in opts:
            lines.append(f"    {opt},")
        lines.append("  }).json();")
    else:
        lines.append(f"  const response = await ky.{method}({path_expr}).json();")

    lines.append("  return response;")
    lines.append("}")

    return "\n".join(lines)
