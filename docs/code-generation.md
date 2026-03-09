# Code Generation

drf-mcp-docs generates ready-to-use integration code for API endpoints. The `generate_code_snippet` tool produces self-documenting functions with real types, proper auth handling, and usage examples.

## Supported Combinations

| Language | Client | Description |
|---|---|---|
| JavaScript | fetch | Browser Fetch API (no dependencies) |
| JavaScript | axios | axios HTTP client |
| JavaScript | ky | ky HTTP client (fetch wrapper) |
| TypeScript | fetch | Typed Fetch API with interfaces |
| TypeScript | axios | Typed axios with interfaces |
| TypeScript | ky | Typed ky with interfaces |
| Python | requests | requests library (sync) |
| Python | httpx | httpx library (async) |

### Auto-client selection

When the language and client don't match, the tool automatically selects an appropriate client:

- `python` + `fetch`/`axios`/`ky` → uses `requests`
- `javascript`/`typescript` + `requests`/`httpx` → uses `fetch`

## What the Generator Produces

Each generated snippet includes:

1. **Import statements** — `import axios from 'axios'`, `import requests`, etc. (fetch is native, no import needed)
2. **Type definitions** — TypeScript interfaces or Python TypedDicts generated from the OpenAPI schema
3. **Documentation** — JSDoc (JS/TS) or Google-style docstrings (Python) with `@param`, `@returns`, `@deprecated`, `@throws`
4. **Base URL** — Pulled from the OpenAPI spec's `servers[0].url`
5. **Auth handling** — Correct headers based on the endpoint's security scheme (bearer, basic, apiKey)
6. **Function with proper types** — Real parameter types, return type annotations
7. **Error handling** — `throw` on non-2xx (fetch), `raise_for_status()` (Python), built-in (axios/ky)
8. **Usage example** — Commented example call with realistic data from the schema

## Examples

### fetch (JavaScript)

**Endpoint:** `GET /api/products/` with query params and bearer auth

```javascript
/**
 * List all products
 * Returns a paginated list of products.
 * @param params - Query parameters
 * @param token - Authentication credential
 * @returns Successful response
 */
async function productsList(params = {}, token) {
  const BASE_URL = 'https://api.example.com/v1';
  const queryString = new URLSearchParams(params).toString();
  const url = BASE_URL + '/api/products/' + (queryString ? `?${queryString}` : '');

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

// Usage:
// const result = await productsList({"page": 1, "category": "string"}, "your-token-here");
```

### fetch (TypeScript)

**Endpoint:** `POST /api/products/` with request body, response type, and auth

```typescript
interface ProductsCreateRequest {
  name: string;
  description?: string;
  price: number;
  category: number;
  in_stock?: boolean;
}

interface ProductsCreateResponse {
  readonly id?: number;
  name: string;
  description?: string;
  price: number;
  category: number;
  readonly category_name?: string;
  in_stock?: boolean;
  readonly created_at?: string;
}

/**
 * Create a product
 * Create a new product in the catalog.
 * @param data - Request body
 * @param token - Authentication credential
 * @returns Created
 * @throws {400} Validation error
 */
async function productsCreate(data: ProductsCreateRequest, token: string): Promise<ProductsCreateResponse> {
  const BASE_URL = 'https://api.example.com/v1';
  const url = BASE_URL + '/api/products/';

  const response = await fetch(url, {
    method: 'POST',
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

// Usage:
// const result = await productsCreate({name: "Example", price: 1.0, category: 1}, "your-token-here");
```

### requests (Python)

**Endpoint:** `GET /api/products/` with query params and bearer auth

```python
import requests
from typing import Any, NotRequired
from typing import TypedDict


class Product(TypedDict):
    id: NotRequired[int]
    name: str
    description: NotRequired[str]
    price: float
    category: int
    category_name: NotRequired[str]
    in_stock: NotRequired[bool]
    created_at: NotRequired[str]


def products_list(page: int | None = None, category: str | None = None, token: str) -> list[Product]:
    """List all products
    Returns a paginated list of products.

    Args:
        page (int): Page number
        category (str): Filter by category slug
        token (str): Authentication credential.

    Returns:
        Successful response
    """
    base_url = "https://api.example.com/v1"
    url = base_url + "/api/products/"
    headers = {"Authorization": f"Bearer {token}"}
    params = {
        "page": page,
        "category": category,
    }
    params = {k: v for k, v in params.items() if v is not None}

    response = requests.get(url, params=params, headers=headers)
    response.raise_for_status()
    return response.json()

# Usage:
# result = products_list(page=1, category="string", token="your-token-here")
```

### httpx (Python, async)

**Endpoint:** `POST /api/products/` with request body and auth

