# Schema Adapters

drf-mcp-docs uses adapters to pull OpenAPI schemas from different DRF schema generators. This page covers how adapters work, the built-in adapters, and how to write your own.

## How Adapters Work

```
┌──────────────┐     ┌──────────────────┐     ┌────────────────────┐
│ Schema       │────>│ BaseSchemaAdapter │────>│ OpenAPI 3.x dict   │
│ Generator    │     │   .get_schema()  │     │ (normalized)       │
│ (spectacular,│     │   .is_available()│     │                    │
│  yasg, DRF)  │     └──────────────────┘     └────────────────────┘
└──────────────┘                                       │
                                                       ▼
                                              ┌────────────────────┐
                                              │ SchemaProcessor    │
                                              │ (parses, indexes,  │
                                              │  generates)        │
                                              └────────────────────┘
```

Every adapter must:

1. Check if its required package is installed (`is_available()`)
2. Return a normalized OpenAPI 3.x dictionary (`get_schema()`)

The `SchemaProcessor` then transforms this dict into structured dataclasses.

## Auto-Detection

When `SCHEMA_ADAPTER` is `None` (default), drf-mcp-docs tries adapters in order:

1. **SpectacularAdapter** — if `drf-spectacular` is importable
2. **YasgAdapter** — if `drf-yasg` is importable
3. **DRFBuiltinAdapter** — always available (uses DRF's built-in generator)

The first adapter where `is_available()` returns `True` is used.

## Built-in Adapters

### SpectacularAdapter

**Package:** `drf-spectacular`
**Install:** `pip install drf-mcp-docs[spectacular]`

The recommended adapter. drf-spectacular produces the most complete OpenAPI 3.0 schemas with:

- Full serializer introspection (nested, related, choice fields)
- Pagination and filter schema generation
- Custom extensions and decorators
- Accurate response schemas

**Requirements:**

```python
# settings.py
INSTALLED_APPS = [..., 'drf_spectacular']

REST_FRAMEWORK = {
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}
```

**How it works:** Calls `SchemaGenerator().get_schema(public=True)` which returns a Python dict directly.

### YasgAdapter

**Package:** `drf-yasg`
**Install:** `pip install drf-mcp-docs[yasg]`

Generates a Swagger 2.0 schema and automatically converts it to OpenAPI 3.0 format.

**Conversion details:**

| Swagger 2.0 | OpenAPI 3.0 |
|---|---|
| `definitions` | `components/schemas` |
| `securityDefinitions` | `components/securitySchemes` |
| `host` + `basePath` + `schemes` | `servers[0].url` |
| Body `parameters` (`in: body`) | `requestBody` |
| `$ref: #/definitions/X` | `$ref: #/components/schemas/X` |

The conversion handles:

- Schema objects with `$ref`, `allOf`, `properties`, `items`
- Security schemes (basic, apiKey, OAuth2)
- Parameters (query, path, header, body, formData)
- Response schemas

**Limitations:**

- Some Swagger 2.0 features don't have exact OpenAPI 3.0 equivalents
- The conversion is best-effort; complex schemas may lose some detail
- drf-yasg is in maintenance mode and no longer actively developed

### DRFBuiltinAdapter

**Package:** None (built into DRF)

Uses DRF's built-in `rest_framework.schemas.openapi.SchemaGenerator`. This is a fallback — the output is less detailed than drf-spectacular or drf-yasg.

**Limitations:**

- Limited serializer introspection
- No pagination or filtering schema
- Minimal response schema detail
- Some field types may not be represented accurately

**When to use:** Only when you can't install drf-spectacular or drf-yasg.

## Writing a Custom Adapter

Create a class that extends `BaseSchemaAdapter`:

```python
# myapp/adapters.py
from drf_mcp_docs.adapters.base import BaseSchemaAdapter


class MyCustomAdapter(BaseSchemaAdapter):
    @classmethod
    def is_available(cls) -> bool:
        """Check if the required dependencies are installed."""
        try:
            import my_schema_package
            return True
        except ImportError:
            return False

    def get_schema(self) -> dict:
        """Return a normalized OpenAPI 3.x dictionary.

        The returned dict MUST conform to OpenAPI 3.0+ structure:
        {
            "openapi": "3.0.x",
            "info": {...},
            "paths": {...},
            "components": {
                "schemas": {...},
                "securitySchemes": {...},
            },
            "servers": [{...}],
        }
        """
        from my_schema_package import generate_schema
        return generate_schema()
```

Register it in settings:

```python
DRF_MCP_DOCS = {
    'SCHEMA_ADAPTER': 'myapp.adapters.MyCustomAdapter',
}
```

### Requirements for `get_schema()`

The returned dict must include:

| Key | Required | Description |
|---|---|---|
| `openapi` | yes | Version string (e.g., `"3.0.3"`) |
| `info` | yes | Object with `title`, `version`, optionally `description` |
| `paths` | yes | Object mapping URL paths to method objects |
| `components.schemas` | no | Schema definitions referenced by `$ref` |
| `components.securitySchemes` | no | Authentication scheme definitions |
| `servers` | no | Array of server objects with `url` field |
| `tags` | no | Array of tag objects with `name` and `description` |

Each path method object should include:

- `operationId` — unique identifier
- `summary` — brief description
- `description` — detailed description
- `tags` — array of tag names
- `parameters` — array of parameter objects
- `requestBody` — request body for POST/PUT/PATCH
- `responses` — object mapping status codes to response objects
- `security` — array of security requirement objects
- `deprecated` — boolean flag

The more complete the schema, the better drf-mcp-docs can serve AI agents.
