# Resources & Tools Reference

drf-mcp-docs exposes your API documentation through two MCP primitives:

- **Resources** — Browsable, read-only data the AI agent can access at any time
- **Tools** — Functions the AI agent can call with parameters to get specific information

## Resources

Resources are identified by URI and return JSON data. AI agents typically read these to understand the overall API structure before using tools for specific queries.

### `api://overview`

Returns a high-level overview of the entire API.

**Response fields:**

| Field | Type | Description |
|---|---|---|
| `title` | string | API title from OpenAPI info |
| `description` | string | API description |
| `version` | string | API version |
| `base_url` | string | Base URL from servers |
| `auth_methods` | array | Authentication methods available |
| `tags` | array | API tag groupings |
| `endpoint_count` | integer | Total number of endpoints |

**Example response:**

```json
{
  "title": "E-Commerce API",
  "description": "REST API for the e-commerce platform",
  "version": "2.1.0",
  "base_url": "https://api.example.com/v2",
  "auth_methods": [
    {
      "name": "bearerAuth",
      "type": "bearer",
      "description": "Bearer token (JWT)",
      "header_name": null,
      "scheme": "bearer"
    }
  ],
  "tags": [
    {"name": "products", "description": "Product operations"},
    {"name": "orders", "description": "Order management"}
  ],
  "endpoint_count": 24
}
```

### `api://endpoints`

Returns a compact listing of all API endpoints.

**Response format:** Array of objects, each with:

| Field | Type | Description |
|---|---|---|
| `path` | string | URL path |
| `method` | string | HTTP method (GET, POST, etc.) |
| `summary` | string | Brief description |
| `tags` | array | Tag groupings |
| `auth_required` | boolean | Whether authentication is needed |
| `deprecated` | boolean | Whether the endpoint is deprecated |

**Example response:**

```json
[
  {
    "path": "/api/products/",
    "method": "GET",
    "summary": "List all products",
    "tags": ["products"],
    "auth_required": false,
    "deprecated": false
  },
  {
    "path": "/api/products/",
    "method": "POST",
    "summary": "Create a product",
    "tags": ["products"],
    "auth_required": true,
    "deprecated": false
  }
]
```

### `api://endpoints/{method}/{path}`

Returns full details for a single endpoint.

**URI parameters:**

- `method` — HTTP method (get, post, put, patch, delete)
- `path` — URL path without leading slash (e.g., `api/products/`)

**Response fields:** Full `Endpoint` dataclass including parameters, request body, responses, auth info.

### `api://schemas`

Returns a compact listing of all data model schemas.

**Response format:** Array of objects, each with:

| Field | Type | Description |
|---|---|---|
| `name` | string | Schema name |
| `type` | string | Schema type (usually "object") |
| `fields` | array | List of field names |
| `description` | string | Schema description |

### `api://schemas/{name}`

Returns full details for a single schema.

**URI parameters:**

- `name` — Schema name (e.g., `Product`, `UserCreate`)

**Response fields:**

| Field | Type | Description |
|---|---|---|
| `name` | string | Schema name |
| `type` | string | Schema type |
| `properties` | object | All properties with type info, format, constraints |
| `required` | array | Required field names |
| `description` | string | Schema description |

**Example response:**

```json
{
  "name": "Product",
  "type": "object",
  "properties": {
    "id": {"type": "integer", "readOnly": true},
    "name": {"type": "string"},
    "price": {"type": "number", "format": "decimal"},
    "category": {"type": "integer"},
    "in_stock": {"type": "boolean"}
  },
  "required": ["name", "price", "category"],
  "description": "A product in the catalog"
}
```

### `api://auth`

Returns details about all authentication methods.

**Response format:** Array of `AuthMethod` objects:

| Field | Type | Description |
|---|---|---|
| `name` | string | Auth scheme name |
| `type` | string | Type: bearer, basic, apiKey, oauth2 |
| `description` | string | Human-readable description |
| `header_name` | string\|null | Header name for apiKey type |
| `scheme` | string\|null | HTTP scheme (bearer, basic) |

---

## Tools

Tools are functions that the AI agent calls with specific parameters. They enable searching, filtering, and generating output.

