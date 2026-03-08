<p align="center">
  <h1 align="center">drf-mcp-docs</h1>
  <p align="center">
    <strong>API documentation via MCP for AI coding agents</strong>
  </p>
  <p align="center">
    <a href="https://pypi.org/project/drf-mcp-docs/"><img src="https://img.shields.io/pypi/v/drf-mcp-docs.svg" alt="PyPI version"></a>
    <a href="https://pypi.org/project/drf-mcp-docs/"><img src="https://img.shields.io/pypi/pyversions/drf-mcp-docs.svg" alt="Python versions"></a>
    <a href="https://github.com/Abdulkhalek-1/drf-mcp-docs/blob/main/LICENSE"><img src="https://img.shields.io/github/license/Abdulkhalek-1/drf-mcp-docs.svg" alt="License"></a>
    <a href="https://github.com/Abdulkhalek-1/drf-mcp-docs/actions"><img src="https://img.shields.io/github/actions/workflow/status/Abdulkhalek-1/drf-mcp-docs/ci.yml?branch=main" alt="CI"></a>
  </p>
</p>

---

**drf-mcp-docs** exposes your Django REST Framework API **documentation** through the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) so AI coding agents can read, understand, and help you write correct frontend integration code.

> **How is this different from other Django+MCP packages?**
>
> Packages like `django-mcp-server` and `django-rest-framework-mcp` expose DRF **actions** as MCP tools — the AI agent calls your endpoints directly. **drf-mcp-docs** is fundamentally different: it exposes API **documentation** so AI agents can help developers **write frontend code** (React, Vue, Angular, etc.).
>
> Think of it as: *drf-spectacular generates docs for humans in a browser* → *drf-mcp-docs generates docs for AI agents via MCP*.

## Features

- **MCP Resources** — Browse your API structure: overview, endpoints, schemas, auth methods
- **MCP Tools** — Search endpoints, get detailed docs, generate request/response examples
- **Code Generation** — Generate frontend integration code (fetch, axios, ky) in JavaScript or TypeScript
- **Multi-adapter** — Works with drf-spectacular, drf-yasg, or DRF's built-in schema generation
- **Zero risk** — Read-only documentation exposure, no data mutation possible
- **Two transports** — stdio for local AI tools, streamable-http for remote/network access

## Quick Start

### 1. Install

```bash
pip install drf-mcp-docs
```

With a specific schema generator:

```bash
pip install drf-mcp-docs[spectacular]   # recommended
pip install drf-mcp-docs[yasg]
```

### 2. Configure

Add to your Django settings:

```python
INSTALLED_APPS = [
    # ...
    'rest_framework',
    'drf_mcp_docs',
]
```

That's it for basic usage. drf-mcp-docs auto-detects your schema generator.

### 3. Run

**stdio transport** (for local AI tools like Claude Code, Cursor, etc.):

```bash
python manage.py runmcpserver --transport stdio
```

**Streamable HTTP transport** (for network access):

```bash
python manage.py runmcpserver --transport streamable-http --host 0.0.0.0 --port 8100
```

### 4. Connect your AI tool

**Claude Code** (`~/.claude/claude_code_config.json`):

```json
{
  "mcpServers": {
    "my-api-docs": {
      "command": "python",
      "args": ["manage.py", "runmcpserver", "--transport", "stdio"],
      "cwd": "/path/to/your/django/project"
    }
  }
}
```

