from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict

from mcp.server.fastmcp import FastMCP

from drf_mcp_docs.schema.types import PaginationInfo
from drf_mcp_docs.server.instance import get_processor
from drf_mcp_docs.settings import get_setting

logger = logging.getLogger(__name__)

_VALID_HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"}


def _validate_inputs(path: str, method: str) -> str | None:
    """Return an error JSON string if inputs are invalid, else None."""
    if not path.startswith("/"):
        logger.debug("Input validation failed: invalid path '%s'", path)
        return json.dumps({"error": f"Invalid path '{path}': must start with '/'"})
    if method.upper() not in _VALID_HTTP_METHODS:
        logger.debug("Input validation failed: invalid method '%s'", method)
        return json.dumps({"error": f"Invalid HTTP method '{method}'"})
    return None


def search_endpoints(
    query: str,
    method: str | None = None,
    tag: str | None = None,
) -> str:
    """Search API endpoints by keyword. Matches path, summary, description, and operationId."""
    logger.debug("Tool search_endpoints: query=%r method=%r tag=%r", query, method, tag)
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
    logger.debug("search_endpoints: %d result(s)", len(compact))
    if not compact:
        return json.dumps({"message": f"No endpoints found matching '{query}'"})
    return json.dumps(compact, indent=2)


def get_endpoint_detail(path: str, method: str) -> str:
    """Get full documentation for a specific endpoint including parameters, request body, responses, and auth."""
    logger.debug("Tool get_endpoint_detail: %s %s", method, path)
    if err := _validate_inputs(path, method):
        return err
    processor = get_processor()
    endpoint = processor.get_endpoint(path, method)
    if endpoint is None:
        logger.debug("get_endpoint_detail: not found")
        return json.dumps({"error": f"Endpoint {method.upper()} {path} not found"})
    logger.debug("get_endpoint_detail: found")
    return json.dumps(asdict(endpoint), indent=2, default=str)


def get_request_example(
    path: str,
    method: str,
) -> str:
    """Generate an example request for an endpoint (body and/or parameters)."""
    logger.debug("Tool get_request_example: %s %s", method, path)
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
    logger.debug("Tool get_response_example: %s %s status=%s", method, path, status_code)
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
    """Generate a ready-to-use code snippet for calling an API endpoint.

    Produces self-documenting code with real types, proper auth handling, and usage examples.

    Supported languages: javascript, typescript, python, curl
    Supported clients: fetch, axios, ky (JS/TS) | requests, httpx (Python) | curl
    """
    logger.debug("Tool generate_code_snippet: %s %s lang=%r client=%r", method, path, language, client)
    if err := _validate_inputs(path, method):
        return err

    lang = (language or get_setting("DEFAULT_CODE_LANGUAGE")).lower()
    http_client = (client or get_setting("DEFAULT_HTTP_CLIENT")).lower()

    # cURL shortcut
    is_curl = lang in ("curl", "shell", "sh", "bash")
    if is_curl:
        lang = "curl"
        http_client = "curl"

    # Auto-select appropriate client for language
    is_python = lang in ("python", "py")
    if is_python and http_client in ("fetch", "axios", "ky"):
        http_client = "requests"
    elif not is_curl and not is_python and http_client in ("requests", "httpx"):
        http_client = "fetch"

    processor = get_processor()
    endpoint = processor.get_endpoint(path, method)
    if endpoint is None:
        return json.dumps({"error": f"Endpoint {method.upper()} {path} not found"})

    generators = {
        "fetch": _generate_fetch_snippet,
        "axios": _generate_axios_snippet,
        "ky": _generate_ky_snippet,
        "requests": _generate_requests_snippet,
        "httpx": _generate_httpx_snippet,
        "curl": _generate_curl_snippet,
    }
    generator = generators.get(http_client, _generate_fetch_snippet)
    use_ts = lang in ("typescript", "ts")

    code = generator(endpoint, processor, use_typescript=use_ts)

    # Build enriched metadata
    auth_methods_detail = []
    if endpoint.auth_required:
        all_auth = processor.get_auth_methods()
        auth_by_name = {a.name: a for a in all_auth}
        for name in endpoint.auth_methods:
            if name in auth_by_name:
                a = auth_by_name[name]
                auth_methods_detail.append({"type": a.type, "description": a.description})

    path_params = [
        {"name": p.name, "type": p.schema.get("type", "string"), "required": p.required, "description": p.description}
        for p in endpoint.parameters
        if p.location == "path"
    ]
    query_params = [
        {"name": p.name, "type": p.schema.get("type", "string"), "required": p.required, "description": p.description}
        for p in endpoint.parameters
        if p.location == "query"
    ]

    success_response = None
    for code_key in ("200", "201", "204"):
        if code_key in endpoint.responses:
            r = endpoint.responses[code_key]
            success_response = {"success_status": r.status_code, "description": r.description}
            break

    pagination = _detect_pagination(endpoint, processor)
    pagination_meta = None
    if pagination:
        pagination_meta = {
            "style": pagination.style,
            "results_field": pagination.results_field,
            "has_count": pagination.has_count,
        }

    return json.dumps(
        {
            "language": lang,
            "client": http_client,
            "code": code,
            "metadata": {
                "function_name": _operation_to_func_name(endpoint, snake_case=is_python),
                "endpoint": {
                    "path": endpoint.path,
                    "method": endpoint.method,
                    "summary": endpoint.summary,
                    "deprecated": endpoint.deprecated,
                },
                "auth": {
                    "required": endpoint.auth_required,
                    "methods": auth_methods_detail,
                },
                "parameters": {
                    "path": path_params,
                    "query": query_params,
                    "body_required": endpoint.request_body.required if endpoint.request_body else False,
                },
                "response": success_response,
                "pagination": pagination_meta,
            },
        },
        indent=2,
    )


def list_schemas() -> str:
    """List all available schema names and descriptions. Use get_schema_detail for full properties."""
    logger.debug("Tool list_schemas")
    processor = get_processor()
    schemas = processor.get_schemas()
    logger.debug("list_schemas: %d schema(s)", len(schemas))
    result = [{"name": s.name, "description": s.description} for s in schemas]
    return json.dumps(result, indent=2)


def get_schema_detail(name: str) -> str:
    """Get full details of a data model schema including all properties, types, and constraints."""
    logger.debug("Tool get_schema_detail: %r", name)
    processor = get_processor()
    schema = processor.get_schema_definition(name)
    if schema is None:
        logger.debug("get_schema_detail: not found")
        return json.dumps({"error": f"Schema '{name}' not found"})
    logger.debug("get_schema_detail: found")
    return json.dumps(asdict(schema), indent=2, default=str)


def register_tools(mcp: FastMCP):
    mcp.tool()(search_endpoints)
    mcp.tool()(get_endpoint_detail)
    mcp.tool()(get_request_example)
    mcp.tool()(get_response_example)
    mcp.tool()(generate_code_snippet)
    mcp.tool()(list_schemas)
    mcp.tool()(get_schema_detail)


# ---------------------------------------------------------------------------
# Sanitization helpers
# ---------------------------------------------------------------------------


def _sanitize_identifier(value: str) -> str:
    """Sanitize a value for use as a JS/TS identifier."""
    return re.sub(r"[^a-zA-Z0-9_$]", "_", value)


