# Example Project

A minimal Django project demonstrating drf-mcp-docs with drf-spectacular. The source code is in the [`example/`](https://github.com/Abdulkhalek-1/drf-mcp-docs/tree/main/example) directory.

## What's Included

- **Author** and **Book** models with a foreign key relationship
- Full CRUD endpoints via DRF ModelViewSets
- A custom `in_stock` action on the Book endpoint
- drf-spectacular for OpenAPI schema generation
- drf-mcp-docs configured and ready to use

## Quick Start

```bash
cd example
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
```

!!! tip
    If you're working from the drf-mcp-docs repo, install the package in editable mode instead:
    ```bash
    pip install -e "..[spectacular]"
    ```

## Running the MCP Server

### stdio transport (for local AI tools)

```bash
python manage.py runmcpserver --transport stdio
```

### streamable-http transport (for network access)

```bash
python manage.py runmcpserver --transport streamable-http --port 8100
```

### ASGI mount (alongside Django)

```bash
pip install uvicorn
uvicorn example_project.asgi:application --host 0.0.0.0 --port 8000
```

The MCP endpoint will be at `http://localhost:8000/mcp/`.

## Validate Configuration

```bash
python manage.py checkmcpconfig
```

## Connecting AI Tools

### Claude Code

Add to `~/.claude.json`:

```json
{
  "mcpServers": {
    "bookstore-api": {
      "command": "/path/to/example/.venv/bin/python",
      "args": ["manage.py", "runmcpserver", "--transport", "stdio"],
      "cwd": "/path/to/example"
    }
  }
}
```

### Cursor

Add to `.cursor/mcp.json` in your project root:

```json
{
  "mcpServers": {
    "bookstore-api": {
      "command": "/path/to/example/.venv/bin/python",
      "args": ["manage.py", "runmcpserver", "--transport", "stdio"],
      "cwd": "/path/to/example"
    }
  }
}
```

### VS Code

Add to `.vscode/mcp.json`:

```json
{
  "servers": {
    "bookstore-api": {
      "command": "/path/to/example/.venv/bin/python",
      "args": ["manage.py", "runmcpserver", "--transport", "stdio"],
      "cwd": "/path/to/example"
    }
  }
}
```

## Configuration

The example uses these settings in `example_project/settings.py`:

```python
REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

DRF_MCP_DOCS = {
    "SERVER_NAME": "bookstore-api",
    "SERVER_INSTRUCTIONS": "This is a simple bookstore API with Author and Book models.",
    "CACHE_SCHEMA": False,
}
```

See the [full configuration reference](configuration.md) for all available settings.