```python
import httpx
from typing import Any, NotRequired
from typing import TypedDict


class ProductsCreateRequest(TypedDict):
    name: str
    description: NotRequired[str]
    price: float
    category: int
    in_stock: NotRequired[bool]


class ProductsCreateResponse(TypedDict):
    id: NotRequired[int]
    name: str
    description: NotRequired[str]
    price: float
    category: int
    category_name: NotRequired[str]
    in_stock: NotRequired[bool]
    created_at: NotRequired[str]


async def products_create(data: ProductsCreateRequest, token: str) -> ProductsCreateResponse:
    """Create a product
    Create a new product in the catalog.

    Args:
        data: Request body.
        token (str): Authentication credential.

    Returns:
        Created

    Raises:
        HTTPError: 400 - Validation error
    """
    async with httpx.AsyncClient() as client:
        base_url = "https://api.example.com/v1"
        url = base_url + "/api/products/"
        headers = {"Authorization": f"Bearer {token}"}

        response = await client.post(url, json=data, headers=headers)
        response.raise_for_status()
        return response.json()

# Usage:
# result = await products_create(data={...}, token="your-token-here")
```

## Function Naming

Functions are named based on the `operationId` from the OpenAPI schema:

| operationId | JS/TS name | Python name |
|---|---|---|
| `products_list` | `productsList` | `products_list` |
| `products_create` | `productsCreate` | `products_create` |
| `user-profile-update` | `userProfileUpdate` | `user_profile_update` |

If no `operationId` is available, the function name is derived from the method and path:

| Method + Path | JS/TS name | Python name |
|---|---|---|
| `GET /api/products/` | `getApiProducts` | `get_api_products` |
| `POST /api/users/` | `postApiUsers` | `post_api_users` |

## TypeScript Type Generation

In TypeScript mode, the generator creates real interfaces from the OpenAPI schema instead of using placeholder types.

### Type mapping

| JSON Schema type | TypeScript type |
|---|---|
| `integer` | `number` |
| `number` | `number` |
| `string` | `string` |
| `boolean` | `boolean` |
| `array` (with items) | `ItemType[]` |
| `object` | `Record<string, any>` |
| `enum` | `'val1' \| 'val2'` |
| `nullable` | `Type \| null` |

### Generated interfaces

For request bodies, responses, and query parameters, the generator creates named interfaces:

- **Request body** — Uses the `$ref` schema name (e.g., `ProductCreate`) or derives from the operation (e.g., `ProductsCreateRequest`)
- **Response** — Named from the response schema (e.g., `Product`, `ProductsCreateResponse`)
- **Query params** — Named from the operation (e.g., `ProductsListParams`)

Properties include `readonly` for read-only fields, `?` for optional fields, and JSDoc descriptions.

## Python Type Generation

In Python mode, the generator creates TypedDict classes from the OpenAPI schema:

- Required fields use bare type annotations (`name: str`)
- Optional fields use `NotRequired[]` (`description: NotRequired[str]`)
- Type mapping: `integer` → `int`, `number` → `float`, `string` → `str`, `boolean` → `bool`, `array` → `list[T]`

## Authentication Handling

The generator reads the endpoint's actual security schemes and produces the correct auth code:

| Auth type | JS/TS header | Python header |
|---|---|---|
| Bearer | `` 'Authorization': `Bearer ${token}` `` | `"Authorization": f"Bearer {token}"` |
| Basic | `` 'Authorization': `Basic ${credentials}` `` | `"Authorization": f"Basic {credentials}"` |
| API Key | `'X-API-Key': api_key` (uses actual header name) | `"X-API-Key": api_key` |

Auth parameters are automatically added to the function signature. Endpoints without security requirements generate no auth code.

## Enriched Output

The tool returns a JSON object with the generated code and structured metadata:

```json
{
  "language": "javascript",
  "client": "fetch",
  "code": "async function productsList(...) { ... }",
  "metadata": {
    "function_name": "productsList",
    "endpoint": {
      "path": "/api/products/",
      "method": "GET",
      "summary": "List all products",
      "deprecated": false
    },
    "auth": {
      "required": true,
      "methods": [{"type": "bearer", "description": "Bearer token (JWT)"}]
    },
    "parameters": {
      "path": [],
      "query": [
        {"name": "page", "type": "integer", "required": false, "description": "Page number"},
        {"name": "category", "type": "string", "required": false, "description": "Filter by category slug"}
      ],
      "body_required": false
    },
    "response": {
      "success_status": "200",
      "description": "Successful response"
    }
  }
}
```

The `metadata` object gives AI agents structured information about the endpoint without needing to parse the generated code.

## Configuring Defaults

Set defaults in your Django settings:

```python
DRF_MCP_DOCS = {
    'DEFAULT_CODE_LANGUAGE': 'typescript',  # 'javascript', 'typescript', or 'python'
    'DEFAULT_HTTP_CLIENT': 'axios',         # 'fetch', 'axios', 'ky', 'requests', or 'httpx'
}
```

These defaults are used when the AI agent doesn't specify a language or client in the tool call. The agent can always override them per-call.

## Behavior Details

### DELETE endpoints

DELETE snippets return the response directly (not `.json()`) since DELETE responses typically have no body.

### Base URL

The base URL is pulled from the OpenAPI spec's `servers[0].url` field and included as a constant in the generated code. If no server URL is defined, it defaults to an empty string.

### Error handling

- **fetch** — Throws on non-2xx responses with status code and text
- **axios/ky** — Built-in error handling (throws automatically on non-2xx)
- **requests/httpx** — Calls `response.raise_for_status()` which raises `HTTPError` on non-2xx
