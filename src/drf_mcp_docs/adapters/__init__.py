from __future__ import annotations

import importlib
import logging
from typing import TYPE_CHECKING

from drf_mcp_docs.settings import get_setting

if TYPE_CHECKING:
    from drf_mcp_docs.adapters.base import BaseSchemaAdapter

logger = logging.getLogger(__name__)

_ADAPTER_PRIORITY = [
    "drf_mcp_docs.adapters.spectacular.SpectacularAdapter",
    "drf_mcp_docs.adapters.yasg.YasgAdapter",
    "drf_mcp_docs.adapters.drf.DRFBuiltinAdapter",
]


def get_adapter() -> BaseSchemaAdapter:
    """Get the schema adapter, using settings override or auto-detection."""
    override = get_setting("SCHEMA_ADAPTER")
    if override:
        logger.info("Using adapter override: '%s'", override)
        module_path, class_name = override.rsplit(".", 1)
        try:
            module = importlib.import_module(module_path)
        except ImportError as exc:
            logger.error("Failed to import adapter '%s': %s", override, exc)
            raise ImportError(
                f"Could not import module '{module_path}' for adapter. "
                f"Check your DRF_MCP_DOCS['SCHEMA_ADAPTER'] setting: '{override}'"
            ) from exc
        try:
            adapter_class = getattr(module, class_name)
        except AttributeError as exc:
            logger.error("Adapter class '%s' not found in '%s'", class_name, module_path)
            raise ImportError(
                f"Module '{module_path}' has no class '{class_name}'. "
                f"Check your DRF_MCP_DOCS['SCHEMA_ADAPTER'] setting: '{override}'"
            ) from exc
        return adapter_class()

    for dotted_path in _ADAPTER_PRIORITY:
        module_path, class_name = dotted_path.rsplit(".", 1)
        module = importlib.import_module(module_path)
        adapter_class = getattr(module, class_name)
        available = adapter_class.is_available()
        logger.debug("Probing adapter %s: available=%s", class_name, available)
        if available:
            logger.info("Auto-detected adapter: %s", class_name)
            return adapter_class()

    logger.error("No schema adapter available")
    raise RuntimeError(
        "No schema adapter available. Install drf-spectacular, drf-yasg, "
        "or ensure DRF's built-in schema generation is configured."
    )
