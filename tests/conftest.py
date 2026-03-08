import pytest

from drf_mcp_docs.schema.processor import SchemaProcessor

SAMPLE_OPENAPI_SCHEMA = {
    "openapi": "3.0.3",
    "info": {
        "title": "Test API",
        "description": "A test API for drf-mcp-docs",
        "version": "1.0.0",
    },
    "servers": [{"url": "https://api.example.com/v1"}],
    "tags": [
        {"name": "products", "description": "Product operations"},
        {"name": "categories", "description": "Category operations"},
    ],
    "paths": {
        "/api/products/": {
            "get": {
                "operationId": "products_list",
                "summary": "List all products",
                "description": "Returns a paginated list of products.",
                "tags": ["products"],
                "parameters": [
                    {
                        "name": "page",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "integer"},
                        "description": "Page number",
                    },
                    {
                        "name": "category",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "string"},
                        "description": "Filter by category slug",
                    },
                ],
                "responses": {
                    "200": {
                        "description": "Successful response",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "array",
                                    "items": {"$ref": "#/components/schemas/Product"},
                                }
                            }
                        },
                    }
                },
                "security": [{"bearerAuth": []}],
            },
            "post": {
                "operationId": "products_create",
                "summary": "Create a product",
                "description": "Create a new product in the catalog.",
                "tags": ["products"],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ProductCreate"},
                        }
                    },
                },
                "responses": {
                    "201": {
                        "description": "Created",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/Product"},
                            }
                        },
                    },
                    "400": {
                        "description": "Validation error",
                    },
                },
                "security": [{"bearerAuth": []}],
            },
        },
        "/api/products/{id}/": {
            "get": {
                "operationId": "products_read",
                "summary": "Get a product",
                "tags": ["products"],
                "parameters": [
                    {
                        "name": "id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "integer"},
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Successful response",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/Product"},
                            }
                        },
                    },
                    "404": {"description": "Not found"},
                },
                "security": [{"bearerAuth": []}],
            },
            "put": {
                "operationId": "products_update",
                "summary": "Update a product",
                "tags": ["products"],
                "parameters": [
                    {
                        "name": "id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "integer"},
                    }
                ],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ProductCreate"},
                        }
                    },
                },
                "responses": {
                    "200": {
                        "description": "Updated",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/Product"},
                            }
                        },
                    },
                },
                "security": [{"bearerAuth": []}],
            },
            "delete": {
                "operationId": "products_delete",
                "summary": "Delete a product",
                "tags": ["products"],
                "deprecated": True,
                "parameters": [
                    {
                        "name": "id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "integer"},
                    }
                ],
                "responses": {
                    "204": {"description": "Deleted"},
                },
                "security": [{"bearerAuth": []}],
            },
        },
        "/api/categories/": {
            "get": {
                "operationId": "categories_list",
                "summary": "List categories",
                "tags": ["categories"],
                "responses": {
                    "200": {
                        "description": "Successful response",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "array",
                                    "items": {"$ref": "#/components/schemas/Category"},
                                }
                            }
                        },
                    }
                },
            }
        },
    },
    "components": {
        "schemas": {
            "Product": {
                "type": "object",
                "description": "A product in the catalog",
                "properties": {
                    "id": {"type": "integer", "readOnly": True},
                    "name": {"type": "string", "maxLength": 200},
                    "description": {"type": "string"},
                    "price": {"type": "number", "format": "decimal"},
                    "category": {"type": "integer"},
                    "category_name": {"type": "string", "readOnly": True},
                    "in_stock": {"type": "boolean"},
                    "created_at": {"type": "string", "format": "date-time", "readOnly": True},
                },
                "required": ["name", "price", "category"],
            },
            "ProductCreate": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "maxLength": 200},
                    "description": {"type": "string"},
                    "price": {"type": "number", "format": "decimal"},
                    "category": {"type": "integer"},
                    "in_stock": {"type": "boolean", "default": True},
                },
                "required": ["name", "price", "category"],
            },
            "Category": {
                "type": "object",
                "description": "Product category",
                "properties": {
                    "id": {"type": "integer", "readOnly": True},
                    "name": {"type": "string", "maxLength": 100},
                    "slug": {"type": "string"},
                    "description": {"type": "string"},
                },
                "required": ["name", "slug"],
            },
        },
        "securitySchemes": {
            "bearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
            }
        },
    },
}


@pytest.fixture
def openapi_schema():
    return SAMPLE_OPENAPI_SCHEMA


@pytest.fixture
def processor(openapi_schema):
    return SchemaProcessor(openapi_schema)
