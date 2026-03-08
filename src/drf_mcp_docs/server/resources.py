from __future__ import annotations

import json
from dataclasses import asdict

from mcp.server.fastmcp import FastMCP

from drf_mcp_docs.server.instance import get_processor


def _serialize(obj) -> str:
    return json.dumps(asdict(obj) if hasattr(obj, "__dataclass_fields__") else obj, indent=2, default=str)


def _serialize_list(items) -> str:
    return json.dumps(
        [asdict(item) for item in items],
        indent=2,
        default=str,
    )


def api_overview() -> str:
    """API overview: title, description, version, base URL, auth methods, tags, endpoint count."""
    processor = get_processor()
    overview = processor.get_overview()
    return _serialize(overview)


def api_endpoints() -> str:
    """List all API endpoints with path, method, summary, and tags."""
    processor = get_processor()
    endpoints = processor.get_endpoints()
    compact = [
        {
            "path": ep.path,
            "method": ep.method,
            "summary": ep.summary,
            "tags": ep.tags,
            "auth_required": ep.auth_required,
            "deprecated": ep.deprecated,
        }
        for ep in endpoints
    ]
    return json.dumps(compact, indent=2)


def api_endpoint_detail(method: str, path: str) -> str:
    """Full detail for one endpoint: params, body, responses, auth, examples."""
    processor = get_processor()
    if not path.startswith("/"):
        path = "/" + path
    endpoint = processor.get_endpoint(path, method)
    if endpoint is None:
        return json.dumps({"error": f"Endpoint {method.upper()} {path} not found"})
    return _serialize(endpoint)


def api_schemas() -> str:
    """All schema/model definitions with names and field summaries."""
    processor = get_processor()
    schemas = processor.get_schemas()
    compact = [
        {
            "name": s.name,
            "type": s.type,
            "fields": list(s.properties.keys()),
            "description": s.description,
        }
        for s in schemas
    ]
    return json.dumps(compact, indent=2)


def api_schema_detail(name: str) -> str:
    """Full schema definition with properties, types, and constraints."""
    processor = get_processor()
    schema = processor.get_schema_definition(name)
    if schema is None:
        return json.dumps({"error": f"Schema '{name}' not found"})
    return _serialize(schema)


def api_auth() -> str:
    """Authentication guide: all auth methods with details."""
    processor = get_processor()
    auth_methods = processor.get_auth_methods()
    return _serialize_list(auth_methods)


def register_resources(mcp: FastMCP):
    mcp.resource("api://overview")(api_overview)
    mcp.resource("api://endpoints")(api_endpoints)
    mcp.resource("api://endpoints/{method}/{path}")(api_endpoint_detail)
    mcp.resource("api://schemas")(api_schemas)
    mcp.resource("api://schemas/{name}")(api_schema_detail)
    mcp.resource("api://auth")(api_auth)