def _sanitize_string_literal(value: str) -> str:
    """Escape a value for safe inclusion in a JS string literal."""
    return (
        value.replace("\\", "\\\\").replace("'", "\\'").replace("`", "\\`").replace("${", "\\${").replace("\n", "\\n")
    )


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _build_path_with_params(endpoint, *, python: bool = False) -> str:
    path = endpoint.path
    path_params = [p for p in endpoint.parameters if p.location == "path"]
    if path_params:
        if python:
            for p in path_params:
                safe = _sanitize_identifier(p.name)
                path = path.replace(f"{{{p.name}}}", f"{{{safe}}}")
            return f'f"{path}"'
        for p in path_params:
            safe = _sanitize_identifier(p.name)
            path = path.replace(f"{{{p.name}}}", f"${{{safe}}}")
        return f"`{path}`"
    if python:
        return f'"{_sanitize_string_literal(endpoint.path)}"'
    return f"'{_sanitize_string_literal(endpoint.path)}'"


def _get_query_params(endpoint) -> list:
    return [p for p in endpoint.parameters if p.location == "query"]


def _get_path_params(endpoint) -> list:
    return [p for p in endpoint.parameters if p.location == "path"]


def _operation_to_func_name(endpoint, *, snake_case: bool = False) -> str:
    if endpoint.operation_id:
        if snake_case:
            name = re.sub(r"[^a-zA-Z0-9]", "_", endpoint.operation_id).lower()
            name = re.sub(r"_+", "_", name).strip("_")
            return name
        parts = endpoint.operation_id.replace("-", "_").split("_")
        name = parts[0].lower() + "".join(p.capitalize() for p in parts[1:])
        return _sanitize_identifier(name)
    method = endpoint.method.lower()
    segments = [s for s in endpoint.path.split("/") if s and not s.startswith("{")]
    if snake_case:
        return _sanitize_identifier(method + "_" + "_".join(segments))
    return _sanitize_identifier(method + "".join(s.capitalize() for s in segments))


def _get_base_url(processor) -> str:
    overview = processor.get_overview()
    return overview.base_url


def _get_success_response(endpoint):
    for code in ("200", "201", "204"):
        if code in endpoint.responses:
            return endpoint.responses[code]
    return None


def _get_ref_name(schema: dict) -> str | None:
    ref = schema.get("$ref", "")
    if ref:
        return ref.split("/")[-1]
    return None


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------


def _build_auth_info(endpoint, processor):
    """Return (header_dict_entries, func_params) for the endpoint's auth."""
    if not endpoint.auth_required:
        return [], []

    all_auth = processor.get_auth_methods()
    auth_by_name = {a.name: a for a in all_auth}

    for name in endpoint.auth_methods:
        auth = auth_by_name.get(name)
        if not auth:
            continue
        if auth.type == "bearer":
            return [("Authorization", "bearer")], [("token", "str")]
        if auth.type == "basic":
            return [("Authorization", "basic")], [("credentials", "str")]
        if auth.type == "apiKey":
            header = auth.header_name or "X-API-Key"
            return [(header, "apiKey")], [("api_key", "str")]

    # Fallback: generic bearer
    return [("Authorization", "bearer")], [("token", "str")]


def _format_auth_header_js(auth_entries: list) -> list[str]:
    lines = []
    for header_name, auth_type in auth_entries:
        if auth_type == "bearer":
            lines.append(f"'{header_name}': `Bearer ${{token}}`")
        elif auth_type == "basic":
            lines.append(f"'{header_name}': `Basic ${{credentials}}`")
        elif auth_type == "apiKey":
            lines.append(f"'{header_name}': api_key")
    return lines


def _format_auth_header_py(auth_entries: list) -> list[str]:
    lines = []
    for header_name, auth_type in auth_entries:
        if auth_type == "bearer":
            lines.append(f'"{header_name}": f"Bearer {{token}}"')
        elif auth_type == "basic":
            lines.append(f'"{header_name}": f"Basic {{credentials}}"')
        elif auth_type == "apiKey":
            lines.append(f'"{header_name}": api_key')
    return lines


def _format_auth_header_curl(auth_entries: list) -> list[str]:
    lines = []
    for header_name, auth_type in auth_entries:
        if auth_type == "bearer":
            lines.append(f"-H '{header_name}: Bearer YOUR_TOKEN'")
        elif auth_type == "basic":
            lines.append(f"-H '{header_name}: Basic YOUR_CREDENTIALS'")
        elif auth_type == "apiKey":
            lines.append(f"-H '{header_name}: YOUR_API_KEY'")
    return lines


# ---------------------------------------------------------------------------
# Pagination helpers
# ---------------------------------------------------------------------------


def _detect_pagination(endpoint, processor) -> PaginationInfo | None:
    """Detect DRF pagination style from endpoint response schema and query params."""
    if endpoint.method.upper() != "GET":
        return None

    response = _get_success_response(endpoint)
    if not response or not response.schema:
        return None

    # Resolve the response schema (follow $ref)
    schema = response.schema
    if "$ref" in schema:
        schema = processor.resolve_ref(schema["$ref"])

    # Must be an object with 'results' (array) + 'next' + 'previous'
    if schema.get("type") != "object":
        return None
    props = schema.get("properties", {})
    results_prop = props.get("results", {})
    if results_prop.get("type") != "array" and "$ref" not in results_prop:
        return None
    if "next" not in props or "previous" not in props:
        return None

    has_count = "count" in props
    query_names = {p.name for p in endpoint.parameters if p.location == "query"}

    if "cursor" in query_names:
        return PaginationInfo(style="cursor", has_count=has_count)
    if "limit" in query_names and "offset" in query_names:
        return PaginationInfo(style="limit_offset", has_count=has_count)
    return PaginationInfo(style="page_number", has_count=has_count)


