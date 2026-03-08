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
├── __init__.py              # Version, default_app_config
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

def get_processor() -> SchemaProcessor:
    global _processor
    cache = get_setting("CACHE_SCHEMA")
    if _processor is not None and cache:
        return _processor
    adapter = get_adapter()
    openapi_schema = adapter.get_schema()
    _processor = SchemaProcessor(openapi_schema)
    return _processor
```

- **`DEBUG=True`** (dev): Schema is regenerated on every request
- **`DEBUG=False`** (prod): Schema is generated once and cached in the global `_processor`

## Dataclass Hierarchy

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

The `generate_code_snippet` tool delegates to one of three generator functions:

```
generate_code_snippet(path, method, language, client)
    │
    ├── client="fetch"  ──>  _generate_fetch_snippet()
    ├── client="axios"  ──>  _generate_axios_snippet()
    └── client="ky"     ──>  _generate_ky_snippet()
```

Each generator:

1. Reads the endpoint's parameters, request body, and auth requirements
2. Builds a function signature (JS or TS)
3. Generates the HTTP call with proper parameter handling
4. Returns the code as a string

Helper functions:

- `_build_path_with_params()` — Converts `{id}` to `${id}` template literals
- `_get_query_params()` — Filters parameters by location
- `_operation_to_func_name()` — Converts operationId to camelCase
- `_schema_to_ts_type()` — Maps JSON Schema types to TypeScript types

## Singleton Pattern

The MCP server uses a singleton to avoid creating multiple FastMCP instances:

```python
# server/__init__.py
_server: FastMCP | None = None

def get_mcp_server() -> FastMCP:
    global _server
    if _server is None:
        from drf_mcp_docs.server.instance import create_mcp_server
        _server = create_mcp_server()
    return _server
```

This ensures resources and tools are registered exactly once, regardless of how many times `get_mcp_server()` is called.

## Extension Points

1. **Custom adapters** — Subclass `BaseSchemaAdapter` for any OpenAPI source
2. **Settings** — All behavior is configurable via the `DRF_MCP_DOCS` dict
3. **Server customization** — Get the FastMCP instance via `get_mcp_server()` and add custom resources/tools before mounting
