# ASGI Integration

For projects using ASGI (e.g., with `uvicorn` or `daphne`), you can mount the MCP server alongside your Django application at a URL path. This lets MCP clients connect over HTTP without running a separate process.

## Basic Setup

### 1. Update `asgi.py`

```python
# myproject/asgi.py
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')

django_app = get_asgi_application()

# Mount MCP alongside Django
from drf_mcp_docs.urls import mount_mcp
application = mount_mcp(django_app)
```

This mounts the MCP server at `/mcp/` (default) and routes everything else to Django.

### 2. Run with ASGI server

```bash
uvicorn myproject.asgi:application --host 0.0.0.0 --port 8000
```

The MCP endpoint will be available at `http://localhost:8000/mcp/`.

## Custom Mount Path

```python
from drf_mcp_docs.urls import mount_mcp

application = mount_mcp(django_app, path="/api-docs-mcp/")
```

Or configure via settings:

```python
# settings.py
DRF_MCP_DOCS = {
    'MCP_ENDPOINT': '/api-docs-mcp/',
}
```

## Custom Server Instance

If you need to customize the MCP server before mounting:

```python
from drf_mcp_docs.server import get_mcp_server
from drf_mcp_docs.urls import mount_mcp

mcp = get_mcp_server()
# ... customize mcp if needed ...
application = mount_mcp(django_app, mcp=mcp, path="/mcp/")
```

## How It Works

The `mount_mcp()` function creates an ASGI application that:

1. Checks if incoming requests match the MCP path prefix
2. Routes matching requests to the FastMCP streamable-http handler
3. Routes everything else to the Django ASGI application

```
Client Request
     │
     ▼
┌─────────────────┐
│ mount_mcp ASGI  │
│                 │
│ path starts     │──yes──> FastMCP (streamable-http)
│ with /mcp/ ?    │
│                 │──no───> Django ASGI app
└─────────────────┘
```

## Custom ASGI Wrappers

If you write your own ASGI `application` function that wraps `mount_mcp()` (e.g., to add WebSocket routing or other protocol handling), you **must** forward `lifespan` events to the `mount_mcp` app. The MCP server uses the ASGI lifespan protocol to initialize its internal task group — without it, all MCP requests will fail with:

```
RuntimeError: Task group is not initialized. Make sure to use run().
```

### Example: Combining MCP with WebSockets

```python
# myproject/asgi.py
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")

django_app = get_asgi_application()

from drf_mcp_docs.urls import mount_mcp
django_app = mount_mcp(django_app)

from myproject.websocket import websocket_application


async def application(scope, receive, send):
    if scope["type"] == "http":
        await django_app(scope, receive, send)
    elif scope["type"] == "websocket":
        await websocket_application(scope, receive, send)
    elif scope["type"] == "lifespan":
        # Required: forward lifespan events so the MCP server can initialize
        await django_app(scope, receive, send)
    else:
        raise NotImplementedError(f"Unknown scope type {scope['type']}")
```

!!! warning
    A common mistake is to only route `http` and `websocket` scopes while ignoring `lifespan`. If `lifespan` events are not forwarded to the `mount_mcp` wrapper, the MCP server's task group will never be started and every request to the MCP endpoint will return a 500 error.

## WSGI Projects

If your project uses WSGI (the default for Django), you have two options:

### Option A: Use stdio transport (recommended)

Run the MCP server as a separate process using the management command:

```bash
python manage.py runmcpserver --transport stdio
```

This works with WSGI projects — no ASGI conversion needed.

### Option B: Use the management command with HTTP

```bash
python manage.py runmcpserver --transport streamable-http --port 8100
```

This starts a standalone HTTP server on port 8100, separate from your Django process.

### Option C: Migrate to ASGI

If you want the integrated ASGI approach:

1. Install an ASGI server: `pip install uvicorn`
2. Create/update `asgi.py` as shown above
3. Run with `uvicorn` instead of `gunicorn`/`runserver`

## Connecting MCP Clients to HTTP

When using streamable-http (either via ASGI mount or the management command), configure your MCP client:

```json
{
  "mcpServers": {
    "my-api": {
      "url": "http://localhost:8000/mcp/"
    }
  }
}
```

Or for a standalone server on a different port:

```json
{
  "mcpServers": {
    "my-api": {
      "url": "http://localhost:8100/mcp/"
    }
  }
}
```

## Production Considerations

- The MCP endpoint does **not** require authentication by default — it only exposes API documentation, not data
- Consider placing the MCP endpoint behind a firewall or VPN if your API schema is sensitive
- The `CACHE_SCHEMA` setting (default: `True` in production) ensures the schema is generated once and reused. Set `CACHE_TTL` (seconds) to automatically refresh the cache periodically, or call `invalidate_schema_cache()` to force an immediate refresh.
- For high-availability setups, each ASGI worker holds its own cached schema copy