### `search_endpoints`

Search API endpoints by keyword. Matches against path, summary, description, operationId, and tags.

**Parameters:**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `query` | string | yes | Search keyword |
| `method` | string | no | Filter by HTTP method (GET, POST, etc.) |
| `tag` | string | no | Filter by tag |

**Example call:**

```
search_endpoints(query="user", method="POST")
```

**Returns:** Array of matching endpoints with path, method, summary, and tags.

### `get_endpoint_detail`

Get full documentation for a specific endpoint.

**Parameters:**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `path` | string | yes | Endpoint path (e.g., `/api/products/`) |
| `method` | string | yes | HTTP method |

**Returns:** Complete endpoint details including:
- Parameters (path, query, header) with types and descriptions
- Request body schema with content type
- Response schemas for each status code
- Authentication requirements
- Deprecation status

### `get_request_example`

Generate an example request for an endpoint, including URL parameters and request body.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `path` | string | yes | — | Endpoint path |
| `method` | string | yes | — | HTTP method |
| `format` | string | no | `"json"` | Output format |

**Returns:** Object with:
- `method` — HTTP method
- `path` — Endpoint path
- `parameters` — Example values for path/query params
- `body` — Example request body (for POST/PUT/PATCH)
- `content_type` — Request content type

**Example response:**

```json
{
  "method": "POST",
  "path": "/api/products/",
  "body": {
    "name": "Example Name",
    "price": 1.0,
    "category": 1,
    "in_stock": true
  },
  "content_type": "application/json"
}
```

### `get_response_example`

Generate an example response for an endpoint.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `path` | string | yes | — | Endpoint path |
| `method` | string | yes | — | HTTP method |
| `status_code` | string | no | `"200"` | HTTP status code |

**Returns:** Object with status code, description, and example data.

### `generate_code_snippet`

Generate frontend integration code for calling an API endpoint.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `path` | string | yes | — | Endpoint path |
| `method` | string | yes | — | HTTP method |
| `language` | string | no | from settings | `"javascript"` or `"typescript"` |
| `client` | string | no | from settings | `"fetch"`, `"axios"`, or `"ky"` |

**Returns:** Object with `language`, `client`, and `code` fields.

**Example response (fetch + JavaScript):**

```json
{
  "language": "javascript",
  "client": "fetch",
  "code": "async function productsList(params = {}) {\n  const queryString = new URLSearchParams(params).toString();\n  const url = '/api/products/' + (queryString ? `?${queryString}` : '');\n\n  const response = await fetch(url, {\n    method: 'GET',\n    headers: {\n      'Authorization': `Bearer ${token}`,\n    },\n  });\n\n  if (!response.ok) {\n    throw new Error(`HTTP ${response.status}: ${response.statusText}`);\n  }\n\n  return response.json();\n}"
}
```

See [Code Generation](code-generation.md) for details on each client/language combo.

### `list_schemas`

List all data model schemas.

**Parameters:** None.

**Returns:** Array of objects with:
- `name` — Schema name
- `type` — Schema type
- `field_count` — Number of fields
- `required_fields` — List of required field names
- `description` — Schema description

### `get_schema_detail`

Get full details of a data model schema.

**Parameters:**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `name` | string | yes | Schema name |

**Returns:** Full schema definition with all properties, types, and constraints.

---

## Usage Patterns

### Pattern 1: Explore then drill down

1. Agent reads `api://overview` to understand the API
2. Agent reads `api://endpoints` to see all available endpoints
3. Agent calls `get_endpoint_detail` for the specific endpoint of interest
4. Agent calls `generate_code_snippet` to produce integration code

### Pattern 2: Search-first

1. Agent calls `search_endpoints(query="user login")` to find relevant endpoints
2. Agent calls `get_request_example` and `get_response_example` for the match
3. Agent calls `generate_code_snippet` to produce the code

### Pattern 3: Schema-driven

1. Agent calls `list_schemas` to see all data models
2. Agent calls `get_schema_detail("User")` to understand the data model
3. Agent generates TypeScript interfaces from the schema
4. Agent calls `generate_code_snippet` for related endpoints
