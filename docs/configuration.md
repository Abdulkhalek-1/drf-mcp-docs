# Configuration

All drf-mcp-docs settings live in a single `DRF_MCP_DOCS` dictionary in your Django `settings.py`. Every setting has a sensible default — you only need to configure what you want to change.

## Full Settings Reference

```python
DRF_MCP_DOCS = {
    # ── Server ─────────────────────────────────────────────────
    'SERVER_NAME': 'drf-mcp-docs',
    'SERVER_INSTRUCTIONS': '',

    # ── Schema ─────────────────────────────────────────────────
    'SCHEMA_ADAPTER': None,
    'SCHEMA_PATH_PREFIX': '/api/',
    'EXCLUDE_PATHS': [],
    'CACHE_SCHEMA': not DEBUG,
    'CACHE_TTL': None,

    # ── Transport ──────────────────────────────────────────────
    'TRANSPORT': 'streamable-http',
    'MCP_ENDPOINT': '/mcp/',

    # ── Code Generation ────────────────────────────────────────
    'DEFAULT_CODE_LANGUAGE': 'javascript',
    'DEFAULT_HTTP_CLIENT': 'fetch',
}
```

## Settings Detail

### Server Settings

#### `SERVER_NAME`

- **Type:** `str`
- **Default:** `'drf-mcp-docs'`

The name of the MCP server, shown to AI agents during connection.

```python
DRF_MCP_DOCS = {
    'SERVER_NAME': 'my-ecommerce-api',
}
```

#### `SERVER_INSTRUCTIONS`

- **Type:** `str`
- **Default:** `''` (uses built-in instructions)

Custom instructions shown to AI agents when they connect. Use this to give agents context about your API:

```python
DRF_MCP_DOCS = {
    'SERVER_INSTRUCTIONS': (
        'This is the backend API for an e-commerce platform. '
        'All endpoints require JWT authentication except the product listing. '
        'The frontend is built with Next.js and uses TypeScript.'
    ),
}
```

When empty, drf-mcp-docs uses detailed default instructions with structured workflow guidance that describes all available resources and tools, helping AI agents effectively navigate the API documentation.

### Schema Settings

#### `SCHEMA_ADAPTER`

- **Type:** `str | None`
- **Default:** `None` (auto-detect)

Full dotted path to the adapter class to use for schema generation. When `None`, drf-mcp-docs auto-detects in this order:

1. `drf_mcp_docs.adapters.spectacular.SpectacularAdapter` (if drf-spectacular is installed)
2. `drf_mcp_docs.adapters.yasg.YasgAdapter` (if drf-yasg is installed)
3. `drf_mcp_docs.adapters.drf.DRFBuiltinAdapter` (always available)

To force a specific adapter:

```python
DRF_MCP_DOCS = {
    'SCHEMA_ADAPTER': 'drf_mcp_docs.adapters.yasg.YasgAdapter',
}
```

To use a custom adapter:

```python
DRF_MCP_DOCS = {
    'SCHEMA_ADAPTER': 'myapp.adapters.MyCustomAdapter',
}
```

See [Schema Adapters](schema-adapters.md) for writing custom adapters.

#### `SCHEMA_PATH_PREFIX`

- **Type:** `str`
- **Default:** `'/api/'`

Only include endpoints whose paths start with this prefix. Useful for filtering out admin or internal URLs.

```python
DRF_MCP_DOCS = {
    'SCHEMA_PATH_PREFIX': '/api/v2/',  # Only v2 endpoints
}
```

#### `EXCLUDE_PATHS`

- **Type:** `list[str]`
- **Default:** `[]`

Paths to exclude from the documentation. Exact prefix matching.

```python
DRF_MCP_DOCS = {
    'EXCLUDE_PATHS': [
        '/api/internal/',
        '/api/debug/',
        '/api/admin/',
    ],
}
```

#### `CACHE_SCHEMA`

- **Type:** `bool`
- **Default:** `not DEBUG`

Whether to cache the parsed schema. When `True`, the schema is loaded once and reused for all requests. When `False`, the schema is regenerated on every request (useful during development).

```python
DRF_MCP_DOCS = {
    'CACHE_SCHEMA': False,  # Always refresh (development)
}
```

In production (`DEBUG=False`), caching is enabled by default for performance.

#### `CACHE_TTL`

- **Type:** `int | None`
- **Default:** `None` (no expiration)