def _generate_pagination_helper_js(
    endpoint,
    processor,
    pagination: PaginationInfo,
    func_name: str,
    *,
    use_typescript: bool = False,
) -> str:
    """Generate a JS/TS async generator that iterates through all pages."""
    all_name = f"fetchAll{func_name[0].upper()}{func_name[1:]}"
    auth_entries, auth_params = _build_auth_info(endpoint, processor)

    # Build the function param list (same as base function minus query params used for pagination)
    params = []
    for p in _get_path_params(endpoint):
        safe = _sanitize_identifier(p.name)
        params.append(f"{safe}: {_schema_to_ts_type(p.schema)}" if use_typescript else safe)
    for pname, _ in auth_params:
        params.append(f"{pname}: string" if use_typescript else pname)
    params.append("delay?: number" if use_typescript else "delay")

    ret_type = ""
    if use_typescript:
        resp = _get_success_response(endpoint)
        item_type = "any"
        if resp and resp.schema:
            schema = resp.schema
            if "$ref" in schema:
                schema = processor.resolve_ref(schema["$ref"])
            results_schema = schema.get("properties", {}).get("results", {})
            items_schema = results_schema.get("items", {})
            item_type = _schema_to_ts_type(items_schema)
        ret_type = f": AsyncGenerator<{item_type}>"

    lines = []
    lines.append(f"async function* {all_name}({', '.join(params)}){ret_type} {{")

    # Build base URL + auth headers
    base_url = _get_base_url(processor)
    path_expr = _build_path_with_params(endpoint)
    url_expr = f"`{base_url}` + {path_expr}" if "{" in endpoint.path else f"'{base_url}{endpoint.path}'"

    auth_header_lines = _format_auth_header_js(auth_entries)
    if auth_header_lines:
        lines.append("  const headers = {")
        for h in auth_header_lines:
            lines.append(f"    {h},")
        lines.append("  };")
    else:
        lines.append("  const headers = {};")

    lines.append(f"  let url{': string | null' if use_typescript else ''} = {url_expr};")

    if pagination.style == "page_number":
        lines.append("  let page = 1;")
        lines.append("")
        lines.append("  while (true) {")
        lines.append("    const separator = url.includes('?') ? '&' : '?';")
        lines.append("    const response = await fetch(`${url}${separator}page=${page}`, { headers });")
        lines.append("    const data = await response.json();")
        lines.append(f"    yield* data.{pagination.results_field};")
        lines.append("    if (!data.next) break;")
        lines.append("    page++;")
    elif pagination.style == "limit_offset":
        lines.append("  let offset = 0;")
        lines.append("  const limit = 100;")
        lines.append("")
        lines.append("  while (true) {")
        lines.append("    const separator = url.includes('?') ? '&' : '?';")
        lines.append(
            "    const response = await fetch(`${url}${separator}limit=${limit}&offset=${offset}`, { headers });"
        )
        lines.append("    const data = await response.json();")
        lines.append(f"    yield* data.{pagination.results_field};")
        lines.append("    if (!data.next) break;")
        lines.append("    offset += limit;")
    else:  # cursor
        lines.append("")
        lines.append("  while (url) {")
        lines.append("    const response = await fetch(url, { headers });")
        lines.append("    const data = await response.json();")
        lines.append(f"    yield* data.{pagination.results_field};")
        lines.append("    url = data.next;")

    lines.append("    if (delay) await new Promise(r => setTimeout(r, delay));")
    lines.append("  }")
    lines.append("}")
    return "\n".join(lines)


def _generate_pagination_helper_py(
    endpoint,
    processor,
    pagination: PaginationInfo,
    func_name: str,
    *,
    is_async: bool = False,
) -> str:
    """Generate a Python generator that iterates through all pages."""
    all_name = f"fetch_all_{func_name}"
    auth_entries, auth_params = _build_auth_info(endpoint, processor)

    # Build param list
    params = []
    for p in _get_path_params(endpoint):
        params.append(_sanitize_identifier(p.name))
    for pname, _ in auth_params:
        params.append(pname)
    params.append("delay: float = 0")

    auth_header_py = _format_auth_header_py(auth_entries)

    base_url = _get_base_url(processor)
    path_expr = _build_path_with_params(endpoint, python=True)
    url_expr = f'f"{base_url}" + {path_expr}' if "{" in endpoint.path else f'"{base_url}{endpoint.path}"'

    indent = "        " if is_async else "    "
    lines = []

    if is_async:
        lines.append(f"async def {all_name}({', '.join(params)}):")
    else:
        lines.append(f"def {all_name}({', '.join(params)}):")

    lines.append(f'{indent.rstrip()}    """Iterate through all pages of results."""')

    if auth_header_py:
        lines.append(f"{indent}headers = {{{', '.join(auth_header_py)}}}")
    else:
        lines.append(f"{indent}headers = {{}}")

    lines.append(f"{indent}url = {url_expr}")

    if pagination.style == "page_number":
        lines.append(f"{indent}page = 1")

        if is_async:
            lines.append(f"{indent}async with httpx.AsyncClient() as client:")
            inner = indent + "    "
            lines.append(f"{inner}while True:")
            lines.append(f"{inner}    sep = '&' if '?' in url else '?'")
            lines.append(f'{inner}    response = await client.get(f"{{url}}{{sep}}page={{page}}", headers=headers)')
            lines.append(f"{inner}    data = response.json()")
            lines.append(f"{inner}    for item in data['{pagination.results_field}']:")
            lines.append(f"{inner}        yield item")
            lines.append(f"{inner}    if not data.get('next'):")
            lines.append(f"{inner}        break")
            lines.append(f"{inner}    page += 1")
            lines.append(f"{inner}    if delay:")
            lines.append(f"{inner}        await asyncio.sleep(delay)")
        else:
            lines.append(f"{indent}while True:")
            lines.append(f"{indent}    sep = '&' if '?' in url else '?'")
            lines.append(f'{indent}    response = requests.get(f"{{url}}{{sep}}page={{page}}", headers=headers)')
            lines.append(f"{indent}    response.raise_for_status()")
            lines.append(f"{indent}    data = response.json()")
            lines.append(f"{indent}    yield from data['{pagination.results_field}']")
            lines.append(f"{indent}    if not data.get('next'):")
            lines.append(f"{indent}        break")
            lines.append(f"{indent}    page += 1")
            lines.append(f"{indent}    if delay:")
            lines.append(f"{indent}        time.sleep(delay)")

    elif pagination.style == "limit_offset":
        lines.append(f"{indent}offset = 0")
        lines.append(f"{indent}limit = 100")

        if is_async:
            lines.append(f"{indent}async with httpx.AsyncClient() as client:")
            inner = indent + "    "
            lines.append(f"{inner}while True:")
            lines.append(f"{inner}    sep = '&' if '?' in url else '?'")
            lo_url = 'f"{url}{sep}limit={limit}&offset={offset}"'
            lines.append(f"{inner}    response = await client.get({lo_url}, headers=headers)")
            lines.append(f"{inner}    data = response.json()")
            lines.append(f"{inner}    for item in data['{pagination.results_field}']:")
            lines.append(f"{inner}        yield item")
            lines.append(f"{inner}    if not data.get('next'):")
            lines.append(f"{inner}        break")
            lines.append(f"{inner}    offset += limit")
            lines.append(f"{inner}    if delay:")
            lines.append(f"{inner}        await asyncio.sleep(delay)")
        else:
            lines.append(f"{indent}while True:")
            lines.append(f"{indent}    sep = '&' if '?' in url else '?'")
            lo_url = 'f"{url}{sep}limit={limit}&offset={offset}"'
            lines.append(f"{indent}    response = requests.get({lo_url}, headers=headers)")
            lines.append(f"{indent}    response.raise_for_status()")
            lines.append(f"{indent}    data = response.json()")
            lines.append(f"{indent}    yield from data['{pagination.results_field}']")
            lines.append(f"{indent}    if not data.get('next'):")
            lines.append(f"{indent}        break")
            lines.append(f"{indent}    offset += limit")
            lines.append(f"{indent}    if delay:")
            lines.append(f"{indent}        time.sleep(delay)")

    else:  # cursor
        if is_async:
            lines.append(f"{indent}async with httpx.AsyncClient() as client:")
            inner = indent + "    "
            lines.append(f"{inner}while url:")
            lines.append(f"{inner}    response = await client.get(url, headers=headers)")
            lines.append(f"{inner}    data = response.json()")
            lines.append(f"{inner}    for item in data['{pagination.results_field}']:")
            lines.append(f"{inner}        yield item")
            lines.append(f"{inner}    url = data.get('next')")
            lines.append(f"{inner}    if url and delay:")
            lines.append(f"{inner}        await asyncio.sleep(delay)")
        else:
            lines.append(f"{indent}while url:")
            lines.append(f"{indent}    response = requests.get(url, headers=headers)")
            lines.append(f"{indent}    response.raise_for_status()")
            lines.append(f"{indent}    data = response.json()")
            lines.append(f"{indent}    yield from data['{pagination.results_field}']")
            lines.append(f"{indent}    url = data.get('next')")
            lines.append(f"{indent}    if url and delay:")
            lines.append(f"{indent}        time.sleep(delay)")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# TypeScript type helpers
