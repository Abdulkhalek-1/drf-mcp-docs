# Troubleshooting

This guide covers common issues you may encounter when setting up or running drf-mcp-docs, organized by symptom.

## First Steps: Run the Diagnostic Command

Before diving into specific issues, run the built-in configuration checker:

```bash
python manage.py checkmcpconfig
```

This command validates your settings, checks adapter availability, and attempts schema generation. It catches the majority of configuration problems and provides actionable error messages.

Example output:

```text
drf-mcp-docs configuration check
===================================

--- Settings ---
  OK: TRANSPORT = 'streamable-http'
  OK: DEFAULT_CODE_LANGUAGE = 'javascript'
  OK: DEFAULT_HTTP_CLIENT = 'fetch'
  OK: CACHE_TTL = None (no expiry)
  OK: SCHEMA_PATH_PREFIX = '/api/'
  OK: MCP_ENDPOINT = '/mcp/'
  OK: EXCLUDE_PATHS = []

--- Adapters ---
  SpectacularAdapter: available
  YasgAdapter: not available
  DRFBuiltinAdapter: available
  OK: Active adapter: SpectacularAdapter (auto-detected)

--- Schema Generation ---
  OK: Schema generated successfully
  OK: 12 endpoint(s) after path filtering
  OK: 5 schema definition(s) found

===================================
All checks passed. 0 warning(s).
```

!!! tip
    Include `checkmcpconfig` output when filing bug reports — it provides the context needed to diagnose most issues.

---

## Installation & Adapter Detection

### "No schema adapter available"

**Symptom:** `RuntimeError` at startup:

```text
RuntimeError: No schema adapter available. Install drf-spectacular, drf-yasg,
or ensure DRF's built-in schema generation is configured.
```

**Cause:** None of the three supported schema generators could be detected.

**Solution:** Install a schema generator. drf-spectacular is recommended:

```bash
pip install drf-mcp-docs[spectacular]
```

Or with drf-yasg:

```bash
pip install drf-mcp-docs[yasg]
```

If you want to use DRF's built-in generator (limited output), make sure `djangorestframework` is installed and that `inflection` and `uritemplate` are available (they are required by DRF's schema generator).

### drf-spectacular installed but not detected

**Symptom:** `checkmcpconfig` shows `SpectacularAdapter: not available` even though `drf-spectacular` is installed. The server falls back to `DRFBuiltinAdapter`.

**Cause:** drf-spectacular requires `DEFAULT_SCHEMA_CLASS` to be set in your `REST_FRAMEWORK` settings. The adapter checks both that the package is installed *and* that the schema class is configured.

**Solution:** Add to your `settings.py`:

```python
REST_FRAMEWORK = {
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}
```

Also ensure `'drf_spectacular'` is in your `INSTALLED_APPS`.

### "Could not import module '...' for adapter"

**Symptom:** `ImportError` when using a custom `SCHEMA_ADAPTER` setting:

```text
ImportError: Could not import module 'myapp.adapters' for adapter.
Check your DRF_MCP_DOCS['SCHEMA_ADAPTER'] setting: 'myapp.adapters.MyAdapter'
```

**Cause:** The module path in `SCHEMA_ADAPTER` is incorrect, or the module is not on `sys.path`.

**Solution:** Verify the dotted path. The format is `'module.path.ClassName'`:

```python
DRF_MCP_DOCS = {
    'SCHEMA_ADAPTER': 'myapp.adapters.MyCustomAdapter',
}
```

Check that the module is importable: `python -c "from myapp.adapters import MyCustomAdapter"`.

### "Module '...' has no class '...'"

**Symptom:** `ImportError` about a missing class name.

**Cause:** The module exists but the class name portion of `SCHEMA_ADAPTER` is misspelled.

**Solution:** Check the class name spelling. The part after the last `.` is the class name:

```python
# Wrong — class name typo
'SCHEMA_ADAPTER': 'myapp.adapters.MyCustomAdaptor'

# Correct
'SCHEMA_ADAPTER': 'myapp.adapters.MyCustomAdapter'
```

---

## Schema Generation Issues

### Empty schema (0 endpoints)

**Symptom:** AI agent says "no endpoints found", or `checkmcpconfig` shows `0 endpoint(s) after path filtering`.