Time-to-live for the cached schema processor, in seconds. When set, the schema is automatically rebuilt after the TTL expires on the next request. When `None`, the cache lives forever (until the process restarts).

```python
DRF_MCP_DOCS = {
    'CACHE_TTL': 300,  # Rebuild schema every 5 minutes
}
```

This is useful when your API schema may change at runtime (e.g., dynamic endpoint registration) and you want stale data to eventually refresh without restarting the server.

#### Programmatic Cache Invalidation

For immediate cache invalidation (rather than waiting for TTL expiry), use the `invalidate_schema_cache()` function:

```python
from drf_mcp_docs import invalidate_schema_cache

# Force the next get_processor() call to rebuild from scratch
invalidate_schema_cache()
```

This is thread-safe and can be called from anywhere — signal handlers, management commands, views, etc.

##### Example: invalidate on model change

```python
from django.db.models.signals import post_save
from django.dispatch import receiver

from drf_mcp_docs import invalidate_schema_cache
from myapp.models import DynamicEndpoint

@receiver(post_save, sender=DynamicEndpoint)
def refresh_mcp_schema(sender, **kwargs):
    invalidate_schema_cache()
```

#### Debug Logging

All drf-mcp-docs modules emit structured debug logs under the `drf_mcp_docs` logger namespace. Enable via Django's standard `LOGGING` config:

```python
LOGGING = {
    'version': 1,
    'handlers': {
        'console': {'class': 'logging.StreamHandler'},
    },
    'loggers': {
        'drf_mcp_docs': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
    },
}
```

This logs adapter selection, schema processing, cache lifecycle, tool invocations, resource access, ASGI routing, and settings resolution. See [Architecture — Debug Logging](architecture.md#debug-logging) for the full list of logged modules.

### Transport Settings

#### `TRANSPORT`

- **Type:** `str`
- **Default:** `'streamable-http'`

Default transport when running `python manage.py runmcpserver` without the `--transport` flag.

- `'stdio'` — stdin/stdout communication. Used when the AI tool launches the server as a subprocess.
- `'streamable-http'` — HTTP-based transport. Used for network access.

```python
DRF_MCP_DOCS = {
    'TRANSPORT': 'stdio',  # Default to stdio
}
```

Can always be overridden via the command line:

```bash
python manage.py runmcpserver --transport stdio
```

#### `MCP_ENDPOINT`

- **Type:** `str`
- **Default:** `'/mcp/'`

URL path prefix when using the ASGI mount helper. Only relevant for streamable-http transport with `mount_mcp()`.

```python
DRF_MCP_DOCS = {
    'MCP_ENDPOINT': '/api-docs-mcp/',
}
```

### Code Generation Settings

#### `DEFAULT_CODE_LANGUAGE`

- **Type:** `str`
- **Default:** `'javascript'`

Default language for the `generate_code_snippet` tool when no language is specified. Options: `'javascript'`, `'typescript'`, `'python'`, `'curl'`.

```python
DRF_MCP_DOCS = {
    'DEFAULT_CODE_LANGUAGE': 'typescript',
}
```

#### `DEFAULT_HTTP_CLIENT`

- **Type:** `str`
- **Default:** `'fetch'`

Default HTTP client library for code generation. Options: `'fetch'`, `'axios'`, `'ky'` (JS/TS), `'requests'`, `'httpx'` (Python). When the client doesn't match the language, it is auto-selected (e.g., `python` + `fetch` → `requests`).

```python
DRF_MCP_DOCS = {
    'DEFAULT_HTTP_CLIENT': 'axios',
}
```

## Example: Production Configuration

```python
DRF_MCP_DOCS = {
    'SERVER_NAME': 'acme-api',
    'SERVER_INSTRUCTIONS': (
        'ACME Corp API. Uses JWT auth. '
        'Frontend is React + TypeScript with axios.'
    ),
    'SCHEMA_ADAPTER': 'drf_mcp_docs.adapters.spectacular.SpectacularAdapter',
    'EXCLUDE_PATHS': ['/api/internal/', '/api/webhooks/'],
    'CACHE_SCHEMA': True,
    'CACHE_TTL': 300,  # Refresh schema every 5 minutes
    'DEFAULT_CODE_LANGUAGE': 'typescript',
    'DEFAULT_HTTP_CLIENT': 'axios',
}
```

## Example: Development Configuration

```python
DRF_MCP_DOCS = {
    'CACHE_SCHEMA': False,  # Always see latest schema changes
    'TRANSPORT': 'stdio',
}
```
