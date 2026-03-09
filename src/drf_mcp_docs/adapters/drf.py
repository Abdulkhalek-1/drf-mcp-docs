from __future__ import annotations

from drf_mcp_docs.adapters.base import BaseSchemaAdapter


class DRFBuiltinAdapter(BaseSchemaAdapter):
    """Adapter for DRF's built-in schema generation (limited)."""

    @classmethod
    def is_available(cls) -> bool:
        try:
            import inflection  # noqa: F401
            from rest_framework.schemas.openapi import SchemaGenerator  # noqa: F401

            return True
        except ImportError:
            return False

    def get_schema(self) -> dict:
        from rest_framework.schemas.openapi import SchemaGenerator

        generator = SchemaGenerator()
        schema = generator.get_schema()
        if schema is None:
            return {
                "openapi": "3.0.3",
                "info": {"title": "API", "version": "0.1.0"},
                "paths": {},
            }
        return schema
