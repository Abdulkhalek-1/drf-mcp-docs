# Getting Started

This guide walks you through installing, configuring, and running drf-mcp-docs with your Django REST Framework project.

## Prerequisites

- Python 3.10+
- Django 4.2+
- Django REST Framework 3.14+
- A schema generator (recommended: drf-spectacular)

## Installation

Install drf-mcp-docs from PyPI:

```bash
pip install drf-mcp-docs
```

For the best experience, install with drf-spectacular (provides the most complete OpenAPI schemas):

```bash
pip install drf-mcp-docs[spectacular]
```

Or with drf-yasg:

```bash
pip install drf-mcp-docs[yasg]
```

If you don't install either, drf-mcp-docs falls back to DRF's built-in schema generation, which produces more limited output.

## Configuration

### 1. Add to INSTALLED_APPS

```python
# settings.py
INSTALLED_APPS = [
    # ...
    'rest_framework',
    'drf_spectacular',  # or 'drf_yasg' — if using one
    'drf_mcp_docs',
]
```

### 2. Configure your schema generator

If using drf-spectacular:

```python
REST_FRAMEWORK = {
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}
```

### 3. (Optional) Customize drf-mcp-docs settings

All settings have sensible defaults. You only need to add this if you want to customize behavior:

```python
DRF_MCP_DOCS = {
    'SERVER_NAME': 'my-project-api',
    'CACHE_SCHEMA': not DEBUG,
}
```

See [Configuration](configuration.md) for all available settings.

## Running the MCP Server

### stdio transport (recommended for local AI tools)

```bash
python manage.py runmcpserver --transport stdio
```

This is the most common setup. Your AI tool (Claude Code, Cursor, etc.) launches this command as a subprocess and communicates via stdin/stdout.

### streamable-http transport (for network access)

```bash
python manage.py runmcpserver --transport streamable-http --host 0.0.0.0 --port 8100
```

Use this when the AI tool connects over the network.

## Connecting AI Tools

### Claude Code

Add to your Claude Code MCP configuration (`~/.claude.json`):

```json
{
  "mcpServers": {
    "my-api": {
      "command": "python",
      "args": ["manage.py", "runmcpserver", "--transport", "stdio"],
      "cwd": "/path/to/your/django/project"
    }
  }
}
```

If you use a virtual environment:

```json
{
  "mcpServers": {
    "my-api": {
      "command": "/path/to/venv/bin/python",
      "args": ["manage.py", "runmcpserver", "--transport", "stdio"],
      "cwd": "/path/to/your/django/project"
    }
  }
}
```

### Cursor

Add to `.cursor/mcp.json` in your project root:

```json
{
  "mcpServers": {
    "my-api": {
      "command": "python",
      "args": ["manage.py", "runmcpserver", "--transport", "stdio"],
      "cwd": "/path/to/your/django/project"
    }
  }
}
```

### VS Code (with MCP extension)

Add to your VS Code settings or workspace `.vscode/mcp.json`:

```json
{
  "servers": {
    "my-api": {
      "command": "python",
      "args": ["manage.py", "runmcpserver", "--transport", "stdio"],
      "cwd": "/path/to/your/django/project"
    }
  }
}
```

### Other MCP clients

For any MCP client that supports streamable-http:

1. Start the server: `python manage.py runmcpserver --transport streamable-http --port 8100`
2. Connect to: `http://localhost:8100/mcp/`

## Verify It Works

After connecting, ask your AI agent:

> "Show me an overview of the API"

The agent should read the `api://overview` resource and return information about your API — title, version, endpoints count, authentication methods, etc.

Try more:

> "What endpoints are available for users?"

> "Generate a fetch function to create a new product"

> "Show me the Product schema"

## Next Steps

- [Configuration](configuration.md) — All settings and customization options
- [Resources & Tools](resources-and-tools.md) — Full reference for MCP resources and tools
- [Schema Adapters](schema-adapters.md) — How adapters work and writing custom ones
- [Code Generation](code-generation.md) — Supported languages, clients, and output
- [ASGI Integration](asgi-integration.md) — Mounting alongside your ASGI application
