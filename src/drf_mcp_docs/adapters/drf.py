from __future__ import annotations

import logging

from drf_mcp_docs.adapters.base import BaseSchemaAdapter

logger = logging.getLogger(__name__)


class DRFBuiltinAdapter(BaseSchemaAdapter):
    """Adapter for DRF's built-in schema generation (limited)."""

    @classmethod
    def is_available(cls) -> bool:
        try:
            import inflection  # noqa: F401
            import uritemplate  # noqa: F401
            from rest_framework.schemas.openapi import SchemaGenerator  # noqa: F401

            return True
        except ImportError:
            logger.debug("DRF built-in schema not available (missing dependencies)")
            return False

    def get_schema(self) -> dict:
        from rest_framework.schemas.openapi import SchemaGenerator

        logger.debug("Generating schema via DRF built-in SchemaGenerator")
        generator = SchemaGenerator()
        schema = generator.get_schema()
        if schema is None:
            logger.warning("DRF SchemaGenerator returned None, using empty schema")
            return {
                "openapi": "3.0.3",
                "info": {"title": "API", "version": "0.1.0"},
                "paths": {},
            }
        logger.debug("Schema generated: %d paths", len(schema.get("paths", {})))
        return schema