**Possible causes and solutions:**

**1. No DRF views registered**

Your `ROOT_URLCONF` doesn't include any DRF router URLs. Verify your URL configuration:

```python
# urls.py
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from myapp.views import MyViewSet

router = DefaultRouter()
router.register(r'items', MyViewSet)

urlpatterns = [
    path('api/', include(router.urls)),
]
```

**2. `SCHEMA_PATH_PREFIX` doesn't match your URLs**

The default prefix is `/api/`. If your URLs use a different prefix (e.g., `/v1/` or no prefix), endpoints will be filtered out.

```python
# If your URLs are under /v1/
DRF_MCP_DOCS = {
    'SCHEMA_PATH_PREFIX': '/v1/',
}

# To include all endpoints regardless of prefix
DRF_MCP_DOCS = {
    'SCHEMA_PATH_PREFIX': '',
}
```

**3. `EXCLUDE_PATHS` is too broad**

Check that your exclusion patterns aren't removing all endpoints:

```python
# This would exclude everything under /api/
DRF_MCP_DOCS = {
    'EXCLUDE_PATHS': ['/api/'],  # Too broad!
}
```

!!! tip
    Run `python manage.py checkmcpconfig` — it reports both the raw endpoint count and the count after filtering, making it easy to spot when filtering is the problem.

### "Path filtering reduced N endpoints to 0"

**Symptom:** `checkmcpconfig` warning showing that path filtering removed all endpoints.

**Cause:** Your `SCHEMA_PATH_PREFIX` or `EXCLUDE_PATHS` settings don't match your actual URL structure.

**Solution:** Check what paths your API actually uses. The `checkmcpconfig` output shows the raw count before filtering. Adjust `SCHEMA_PATH_PREFIX` to match, or set it to `''` to disable prefix filtering.

### Empty or generic examples for endpoints

**Symptom:** `get_request_example` returns placeholder values like `"string"` or `0` instead of realistic examples.

**Cause:** The schema generator doesn't provide enough field detail. This is common with DRF's built-in adapter, which has limited serializer introspection. It can also happen with circular `$ref` references (the resolver has a depth limit of 10).

**Solution:** Switch to drf-spectacular for richer schemas. With drf-spectacular, you can also add explicit examples using `@extend_schema`:

```python
from drf_spectacular.utils import extend_schema, OpenApiExample

class MyViewSet(viewsets.ModelViewSet):
    @extend_schema(
        examples=[
            OpenApiExample('Create item', value={'name': 'Widget', 'price': 9.99})
        ]
    )
    def create(self, request, *args, **kwargs):
        ...
```

---

## ASGI Integration Issues

### "RuntimeError: Task group is not initialized"

**Symptom:** Every request to the MCP endpoint returns a 500 error with:

```text
RuntimeError: Task group is not initialized. Make sure to use run().
```

**Cause:** ASGI lifespan events are not being forwarded to the `mount_mcp` wrapper. The MCP server uses the ASGI lifespan protocol to initialize its internal task group — without it, all MCP requests fail.

**Solution:** Make sure your ASGI application forwards `lifespan` scope to `mount_mcp`. If you have a custom ASGI wrapper, it **must** include the lifespan case:

```python
# asgi.py
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")
django_app = get_asgi_application()

from drf_mcp_docs.urls import mount_mcp
django_app = mount_mcp(django_app)

async def application(scope, receive, send):
    if scope["type"] == "http":
        await django_app(scope, receive, send)
    elif scope["type"] == "websocket":
        await websocket_app(scope, receive, send)
    elif scope["type"] == "lifespan":
        # Required: forward lifespan events to mount_mcp
        await django_app(scope, receive, send)
```

!!! warning
    A common mistake is routing only `http` and `websocket` scopes while dropping `lifespan`. If you use `mount_mcp()`, lifespan forwarding is mandatory.

### MCP endpoint returns 404 or Django handles it

**Symptom:** Requests to `/mcp/` are handled by Django instead of the MCP server, returning a 404 or an unexpected response.

**Cause:** A Django URL pattern matches the MCP endpoint path before `mount_mcp` can intercept it, or the `MCP_ENDPOINT` path doesn't match what the client is requesting.