# ---------------------------------------------------------------------------


def _schema_to_ts_type(schema: dict) -> str:
    if not schema:
        return "any"

    # Handle $ref
    ref_name = _get_ref_name(schema)
    if ref_name:
        return ref_name

    # Handle enum
    if "enum" in schema:
        return " | ".join(f"'{v}'" if isinstance(v, str) else str(v) for v in schema["enum"])

    type_val = schema.get("type", "any")

    type_map = {
        "integer": "number",
        "number": "number",
        "string": "string",
        "boolean": "boolean",
    }

    if type_val == "array":
        items = schema.get("items", {})
        item_type = _schema_to_ts_type(items)
        base = f"{item_type}[]"
    elif type_val == "object":
        base = "Record<string, any>"
    else:
        base = type_map.get(type_val, "any")

    if schema.get("nullable"):
        return f"{base} | null"
    return base


def _schema_to_ts_interface(name: str, schema: dict, processor, *, seen: set | None = None) -> str:
    """Generate a TypeScript interface from an OpenAPI schema dict."""
    if seen is None:
        seen = set()

    # Resolve $ref if present
    ref_name = _get_ref_name(schema)
    if ref_name:
        if ref_name in seen:
            return ""
        seen.add(ref_name)
        resolved = processor.resolve_ref(schema["$ref"])
        return _schema_to_ts_interface(ref_name, resolved, processor, seen=seen)

    properties = schema.get("properties", {})
    if not properties:
        return ""

    required_fields = set(schema.get("required", []))
    lines = [f"interface {name} {{"]

    for prop_name, prop_schema in properties.items():
        resolved_prop = processor._resolve_schema(prop_schema)
        desc = resolved_prop.get("description", "")
        if desc:
            lines.append(f"  /** {desc} */")

        ts_type = _schema_to_ts_type(resolved_prop)
        optional = "" if prop_name in required_fields else "?"
        readonly = "readonly " if resolved_prop.get("readOnly") else ""
        lines.append(f"  {readonly}{prop_name}{optional}: {ts_type};")

    lines.append("}")
    return "\n".join(lines)


def _build_ts_interfaces(endpoint, processor) -> tuple[str, str, str, str]:
    """Return (interfaces_block, request_type, response_type, query_type)."""
    interfaces = []
    request_type = "any"
    response_type = "any"
    query_type = ""

    # Request body interface
    if endpoint.request_body and endpoint.request_body.schema:
        schema = endpoint.request_body.schema
        ref_name = _get_ref_name(schema)
        if ref_name:
            iface = _schema_to_ts_interface(ref_name, schema, processor)
            if iface:
                interfaces.append(iface)
            request_type = ref_name
        elif schema.get("properties"):
            func_name = _operation_to_func_name(endpoint)
            iface_name = func_name[0].upper() + func_name[1:] + "Request"
            iface = _schema_to_ts_interface(iface_name, schema, processor)
            if iface:
                interfaces.append(iface)
            request_type = iface_name
        else:
            request_type = "Record<string, any>"

    # Response interface
    success_resp = _get_success_response(endpoint)
    if success_resp and success_resp.schema:
        resp_schema = success_resp.schema
        if resp_schema.get("type") == "array" and resp_schema.get("items"):
            items = resp_schema["items"]
            ref_name = _get_ref_name(items)
            if ref_name:
                iface = _schema_to_ts_interface(ref_name, items, processor)
                if iface:
                    interfaces.append(iface)
                response_type = f"{ref_name}[]"
            else:
                response_type = "any[]"
        else:
            ref_name = _get_ref_name(resp_schema)
            if ref_name:
                iface = _schema_to_ts_interface(ref_name, resp_schema, processor)
                if iface:
                    interfaces.append(iface)
                response_type = ref_name
            elif resp_schema.get("properties"):
                func_name = _operation_to_func_name(endpoint)
                iface_name = func_name[0].upper() + func_name[1:] + "Response"
                iface = _schema_to_ts_interface(iface_name, resp_schema, processor)
                if iface:
                    interfaces.append(iface)
                response_type = iface_name

    # Query params interface
    query_params = _get_query_params(endpoint)
    if query_params:
        func_name = _operation_to_func_name(endpoint)
        qname = func_name[0].upper() + func_name[1:] + "Params"
        qlines = [f"interface {qname} {{"]
        for p in query_params:
            if p.description:
                qlines.append(f"  /** {p.description} */")
            ts_type = _schema_to_ts_type(p.schema)
            optional = "" if p.required else "?"
            qlines.append(f"  {p.name}{optional}: {ts_type};")
        qlines.append("}")
        interfaces.append("\n".join(qlines))
        query_type = qname

    # Deduplicate interfaces by name
    seen_names: set[str] = set()
    unique: list[str] = []
    for iface in interfaces:
        first_line = iface.split("\n")[0]
        if first_line not in seen_names:
            seen_names.add(first_line)
            unique.append(iface)

    block = "\n\n".join(unique)
    return block, request_type, response_type, query_type


# ---------------------------------------------------------------------------
# Python type helpers
# ---------------------------------------------------------------------------


def _schema_to_python_type(schema: dict) -> str:
    if not schema:
        return "Any"

    ref_name = _get_ref_name(schema)
    if ref_name:
        return ref_name

    if "enum" in schema:
        vals = ", ".join(f'"{v}"' if isinstance(v, str) else str(v) for v in schema["enum"])
        return f"Literal[{vals}]"

    type_val = schema.get("type", "Any")
    type_map = {
        "integer": "int",
        "number": "float",
        "string": "str",
        "boolean": "bool",
    }

    if type_val == "array":
        items = schema.get("items", {})
        item_type = _schema_to_python_type(items)
        base = f"list[{item_type}]"
    elif type_val == "object":
        base = "dict[str, Any]"
    else:
        base = type_map.get(type_val, "Any")

    if schema.get("nullable"):
        return f"{base} | None"
    return base


def _schema_to_python_typeddict(name: str, schema: dict, processor, *, seen: set | None = None) -> str:
    """Generate a Python TypedDict from an OpenAPI schema dict."""
    if seen is None:
        seen = set()

    ref_name = _get_ref_name(schema)
    if ref_name:
        if ref_name in seen:
            return ""
        seen.add(ref_name)
        resolved = processor.resolve_ref(schema["$ref"])
        return _schema_to_python_typeddict(ref_name, resolved, processor, seen=seen)

    properties = schema.get("properties", {})
    if not properties:
        return ""

    required_fields = set(schema.get("required", []))
    lines = [f"class {name}(TypedDict):"]

    for prop_name, prop_schema in properties.items():
        resolved_prop = processor._resolve_schema(prop_schema)
        desc = resolved_prop.get("description", "")
        py_type = _schema_to_python_type(resolved_prop)

        annotation = py_type if prop_name in required_fields else f"NotRequired[{py_type}]"

        if desc:
            lines.append(f"    {prop_name}: {annotation}  # {desc}")
        else:
            lines.append(f"    {prop_name}: {annotation}")

    return "\n".join(lines)


