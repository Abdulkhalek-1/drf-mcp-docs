# Architecture

This page describes the internal architecture of drf-mcp-docs for contributors and advanced users.

## Overview

```
┌───────────────────────────────────────────────────────────────────────┐
│                          drf-mcp-docs                                      │
│                                                                       │
│  ┌─────────────┐   ┌──────────────────┐   ┌───────────────────────┐  │
│  │  Adapters    │──>│  Schema Processor │──>│    MCP Server         │  │
│  │             │   │                  │   │                       │  │
│  │ spectacular │   │ OpenAPI dict     │   │ Resources (6)         │  │
│  │ yasg        │   │    ↓             │   │ Tools (7)             │  │
│  │ drf builtin │   │ Dataclasses      │   │                       │  │
│  │ (custom)    │   │ Search/Filter    │   │ stdio / streamable-   │  │
│  │             │   │ Example gen      │   │ http transport        │  │
│  └─────────────┘   └──────────────────┘   └───────────────────────┘  │
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │  Django Integration                                             │  │
│  │  AppConfig · Settings · Management Command · ASGI Mount         │  │
│  └─────────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────────┘
```

## Module Layout

```
src/drf_mcp_docs/
├── __init__.py              # Version, public API (invalidate_schema_cache)
├── apps.py                  # Django AppConfig
├── settings.py              # Settings reader with defaults
├── urls.py                  # ASGI mount helper
├── adapters/
│   ├── __init__.py          # get_adapter() — auto-detection logic
│   ├── base.py              # BaseSchemaAdapter (ABC)
│   ├── spectacular.py       # SpectacularAdapter
│   ├── yasg.py              # YasgAdapter + Swagger→OpenAPI converter
│   └── drf.py               # DRFBuiltinAdapter
├── schema/
│   ├── __init__.py
│   ├── types.py             # Dataclasses: Endpoint, Parameter, etc.
│   └── processor.py         # SchemaProcessor — transforms OpenAPI dict
├── server/
│   ├── __init__.py          # get_mcp_server() singleton
│   ├── instance.py          # create_mcp_server() + get_processor()
│   ├── resources.py         # MCP resource definitions
│   └── tools.py             # MCP tool definitions + code generators
└── management/
    └── commands/
        └── runmcpserver.py  # Management command
```

## Data Flow

### 1. Schema Acquisition

```
DRF Schema Generator  ──adapter.get_schema()──>  OpenAPI 3.x dict
```

The adapter layer abstracts over different schema generators. Each adapter calls its generator's API and returns a normalized OpenAPI 3.x Python dict.

The `YasgAdapter` includes an additional conversion step: Swagger 2.0 → OpenAPI 3.0.

### 2. Schema Processing

```
OpenAPI dict  ──SchemaProcessor──>  Structured dataclasses
```

`SchemaProcessor` takes the raw OpenAPI dict and provides methods to extract structured data:

- **`get_overview()`** — Extracts info, servers, tags, counts endpoints
- **`get_endpoints(tag=None)`** — Iterates paths/methods, resolves `$ref` in parameters and request bodies
- **`get_endpoint(path, method)`** — Returns a single `Endpoint` dataclass
- **`get_schemas()`** — Extracts `components/schemas` into `SchemaDefinition` objects
- **`get_auth_methods()`** — Extracts `components/securitySchemes` into `AuthMethod` objects
- **`search_endpoints(query)`** — Full-text search across paths, summaries, descriptions
- **`generate_example_from_schema(schema)`** — Generates plausible example values from JSON schemas
- **`resolve_ref(ref)`** — Follows `$ref` pointers within the schema

### 3. MCP Server

```
SchemaProcessor  ──resources/tools──>  FastMCP server  ──transport──>  AI Agent
```

The MCP server uses the official `mcp` Python SDK's `FastMCP` class. Resources and tools are registered as functions that call `get_processor()` to get the (cached) processor instance.

### Schema Caching

```python
# server/instance.py
_processor: SchemaProcessor | None = None
_processor_cached_at: float | None = None
_processor_lock = threading.Lock()

def get_processor() -> SchemaProcessor:
    global _processor, _processor_cached_at
    cache = get_setting("CACHE_SCHEMA")
    if _processor is not None and cache and not _is_cache_expired():
        return _processor
    with _processor_lock:
        if _processor is not None and cache and not _is_cache_expired():
            return _processor
        adapter = get_adapter()
        openapi_schema = _filter_paths(adapter.get_schema())
        _processor = SchemaProcessor(openapi_schema)
        _processor_cached_at = time.monotonic()
        return _processor
```