**Solution:**

- `mount_mcp()` checks the path *before* passing to Django, so this usually means the path configuration is wrong. Verify your `MCP_ENDPOINT` setting matches what you're requesting.
- If using a custom mount path, ensure it's consistent:

```python
# settings.py
DRF_MCP_DOCS = {
    'MCP_ENDPOINT': '/docs-mcp/',
}

# asgi.py — path parameter overrides the setting
application = mount_mcp(django_app, path="/docs-mcp/")
```

### WSGI project trying to use `mount_mcp`

**Symptom:** `mount_mcp` doesn't work or produces errors when running under WSGI (e.g., `gunicorn myproject.wsgi`).

**Cause:** `mount_mcp` creates an ASGI application. It cannot be used with WSGI servers.

**Solution:** Use one of these alternatives:

```bash
# Option A: stdio transport (recommended for WSGI projects)
python manage.py runmcpserver --transport stdio

# Option B: standalone HTTP server on a separate port
python manage.py runmcpserver --transport streamable-http --port 8100

# Option C: migrate to ASGI
pip install uvicorn
uvicorn myproject.asgi:application --host 0.0.0.0 --port 8000
```

See [ASGI Integration](asgi-integration.md) for details on each option.

---

## Connection & Transport Issues

### stdio: AI tool fails to start the MCP server

**Symptom:** Your AI tool (Claude Code, Cursor, VS Code) reports "command not found", "No module named django", or similar errors when trying to start the MCP server.

**Cause:** The AI tool is using the wrong Python interpreter or working directory.

**Solution:** Use absolute paths in your MCP configuration:

```json
{
  "mcpServers": {
    "my-api": {
      "command": "/path/to/venv/bin/python",
      "args": ["manage.py", "runmcpserver", "--transport", "stdio"],
      "cwd": "/absolute/path/to/your/django/project"
    }
  }
}
```

!!! warning
    The most common mistake is not pointing to the virtual environment's Python. If you use a venv, always use its full path (e.g., `/home/user/myproject/.venv/bin/python`).

Verify manually first:

```bash
cd /path/to/your/django/project
/path/to/venv/bin/python manage.py runmcpserver --transport stdio
```

### streamable-http: "Address already in use"

**Symptom:** `OSError: [Errno 98] Address already in use` when starting `runmcpserver`.

**Cause:** Another process is already listening on that port.

**Solution:**

```bash
# Use a different port
python manage.py runmcpserver --transport streamable-http --port 8200

# Or find and stop the process using the port
lsof -i :8100
kill <PID>
```

### streamable-http: Connection refused

**Symptom:** MCP client reports "connection refused" or times out.

**Cause:** The server isn't running, the URL is wrong, or a firewall is blocking the connection.

**Solution:**

1. Verify the server is running: `python manage.py runmcpserver --transport streamable-http --port 8100`
2. Check the URL in your MCP client config matches (default: `http://localhost:8100/mcp/`)
3. For remote connections, ensure the firewall allows traffic on the port and the server binds to `0.0.0.0` (not just `localhost`)

### AI tool connects but gets empty data

**Symptom:** The MCP server responds, but resources and tools return no endpoints or schemas.

**Cause:** Schema generation succeeded but produced 0 endpoints. This is a schema generation issue, not a connection issue.