def _build_python_types(endpoint, processor) -> tuple[str, str, str, str]:
    """Return (types_block, request_type, response_type, query_type)."""
    type_defs = []
    request_type = "dict[str, Any]"
    response_type = "dict[str, Any]"
    query_type = ""

    # Request body TypedDict
    if endpoint.request_body and endpoint.request_body.schema:
        schema = endpoint.request_body.schema
        ref_name = _get_ref_name(schema)
        if ref_name:
            td = _schema_to_python_typeddict(ref_name, schema, processor)
            if td:
                type_defs.append(td)
            request_type = ref_name
        elif schema.get("properties"):
            func_name = _operation_to_func_name(endpoint, snake_case=True)
            td_name = "".join(w.capitalize() for w in func_name.split("_")) + "Request"
            td = _schema_to_python_typeddict(td_name, schema, processor)
            if td:
                type_defs.append(td)
            request_type = td_name

    # Response TypedDict
    success_resp = _get_success_response(endpoint)
    if success_resp and success_resp.schema:
        resp_schema = success_resp.schema
        if resp_schema.get("type") == "array" and resp_schema.get("items"):
            items = resp_schema["items"]
            ref_name = _get_ref_name(items)
            if ref_name:
                td = _schema_to_python_typeddict(ref_name, items, processor)
                if td:
                    type_defs.append(td)
                response_type = f"list[{ref_name}]"
            else:
                response_type = "list[dict[str, Any]]"
        else:
            ref_name = _get_ref_name(resp_schema)
            if ref_name:
                td = _schema_to_python_typeddict(ref_name, resp_schema, processor)
                if td:
                    type_defs.append(td)
                response_type = ref_name
            elif resp_schema.get("properties"):
                func_name = _operation_to_func_name(endpoint, snake_case=True)
                td_name = "".join(w.capitalize() for w in func_name.split("_")) + "Response"
                td = _schema_to_python_typeddict(td_name, resp_schema, processor)
                if td:
                    type_defs.append(td)
                response_type = td_name

    # Deduplicate
    seen_names: set[str] = set()
    unique: list[str] = []
    for td in type_defs:
        first_line = td.split("\n")[0]
        if first_line not in seen_names:
            seen_names.add(first_line)
            unique.append(td)

    block = "\n\n\n".join(unique)
    return block, request_type, response_type, query_type


# ---------------------------------------------------------------------------
# JSDoc / Docstring builders
# ---------------------------------------------------------------------------


def _build_jsdoc(endpoint) -> str:
    lines = ["/**"]
    if endpoint.summary:
        lines.append(f" * {endpoint.summary}")
    if endpoint.description and endpoint.description != endpoint.summary:
        lines.append(f" * {endpoint.description}")
    if endpoint.deprecated:
        lines.append(" * @deprecated This endpoint is deprecated.")

    path_params = _get_path_params(endpoint)
    for p in path_params:
        ts_type = _schema_to_ts_type(p.schema)
        desc = f" - {p.description}" if p.description else ""
        lines.append(f" * @param {{{ts_type}}} {p.name}{desc}")

    if endpoint.request_body:
        lines.append(" * @param data - Request body")

    query_params = _get_query_params(endpoint)
    if query_params:
        lines.append(" * @param params - Query parameters")

    auth_entries, auth_params = _build_auth_info(endpoint, _LazyProcessor())
    for param_name, _ in auth_params:
        lines.append(f" * @param {param_name} - Authentication credential")

    success = _get_success_response(endpoint)
    if success:
        lines.append(f" * @returns {success.description}")

    # Error responses
    for code, resp in sorted(endpoint.responses.items()):
        if code.startswith("4") or code.startswith("5"):
            lines.append(f" * @throws {{{code}}} {resp.description}")

    lines.append(" */")
    return "\n".join(lines)


class _LazyProcessor:
    """Placeholder to avoid passing processor to jsdoc builder when not needed for auth."""

    def get_auth_methods(self):
        return []


def _build_jsdoc_with_processor(endpoint, processor) -> str:
    lines = ["/**"]
    if endpoint.summary:
        lines.append(f" * {endpoint.summary}")
    if endpoint.description and endpoint.description != endpoint.summary:
        lines.append(f" * {endpoint.description}")
    if endpoint.deprecated:
        lines.append(" * @deprecated This endpoint is deprecated.")

    path_params = _get_path_params(endpoint)
    for p in path_params:
        ts_type = _schema_to_ts_type(p.schema)
        desc = f" - {p.description}" if p.description else ""
        lines.append(f" * @param {{{ts_type}}} {p.name}{desc}")

    if endpoint.request_body:
        lines.append(" * @param data - Request body")

    query_params = _get_query_params(endpoint)
    if query_params:
        lines.append(" * @param params - Query parameters")

    auth_entries, auth_params = _build_auth_info(endpoint, processor)
    for param_name, _ in auth_params:
        lines.append(f" * @param {param_name} - Authentication credential")

    success = _get_success_response(endpoint)
    if success:
        lines.append(f" * @returns {success.description}")

    for code, resp in sorted(endpoint.responses.items()):
        if code.startswith("4") or code.startswith("5"):
            lines.append(f" * @throws {{{code}}} {resp.description}")

    lines.append(" */")
    return "\n".join(lines)


def _build_docstring(endpoint, processor) -> str:
    lines = ['    """']
    if endpoint.summary:
        lines[0] += endpoint.summary
    if endpoint.description and endpoint.description != endpoint.summary:
        lines.append(f"    {endpoint.description}")
    if endpoint.deprecated:
        lines.append("")
        lines.append("    .. deprecated::")
        lines.append("        This endpoint is deprecated.")

    # Args section
    args = []
    path_params = _get_path_params(endpoint)
    for p in path_params:
        py_type = _schema_to_python_type(p.schema)
        desc = p.description or p.name
        args.append(f"        {p.name} ({py_type}): {desc}")

    if endpoint.request_body:
        args.append("        data: Request body.")

    query_params = _get_query_params(endpoint)
    for p in query_params:
        py_type = _schema_to_python_type(p.schema)
        desc = p.description or p.name
        args.append(f"        {p.name} ({py_type}): {desc}")

    auth_entries, auth_params = _build_auth_info(endpoint, processor)
    for param_name, param_type in auth_params:
        args.append(f"        {param_name} ({param_type}): Authentication credential.")

    if args:
        lines.append("")
        lines.append("    Args:")
        lines.extend(args)

    # Returns section
    success = _get_success_response(endpoint)
    if success:
        lines.append("")
        lines.append("    Returns:")
        lines.append(f"        {success.description}")

    # Raises section
    error_lines = []
    for code, resp in sorted(endpoint.responses.items()):
        if code.startswith("4") or code.startswith("5"):
            error_lines.append(f"        HTTPError: {code} - {resp.description}")
    if error_lines:
        lines.append("")
        lines.append("    Raises:")
        lines.extend(error_lines)

    lines.append('    """')
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Usage example builders
# ---------------------------------------------------------------------------


