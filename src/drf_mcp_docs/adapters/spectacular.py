from __future__ import annotations

from drf_mcp_docs.adapters.base import BaseSchemaAdapter


class SpectacularAdapter(BaseSchemaAdapter):
    """Adapter for drf-spectacular."""

    @classmethod
    def is_available(cls) -> bool:
        try:
            import drf_spectacular  # noqa: F401
            from django.conf import settings

            schema_class = getattr(settings, "REST_FRAMEWORK", {}).get("DEFAULT_SCHEMA_CLASS", "")
            return "drf_spectacular" in schema_class
        except (ImportError, Exception):
            return False

    def get_schema(self) -> dict:
        from drf_spectacular.generators import SchemaGenerator

        generator = SchemaGenerator()
        schema = generator.get_schema(public=True)
        return schema