**Cursor** (`.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "my-api-docs": {
      "command": "python",
      "args": ["manage.py", "runmcpserver", "--transport", "stdio"],
      "cwd": "/path/to/your/django/project"
    }
  }
}
```

## What AI Agents Can Do

Once connected, your AI coding agent can:

```
You: "Show me all the product endpoints"
Agent: [reads api://endpoints resource, filters by tag]

You: "Generate a React hook to create a new product"
Agent: [calls get_endpoint_detail for POST /api/products/]
       [calls get_request_example for the request body]
       [calls generate_code_snippet with typescript + fetch]
       → Generates a complete, typed React hook with correct fields
```

### Available Resources

| Resource URI | Description |
|---|---|
| `api://overview` | API title, version, base URL, auth summary, tags, endpoint count |
| `api://endpoints` | All endpoints: path, method, summary, tags (compact listing) |
| `api://endpoints/{method}/{path}` | Full detail for one endpoint |
| `api://schemas` | All schema/model definitions (names + field summaries) |
| `api://schemas/{name}` | Full schema with properties, types, constraints |
| `api://auth` | Authentication guide with all auth methods |

### Available Tools

| Tool | Parameters | Description |
|---|---|---|
| `search_endpoints` | `query`, `method?`, `tag?` | Search endpoints by keyword |
| `get_endpoint_detail` | `path`, `method` | Full endpoint documentation |
| `get_request_example` | `path`, `method` | Example request body and parameters |
| `get_response_example` | `path`, `method`, `status_code?` | Example response |
| `generate_code_snippet` | `path`, `method`, `language?`, `client?` | Frontend integration code |
| `list_schemas` | — | All data model names and descriptions |
| `get_schema_detail` | `name` | Full schema with all fields and types |

## Configuration

All settings are optional. Add a `DRF_MCP_DOCS` dict to your Django settings:

```python
DRF_MCP_DOCS = {
    # Server
    'SERVER_NAME': 'my-api',                    # MCP server name (default: 'drf-mcp-docs')
    'SERVER_INSTRUCTIONS': 'Custom prompt...',   # Instructions shown to AI agents

    # Schema
    'SCHEMA_ADAPTER': None,                      # Auto-detect, or full dotted path
    'SCHEMA_PATH_PREFIX': '/api/',               # Only include endpoints under this prefix
    'EXCLUDE_PATHS': ['/api/internal/'],          # Paths to exclude
    'CACHE_SCHEMA': not DEBUG,                   # Cache in production, refresh in dev

    # Transport
    'TRANSPORT': 'streamable-http',              # Default transport: 'streamable-http' or 'stdio'
    'MCP_ENDPOINT': '/mcp/',                     # URL path for HTTP transport

    # Code generation
    'DEFAULT_CODE_LANGUAGE': 'javascript',       # 'javascript' or 'typescript'
    'DEFAULT_HTTP_CLIENT': 'fetch',              # 'fetch', 'axios', or 'ky'
}
```

### Schema Adapter Selection

drf-mcp-docs auto-detects your schema generator in this priority order:

1. **drf-spectacular** (recommended) — most complete OpenAPI 3.x output
2. **drf-yasg** — Swagger 2.0 auto-converted to OpenAPI 3.0
3. **DRF built-in** — basic fallback with limited schema detail

To force a specific adapter:

```python
DRF_MCP_DOCS = {
    'SCHEMA_ADAPTER': 'drf_mcp_docs.adapters.spectacular.SpectacularAdapter',
}
```

## ASGI Integration

For projects using ASGI, mount the MCP endpoint alongside your Django app:

```python
# asgi.py
from django.core.asgi import get_asgi_application
from drf_mcp_docs.urls import mount_mcp

django_app = get_asgi_application()
application = mount_mcp(django_app)  # Mounts at /mcp/ by default
```

With custom path:

```python
application = mount_mcp(django_app, path="/api-docs-mcp/")
```

## Development

```bash
git clone https://github.com/Abdulkhalek-1/drf-mcp-docs.git
cd drf-mcp-docs
pip install -e ".[dev]"
pytest
```

## How It Works

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐     ┌───────────┐
│  AI Agent   │────>│  MCP Server  │────>│ Schema Processor │────>│  Adapter  │
│ (Claude,    │<────│  (FastMCP)   │<────│  (OpenAPI dict   │<────│ (spectac- │
│  Cursor...) │     │              │     │   → structured)  │     │  ular,    │
└─────────────┘     └──────────────┘     └─────────────────┘     │  yasg,    │
                    Resources + Tools     Dataclasses + Search    │  DRF)     │
                                                                  └───────────┘
```

1. **Adapter** pulls the OpenAPI schema from your chosen generator
2. **Processor** transforms the raw dict into structured, AI-friendly dataclasses
3. **MCP Server** exposes resources (browsable docs) and tools (search, examples, code gen)
4. **AI Agent** connects via stdio or HTTP, reads your API docs, helps write frontend code

## License

MIT License. See [LICENSE](LICENSE) for details.
