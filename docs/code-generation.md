# Code Generation

drf-mcp-docs can generate frontend integration code for API endpoints. The `generate_code_snippet` tool produces ready-to-use functions in JavaScript or TypeScript using popular HTTP clients.

## Supported Combinations

| Language | Client | Description |
|---|---|---|
| JavaScript | fetch | Browser Fetch API (no dependencies) |
| JavaScript | axios | axios HTTP client |
| JavaScript | ky | ky HTTP client (fetch wrapper) |
| TypeScript | fetch | Typed Fetch API |
| TypeScript | axios | Typed axios |
| TypeScript | ky | Typed ky |

## How It Works

The code generator reads the endpoint definition and produces a function that:

1. **Names the function** from the `operationId` (or falls back to method + path segments)
2. **Handles path parameters** using template literals (`/api/products/${id}/`)
3. **Handles query parameters** using `URLSearchParams` (fetch/ky) or axios `params`
4. **Includes the request body** for POST/PUT/PATCH methods
5. **Adds auth headers** when the endpoint requires authentication
6. **Returns typed responses** (TypeScript mode adds parameter types)

## Examples

### fetch (JavaScript)

**Endpoint:** `GET /api/products/` with query params and auth

```javascript
async function productsList(params = {}) {
  const queryString = new URLSearchParams(params).toString();
  const url = '/api/products/' + (queryString ? `?${queryString}` : '');

  const response = await fetch(url, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }

  return response.json();
}
```

### fetch (TypeScript)

**Endpoint:** `PUT /api/products/{id}/` with path param, body, and auth

```typescript
async function productsUpdate(id: number, data: RequestData) {
  const url = `/api/products/${id}/`;

  const response = await fetch(url, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }

  return response.json();
}
```

### axios (JavaScript)

**Endpoint:** `POST /api/products/` with body and auth

```javascript
async function productsCreate(data) {
  const response = await axios.post('/api/products/', data, { headers: { Authorization: `Bearer ${token}` } });
  return response.data;
}
```

### ky (JavaScript)

**Endpoint:** `GET /api/products/` with query params and auth

```javascript
async function productsList(params = {}) {
  const response = await ky.get('/api/products/', {
    searchParams: params,
    headers: { Authorization: `Bearer ${token}` },
  }).json();
  return response;
}
```

## Function Naming

Functions are named based on the `operationId` from the OpenAPI schema:

| operationId | Function name |
|---|---|
| `products_list` | `productsList` |
| `products_create` | `productsCreate` |
| `products_read` | `productsRead` |
| `user-profile-update` | `userProfileUpdate` |

If no `operationId` is available, the function name is derived from the method and path:

| Method + Path | Function name |
|---|---|
| `GET /api/products/` | `getApiProducts` |
| `POST /api/users/` | `postApiUsers` |

## TypeScript Type Annotations

In TypeScript mode, the generator adds type annotations for path parameters:

| JSON Schema type | TypeScript type |
|---|---|
| `integer` | `number` |
| `number` | `number` |
| `string` | `string` |
| `boolean` | `boolean` |
| `array` | `any[]` |
| `object` | `Record<string, any>` |

Request bodies use `RequestData` and query params use `QueryParams` as placeholder types. The AI agent is expected to fill these in with actual interfaces based on the schema.

## Configuring Defaults

Set defaults in your Django settings:

```python
DRF_MCP_DOCS = {
    'DEFAULT_CODE_LANGUAGE': 'typescript',  # or 'javascript'
    'DEFAULT_HTTP_CLIENT': 'axios',         # or 'fetch', 'ky'
}
```

These defaults are used when the AI agent doesn't specify a language or client in the tool call. The agent can always override them per-call.

## Behavior Details

### DELETE endpoints

DELETE snippet returns `response` directly (not `.json()`) since DELETE responses typically have no body.

### Authentication

When an endpoint has `security` requirements in the schema, the generated code includes an `Authorization: Bearer ${token}` header. The `token` variable is left for the developer to provide.

### Error handling

All fetch snippets include basic error handling that throws on non-2xx responses. Axios and ky have their own built-in error handling.