**Solution:** See [Empty schema (0 endpoints)](#empty-schema-0-endpoints) above. Run `python manage.py checkmcpconfig` to diagnose.

---

## Configuration Issues

### Unknown setting warning

**Symptom:** `checkmcpconfig` warns about an unknown setting, possibly with a suggestion:

```text
WARNING: Unknown setting 'SERVR_NAME' in DRF_MCP_DOCS (did you mean 'SERVER_NAME'?)
```

**Cause:** Typo in your `DRF_MCP_DOCS` dictionary key.

**Solution:** Fix the key name. See [Configuration](configuration.md) for the full list of valid settings.

### Invalid setting values

**Symptom:** `checkmcpconfig` reports errors about setting values.

**Common mistakes and fixes:**

| Setting | Invalid | Valid |
|---------|---------|-------|
| `TRANSPORT` | `'http'` | `'stdio'` or `'streamable-http'` |
| `DEFAULT_CODE_LANGUAGE` | `'ts'` | `'javascript'`, `'typescript'`, or `'python'` |
| `DEFAULT_HTTP_CLIENT` | `'curl'` | `'fetch'`, `'axios'`, `'ky'`, `'requests'`, or `'httpx'` |
| `CACHE_TTL` | `-1` or `'300'` | `None` or a positive number (e.g., `300`) |
| `SCHEMA_PATH_PREFIX` | `'api/'` | `'/api/'` (must start with `/`) |
| `MCP_ENDPOINT` | `'mcp/'` | `'/mcp/'` (must start with `/`) |
| `EXCLUDE_PATHS` | `'/admin/'` | `['/admin/']` (must be a list) |

### Language/client mismatch warning

**Symptom:** `checkmcpconfig` warns:

```text
WARNING: DEFAULT_HTTP_CLIENT = 'fetch' will be auto-corrected to 'requests' for language 'python'
```

**Cause:** The default HTTP client doesn't match the default code language (e.g., `fetch` is a JavaScript client but the language is set to Python).

**Solution:** This is a warning, not an error — the code generator will auto-correct. To silence it, set a matching pair:

```python
# Python with requests
DRF_MCP_DOCS = {
    'DEFAULT_CODE_LANGUAGE': 'python',
    'DEFAULT_HTTP_CLIENT': 'requests',
}

# TypeScript with axios
DRF_MCP_DOCS = {
    'DEFAULT_CODE_LANGUAGE': 'typescript',
    'DEFAULT_HTTP_CLIENT': 'axios',
}
```

---

## Cache & Performance

### Stale schema data after model or view changes

**Symptom:** The MCP server still shows old endpoints, fields, or schemas after you've made changes to your models, serializers, or views.

**Cause:** In production (`DEBUG=False`), `CACHE_SCHEMA` defaults to `True` and the schema is cached indefinitely (unless `CACHE_TTL` is set).

**Solutions:**

**Option 1: Set a TTL for automatic refresh**

```python
DRF_MCP_DOCS = {
    'CACHE_TTL': 300,  # Refresh every 5 minutes
}
```

**Option 2: Invalidate programmatically**

```python
from drf_mcp_docs import invalidate_schema_cache

# Call after deploying new code, or in a signal handler
invalidate_schema_cache()
```

**Option 3: Restart the server**

The simplest approach — the cache is in-process memory and is cleared on restart.

### Schema rebuilds on every request in development

**Symptom:** Logs show the schema being rebuilt on every MCP request, making responses slower.

**Cause:** When `DEBUG=True`, `CACHE_SCHEMA` defaults to `False`, so the schema is regenerated on every request. This is the intended behavior for development — you always see your latest changes.

**Solution:** This is expected. If schema generation is slow, you can enable caching in development:

```python
DRF_MCP_DOCS = {
    'CACHE_SCHEMA': True,
}
```

Just remember to restart the server or call `invalidate_schema_cache()` when you make API changes.

---

## Debugging with Logs

Enable detailed logging to see what drf-mcp-docs is doing internally:

```python
# settings.py
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'drf_mcp_docs': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
    },
}
```

This enables debug output from all drf-mcp-docs modules:

- **`drf_mcp_docs.adapters`** — Adapter probing, selection, and schema generation timing
- **`drf_mcp_docs.server.instance`** — Cache hits/misses, schema processor creation, path filtering
- **`drf_mcp_docs.server.tools`** — Tool inputs and endpoint lookups
- **`drf_mcp_docs.schema.processor`** — Schema processing, `$ref` resolution, depth limit warnings
- **`drf_mcp_docs.urls`** — ASGI lifespan events and request routing
- **`drf_mcp_docs.settings`** — Resolved settings values

---

## Getting Help

If the troubleshooting steps above don't resolve your issue:

1. Run `python manage.py checkmcpconfig` and note the output
2. Enable debug logging (see above) and reproduce the issue
3. Open an issue at [github.com/Abdulkhalek-1/drf-mcp-docs/issues](https://github.com/Abdulkhalek-1/drf-mcp-docs/issues) with:
    - The `checkmcpconfig` output
    - Relevant log output
    - Your Python, Django, and DRF versions
    - Which schema generator you're using
