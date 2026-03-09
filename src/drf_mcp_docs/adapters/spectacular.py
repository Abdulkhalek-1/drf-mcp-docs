from __future__ import annotations

import logging

from drf_mcp_docs.adapters.base import BaseSchemaAdapter

logger = logging.getLogger(__name__)


class SpectacularAdapter(BaseSchemaAdapter):
    """Adapter for drf-spectacular."""

    @classmethod
    def is_available(cls) -> bool:
        try:
            import drf_spectacular  # noqa: F401
            from django.conf import settings

            schema_class = getattr(settings, "REST_FRAMEWORK", {}).get("DEFAULT_SCHEMA_CLASS", "")
            if "drf_spectacular" not in schema_class:
                logger.debug(
                    "drf-spectacular installed but DEFAULT_SCHEMA_CLASS is '%s'",
                    schema_class,
                )
                return False
            return True
        except ImportError:
            logger.debug("drf-spectacular not installed")
            return False

    def get_schema(self) -> dict:
        from drf_spectacular.generators import SchemaGenerator

        logger.debug("Generating schema via drf-spectacular")
        generator = SchemaGenerator()
        schema = generator.get_schema(public=True)
        logger.debug("Schema generated: %d paths", len(schema.get("paths", {})))
        return schema