def _build_js_usage_example(endpoint, processor) -> str:
    func_name = _operation_to_func_name(endpoint)
    args = []

    path_params = _get_path_params(endpoint)
    for p in path_params:
        val = processor.generate_example_value(p.name, p.schema)
        args.append(json.dumps(val))

    if endpoint.request_body and endpoint.request_body.schema:
        example = processor.generate_example_from_schema(endpoint.request_body.schema)
        args.append(json.dumps(example, default=str))

    query_params = _get_query_params(endpoint)
    if query_params:
        qvals = {}
        for p in query_params:
            qvals[p.name] = processor.generate_example_value(p.name, p.schema)
        args.append(json.dumps(qvals, default=str))

    auth_entries, auth_params = _build_auth_info(endpoint, processor)
    for param_name, _ in auth_params:
        args.append(f'"your-{param_name}-here"')

    call = f"{func_name}({', '.join(args)})"
    lines = [
        "",
        "// Usage:",
        f"// const result = await {call};",
    ]
    return "\n".join(lines)


def _build_python_usage_example(endpoint, processor, *, is_async: bool = False) -> str:
    func_name = _operation_to_func_name(endpoint, snake_case=True)
    kwargs = []

    path_params = _get_path_params(endpoint)
    for p in path_params:
        val = processor.generate_example_value(p.name, p.schema)
        kwargs.append(f"{p.name}={json.dumps(val)}")

    if endpoint.request_body and endpoint.request_body.schema:
        example = processor.generate_example_from_schema(endpoint.request_body.schema)
        kwargs.append(f"data={json.dumps(example, default=str)}")

    query_params = _get_query_params(endpoint)
    for p in query_params:
        val = processor.generate_example_value(p.name, p.schema)
        kwargs.append(f"{p.name}={json.dumps(val)}")

    auth_entries, auth_params = _build_auth_info(endpoint, processor)
    for param_name, _ in auth_params:
        kwargs.append(f'{param_name}="your-{param_name}-here"')

    call = f"{func_name}({', '.join(kwargs)})"
    prefix = "await " if is_async else ""
    lines = [
        "",
        "# Usage:",
        f"# result = {prefix}{call}",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# JavaScript / TypeScript generators
# ---------------------------------------------------------------------------


def _generate_fetch_snippet(endpoint, processor, use_typescript: bool = False) -> str:
    lines = []
    base_url = _get_base_url(processor)
    path_expr = _build_path_with_params(endpoint)
    method = endpoint.method.upper()
    has_body = endpoint.request_body is not None
    query_params = _get_query_params(endpoint)
    path_params = _get_path_params(endpoint)
    auth_entries, auth_params = _build_auth_info(endpoint, processor)

    func_name = _operation_to_func_name(endpoint)

    # TypeScript interfaces
    if use_typescript:
        iface_block, req_type, resp_type, query_type = _build_ts_interfaces(endpoint, processor)
        if iface_block:
            lines.append(iface_block)
            lines.append("")

    # JSDoc
    jsdoc = _build_jsdoc_with_processor(endpoint, processor)
    lines.append(jsdoc)

    # Function signature
    params = []
    if use_typescript:
        for p in path_params:
            ts_type = _schema_to_ts_type(p.schema)
            params.append(f"{_sanitize_identifier(p.name)}: {ts_type}")
        if has_body:
            params.append(f"data: {req_type}")
        if query_params:
            optional = "?" if not any(p.required for p in query_params) else ""
            q_type = query_type or "Record<string, any>"
            params.append(f"params{optional}: {q_type}")
        for param_name, _ in auth_params:
            params.append(f"{param_name}: string")
        ret_type = f": Promise<{resp_type}>" if use_typescript else ""
        sig = f"async function {func_name}({', '.join(params)}){ret_type} {{"
    else:
        for p in path_params:
            params.append(_sanitize_identifier(p.name))
        if has_body:
            params.append("data")
        if query_params:
            params.append("params = {}")
        for param_name, _ in auth_params:
            params.append(param_name)
        sig = f"async function {func_name}({', '.join(params)}) {{"

    lines.append(sig)

    # Base URL + path
    if base_url:
        lines.append(f"  const BASE_URL = '{_sanitize_string_literal(base_url)}';")
    else:
        lines.append("  const BASE_URL = '';")

    if query_params:
        lines.append("  const queryString = new URLSearchParams(params).toString();")
        lines.append(f"  const url = BASE_URL + {path_expr} + (queryString ? `?${{queryString}}` : '');")
    else:
        lines.append(f"  const url = BASE_URL + {path_expr};")

    lines.append("")
    lines.append("  const response = await fetch(url, {")
    lines.append(f"    method: '{method}',")

    headers = []
    if has_body:
        headers.append("'Content-Type': 'application/json'")
    headers.extend(_format_auth_header_js(auth_entries))
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

    # Usage example
    lines.append(_build_js_usage_example(endpoint, processor))

    pagination = _detect_pagination(endpoint, processor)
    if pagination:
        func_name = _operation_to_func_name(endpoint)
        lines.append("")
        lines.append(
            _generate_pagination_helper_js(endpoint, processor, pagination, func_name, use_typescript=use_typescript)
        )

    return "\n".join(lines)


def _generate_axios_snippet(endpoint, processor, use_typescript: bool = False) -> str:
    lines = ["import axios from 'axios';", ""]
    base_url = _get_base_url(processor)
    path_expr = _build_path_with_params(endpoint)
    method = endpoint.method.lower()
    has_body = endpoint.request_body is not None
    query_params = _get_query_params(endpoint)
    path_params = _get_path_params(endpoint)
    auth_entries, auth_params = _build_auth_info(endpoint, processor)

    func_name = _operation_to_func_name(endpoint)

    # TypeScript interfaces
    if use_typescript:
        iface_block, req_type, resp_type, query_type = _build_ts_interfaces(endpoint, processor)
        if iface_block:
            lines.append(iface_block)
            lines.append("")

    # JSDoc
    jsdoc = _build_jsdoc_with_processor(endpoint, processor)
    lines.append(jsdoc)

    # Function signature
    params = []
    if use_typescript:
        for p in path_params:
            ts_type = _schema_to_ts_type(p.schema)
            params.append(f"{_sanitize_identifier(p.name)}: {ts_type}")
        if has_body:
            params.append(f"data: {req_type}")
        if query_params:
            optional = "?" if not any(p.required for p in query_params) else ""
            q_type = query_type or "Record<string, any>"
            params.append(f"params{optional}: {q_type}")
        for param_name, _ in auth_params:
            params.append(f"{param_name}: string")
        ret_type = f": Promise<{resp_type}>"
        sig = f"async function {func_name}({', '.join(params)}){ret_type} {{"
    else:
        for p in path_params:
            params.append(_sanitize_identifier(p.name))
        if has_body:
            params.append("data")
        if query_params:
            params.append("params = {}")
        for param_name, _ in auth_params:
            params.append(param_name)
        sig = f"async function {func_name}({', '.join(params)}) {{"

    lines.append(sig)

    # Base URL
    if base_url:
        lines.append(f"  const BASE_URL = '{_sanitize_string_literal(base_url)}';")
    else:
        lines.append("  const BASE_URL = '';")
    lines.append(f"  const url = BASE_URL + {path_expr};")

    # Axios call
    generic = f"<{resp_type}>" if use_typescript else ""
    lines.append(f"  const response = await axios.{method}{generic}(url")

    if has_body and method in ("post", "put", "patch"):
        lines[-1] += ", data"

    config_parts = []
    if query_params:
        config_parts.append("params")

    auth_header_lines = _format_auth_header_js(auth_entries)
    if auth_header_lines:
        header_str = ", ".join(auth_header_lines)
        config_parts.append(f"headers: {{ {header_str} }}")

    if config_parts:
        lines[-1] += ", { " + ", ".join(config_parts) + " }"

    lines[-1] += ");"
    lines.append("  return response.data;")
    lines.append("}")

    # Usage example
    lines.append(_build_js_usage_example(endpoint, processor))

    pagination = _detect_pagination(endpoint, processor)
    if pagination:
        func_name = _operation_to_func_name(endpoint)
        lines.append("")
        lines.append(
            _generate_pagination_helper_js(endpoint, processor, pagination, func_name, use_typescript=use_typescript)
        )

    return "\n".join(lines)


def _generate_ky_snippet(endpoint, processor, use_typescript: bool = False) -> str:
    lines = ["import ky from 'ky';", ""]
    base_url = _get_base_url(processor)
    method = endpoint.method.lower()
    has_body = endpoint.request_body is not None
    query_params = _get_query_params(endpoint)
    path_params = _get_path_params(endpoint)
    path_expr = _build_path_with_params(endpoint)
    auth_entries, auth_params = _build_auth_info(endpoint, processor)

    func_name = _operation_to_func_name(endpoint)

    # TypeScript interfaces
    if use_typescript:
        iface_block, req_type, resp_type, query_type = _build_ts_interfaces(endpoint, processor)
        if iface_block:
            lines.append(iface_block)
            lines.append("")

    # JSDoc
    jsdoc = _build_jsdoc_with_processor(endpoint, processor)
    lines.append(jsdoc)

    # Function signature
    params = []
    if use_typescript:
        for p in path_params:
            ts_type = _schema_to_ts_type(p.schema)
            params.append(f"{_sanitize_identifier(p.name)}: {ts_type}")
        if has_body:
            params.append(f"data: {req_type}")
        if query_params:
            optional = "?" if not any(p.required for p in query_params) else ""
            q_type = query_type or "Record<string, any>"
            params.append(f"params{optional}: {q_type}")
        for param_name, _ in auth_params:
            params.append(f"{param_name}: string")
        ret_type = f": Promise<{resp_type}>"
        sig = f"async function {func_name}({', '.join(params)}){ret_type} {{"
    else:
        for p in path_params:
            params.append(_sanitize_identifier(p.name))
        if has_body:
            params.append("data")
        if query_params:
            params.append("params = {}")
        for param_name, _ in auth_params:
            params.append(param_name)
        sig = f"async function {func_name}({', '.join(params)}) {{"

    lines.append(sig)

    # Base URL
    if base_url:
        lines.append(f"  const BASE_URL = '{_sanitize_string_literal(base_url)}';")
    else:
        lines.append("  const BASE_URL = '';")
    lines.append(f"  const url = BASE_URL + {path_expr};")

    # Ky call
    opts = []
    if has_body:
        opts.append("json: data")
    if query_params:
        opts.append("searchParams: params")

    auth_header_lines = _format_auth_header_js(auth_entries)
    if auth_header_lines:
        header_str = ", ".join(auth_header_lines)
        opts.append(f"headers: {{ {header_str} }}")

    generic = f"<{resp_type}>" if use_typescript else ""
    if opts:
        lines.append(f"  const response = await ky.{method}(url, {{")
        for opt in opts:
            lines.append(f"    {opt},")
        lines.append(f"  }}).json{generic}();")
    else:
        lines.append(f"  const response = await ky.{method}(url).json{generic}();")

    lines.append("  return response;")
    lines.append("}")

    # Usage example
    lines.append(_build_js_usage_example(endpoint, processor))

    pagination = _detect_pagination(endpoint, processor)
    if pagination:
        func_name = _operation_to_func_name(endpoint)
        lines.append("")
        lines.append(
            _generate_pagination_helper_js(endpoint, processor, pagination, func_name, use_typescript=use_typescript)
        )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Python generators
# ---------------------------------------------------------------------------


def _generate_requests_snippet(endpoint, processor, use_typescript: bool = False) -> str:
    lines = ["import requests"]

    base_url = _get_base_url(processor)
    method = endpoint.method.lower()
    has_body = endpoint.request_body is not None
    query_params = _get_query_params(endpoint)
    path_params = _get_path_params(endpoint)
    auth_entries, auth_params = _build_auth_info(endpoint, processor)

    # Type definitions
    types_block, req_type, resp_type, _ = _build_python_types(endpoint, processor)
    needs_typing = types_block or resp_type != "dict[str, Any]"

    imports = ["import requests"]
    if needs_typing:
        typing_imports = ["Any"]
        if "NotRequired" in types_block:
            typing_imports.append("NotRequired")
        if "Literal" in types_block:
            typing_imports.append("Literal")
        imports.append(f"from typing import {', '.join(sorted(typing_imports))}")
        if "TypedDict" in types_block:
            imports.append("from typing import TypedDict")

    lines = imports
    if types_block:
        lines.append("")
        lines.append("")
        lines.append(types_block)

    lines.append("")
    lines.append("")

    func_name = _operation_to_func_name(endpoint, snake_case=True)

    # Function signature
    params = []
    for p in path_params:
        py_type = _schema_to_python_type(p.schema)
        params.append(f"{_sanitize_identifier(p.name)}: {py_type}")
    if has_body:
        params.append(f"data: {req_type}")
    for p in query_params:
        py_type = _schema_to_python_type(p.schema)
        default = " = None" if not p.required else ""
        opt = " | None" if not p.required else ""
        params.append(f"{_sanitize_identifier(p.name)}: {py_type}{opt}{default}")
    for param_name, param_type in auth_params:
        params.append(f"{param_name}: {param_type}")

    ret_annotation = f" -> {resp_type}" if resp_type != "dict[str, Any]" else " -> dict[str, Any]"
    sig = f"def {func_name}({', '.join(params)}){ret_annotation}:"
    lines.append(sig)

    # Docstring
    docstring = _build_docstring(endpoint, processor)
    lines.append(docstring)

    # Base URL
    if base_url:
        lines.append(f'    base_url = "{_sanitize_string_literal(base_url)}"')
    else:
        lines.append('    base_url = ""')

    path_expr = _build_path_with_params(endpoint, python=True)
    lines.append(f"    url = base_url + {path_expr}")

    # Headers
    auth_header_py = _format_auth_header_py(auth_entries)
    if auth_header_py:
        lines.append(f"    headers = {{{', '.join(auth_header_py)}}}")

    # Query params
    if query_params:
        lines.append("    params = {")
        for p in query_params:
            lines.append(f'        "{p.name}": {_sanitize_identifier(p.name)},')
        lines.append("    }")
        lines.append("    params = {k: v for k, v in params.items() if v is not None}")

    # Request
    lines.append("")
    call_args = ["url"]
    if has_body:
        call_args.append("json=data")
    if query_params:
        call_args.append("params=params")
    if auth_header_py:
        call_args.append("headers=headers")

    lines.append(f"    response = requests.{method}({', '.join(call_args)})")
    lines.append("    response.raise_for_status()")

    if method == "delete" and "204" in endpoint.responses:
        lines.append("    return response")
    else:
        lines.append("    return response.json()")

    # Usage example
    lines.append(_build_python_usage_example(endpoint, processor, is_async=False))

    pagination = _detect_pagination(endpoint, processor)
    if pagination:
        func_name = _operation_to_func_name(endpoint, snake_case=True)
        lines.append("")
        lines.append(_generate_pagination_helper_py(endpoint, processor, pagination, func_name, is_async=False))

    return "\n".join(lines)


def _generate_httpx_snippet(endpoint, processor, use_typescript: bool = False) -> str:
    base_url = _get_base_url(processor)
    method = endpoint.method.lower()
    has_body = endpoint.request_body is not None
    query_params = _get_query_params(endpoint)
    path_params = _get_path_params(endpoint)
    auth_entries, auth_params = _build_auth_info(endpoint, processor)

    # Type definitions
    types_block, req_type, resp_type, _ = _build_python_types(endpoint, processor)
    needs_typing = types_block or resp_type != "dict[str, Any]"

    imports = ["import httpx"]
    if needs_typing:
        typing_imports = ["Any"]
        if "NotRequired" in types_block:
            typing_imports.append("NotRequired")
        if "Literal" in types_block:
            typing_imports.append("Literal")
        imports.append(f"from typing import {', '.join(sorted(typing_imports))}")
        if "TypedDict" in types_block:
            imports.append("from typing import TypedDict")

    lines = imports
    if types_block:
        lines.append("")
        lines.append("")
        lines.append(types_block)

    lines.append("")
    lines.append("")

    func_name = _operation_to_func_name(endpoint, snake_case=True)

    # Function signature
    params = []
    for p in path_params:
        py_type = _schema_to_python_type(p.schema)
        params.append(f"{_sanitize_identifier(p.name)}: {py_type}")
    if has_body:
        params.append(f"data: {req_type}")
    for p in query_params:
        py_type = _schema_to_python_type(p.schema)
        default = " = None" if not p.required else ""
        opt = " | None" if not p.required else ""
        params.append(f"{_sanitize_identifier(p.name)}: {py_type}{opt}{default}")
    for param_name, param_type in auth_params:
        params.append(f"{param_name}: {param_type}")

    ret_annotation = f" -> {resp_type}" if resp_type != "dict[str, Any]" else " -> dict[str, Any]"
    sig = f"async def {func_name}({', '.join(params)}){ret_annotation}:"
    lines.append(sig)

    # Docstring
    docstring = _build_docstring(endpoint, processor)
    lines.append(docstring)

    # Body
    lines.append("    async with httpx.AsyncClient() as client:")

    if base_url:
        lines.append(f'        base_url = "{_sanitize_string_literal(base_url)}"')
    else:
        lines.append('        base_url = ""')

    path_expr = _build_path_with_params(endpoint, python=True)
    lines.append(f"        url = base_url + {path_expr}")

    # Headers
    auth_header_py = _format_auth_header_py(auth_entries)
    if auth_header_py:
        lines.append(f"        headers = {{{', '.join(auth_header_py)}}}")

    # Query params
    if query_params:
        lines.append("        params = {")
        for p in query_params:
            lines.append(f'            "{p.name}": {_sanitize_identifier(p.name)},')
        lines.append("        }")
        lines.append("        params = {k: v for k, v in params.items() if v is not None}")

    # Request
    lines.append("")
    call_args = ["url"]
    if has_body:
        call_args.append("json=data")
    if query_params:
        call_args.append("params=params")
    if auth_header_py:
        call_args.append("headers=headers")

    lines.append(f"        response = await client.{method}({', '.join(call_args)})")
    lines.append("        response.raise_for_status()")

    if method == "delete" and "204" in endpoint.responses:
        lines.append("        return response")
    else:
        lines.append("        return response.json()")

    # Usage example
    lines.append(_build_python_usage_example(endpoint, processor, is_async=True))

    pagination = _detect_pagination(endpoint, processor)
    if pagination:
        func_name = _operation_to_func_name(endpoint, snake_case=True)
        lines.append("")
        lines.append(_generate_pagination_helper_py(endpoint, processor, pagination, func_name, is_async=True))

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# cURL generator
# ---------------------------------------------------------------------------


def _generate_curl_snippet(endpoint, processor, use_typescript: bool = False) -> str:
    base_url = _get_base_url(processor)
    method = endpoint.method.upper()
    has_body = endpoint.request_body is not None
    query_params = _get_query_params(endpoint)
    path_params = _get_path_params(endpoint)
    auth_entries, _ = _build_auth_info(endpoint, processor)

    # Build URL with path params substituted with example values
    url = base_url + endpoint.path
    for p in path_params:
        example_val = processor.generate_example_value(p.name, p.schema)
        url = url.replace(f"{{{p.name}}}", str(example_val))

    # Append query params
    if query_params:
        qparts = []
        for p in query_params:
            val = processor.generate_example_value(p.name, p.schema)
            qparts.append(f"{p.name}={val}")
        url += "?" + "&".join(qparts)

    lines = []

    # Comment header
    if endpoint.summary:
        lines.append(f"# {endpoint.summary}")
    lines.append(f"# {method} {endpoint.path}")

    if endpoint.deprecated:
        lines.append("# WARNING: This endpoint is deprecated")
    lines.append("")

    # Build curl command parts
    parts = [f"curl -X {method}"]
    parts.append(f"  '{url}'")

    # Headers
    if has_body:
        parts.append("  -H 'Content-Type: application/json'")

    auth_curl = _format_auth_header_curl(auth_entries)
    for h in auth_curl:
        parts.append(f"  {h}")

    # Request body
    if has_body and endpoint.request_body.schema:
        body = processor.generate_example_from_schema(endpoint.request_body.schema)
        body_json = json.dumps(body, indent=2, default=str)
        parts.append(f"  -d '{body_json}'")

    lines.append(" \\\n".join(parts))

    # Pagination hint
    pagination = _detect_pagination(endpoint, processor)
    if pagination:
        lines.append("")
        if pagination.style == "page_number":
            lines.append("# Pagination: page number style")
            lines.append("# Add ?page=2 (or &page=2) for subsequent pages.")
        elif pagination.style == "limit_offset":
            lines.append("# Pagination: limit/offset style")
            lines.append("# Adjust limit and offset params for subsequent pages.")
        else:
            lines.append("# Pagination: cursor style")
            lines.append("# Use the 'next' URL from the response to fetch the next page.")
        lines.append("# Response includes 'next' and 'previous' URLs for navigation.")

    return "\n".join(lines)