- **`DEBUG=True`** (dev): Schema is regenerated on every request
- **`DEBUG=False`** (prod): Schema is generated once and cached in the global `_processor`
- **TTL expiration**: When `CACHE_TTL` is set (seconds), the cached processor is automatically rebuilt after the TTL elapses. When `None` (default), the cache lives forever.
- **Manual invalidation**: Call `invalidate_schema_cache()` to force-clear the cache from any thread (signal handlers, management commands, etc.)
- **Thread safety**: Double-checked locking ensures safe concurrent access under multi-worker deployments. `invalidate_schema_cache()` acquires the same lock.

Additionally, `SchemaProcessor` caches resolved `$ref` pointers internally (`_ref_cache`) to avoid redundant resolution of the same references.

## Dataclass Hierarchy

All dataclasses are **frozen** (`frozen=True`) to ensure immutability after construction. This prevents accidental mutation of schema data during processing.

```
APIOverview
├── title, description, version, base_url
├── auth_methods: list[AuthMethod]
├── tags: list[Tag]
└── endpoint_count: int

Endpoint
├── path, method, operation_id, summary, description
├── tags: list[str]
├── parameters: list[Parameter]
│   └── name, location, required, schema, description
├── request_body: RequestBody | None
│   └── content_type, schema, required, example
├── responses: dict[str, Response]
│   └── status_code, description, schema, example
├── auth_required, auth_methods, deprecated

SchemaDefinition
├── name, type, description
├── properties: dict  (field name → type/format/constraints)
└── required: list[str]

AuthMethod
├── name, type, description
├── header_name, scheme
```

## Code Generation Architecture

The `generate_code_snippet` tool delegates to one of five generator functions based on language and client:

```
generate_code_snippet(path, method, language, client)
    │
    ├── client="fetch"     ──>  _generate_fetch_snippet()      (JS/TS)
    ├── client="axios"     ──>  _generate_axios_snippet()      (JS/TS)
    ├── client="ky"        ──>  _generate_ky_snippet()         (JS/TS)
    ├── client="requests"  ──>  _generate_requests_snippet()   (Python, sync)
    └── client="httpx"     ──>  _generate_httpx_snippet()      (Python, async)
```

Each generator produces self-documenting code with:

1. Import statements (where applicable)
2. Type definitions — TypeScript interfaces or Python TypedDicts from OpenAPI schemas
3. JSDoc (JS/TS) or Google-style docstrings (Python) with `@param`, `@returns`, `@deprecated`
4. Base URL from the OpenAPI spec's `servers[0].url`
5. Auth headers based on actual security schemes (bearer, basic, apiKey)
6. The HTTP call with proper parameter handling
7. A commented usage example with realistic data

The tool also returns structured `metadata` alongside the code (function name, endpoint info, auth details, parameter breakdown, response summary).

Helper functions:

- `_build_path_with_params()` — Converts `{id}` to `${id}` (JS) or `{id}` f-string (Python)
- `_get_query_params()` / `_get_path_params()` — Filter parameters by location
- `_operation_to_func_name()` — Converts operationId to camelCase (JS) or snake_case (Python)
- `_schema_to_ts_type()` / `_schema_to_python_type()` — Map JSON Schema types to language types
- `_schema_to_ts_interface()` — Generate TypeScript interfaces from OpenAPI schemas
- `_schema_to_python_typeddict()` — Generate Python TypedDicts from OpenAPI schemas
- `_build_auth_info()` — Resolve auth headers from security schemes
- `_build_jsdoc_with_processor()` / `_build_docstring()` — Generate documentation blocks
- `_build_js_usage_example()` / `_build_python_usage_example()` — Generate usage comments
- `_build_ts_interfaces()` / `_build_python_types()` — Orchestrate type generation for an endpoint

## Singleton Pattern

The MCP server uses a thread-safe singleton to avoid creating multiple FastMCP instances:

```python
# server/__init__.py
_server: FastMCP | None = None
_server_lock = threading.Lock()

def get_mcp_server() -> FastMCP:
    global _server
    if _server is None:
        with _server_lock:
            if _server is None:
                from drf_mcp_docs.server.instance import create_mcp_server
                _server = create_mcp_server()
    return _server
```

Double-checked locking ensures resources and tools are registered exactly once, even under concurrent access from multiple threads.

## Extension Points

1. **Custom adapters** — Subclass `BaseSchemaAdapter` for any OpenAPI source
2. **Settings** — All behavior is configurable via the `DRF_MCP_DOCS` dict
3. **Server customization** — Get the FastMCP instance via `get_mcp_server()` and add custom resources/tools before mounting
