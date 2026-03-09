from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

from drf_mcp_docs.settings import get_setting

if TYPE_CHECKING:
    from drf_mcp_docs.adapters.base import BaseSchemaAdapter

_ADAPTER_PRIORITY = [
    "drf_mcp_docs.adapters.spectacular.SpectacularAdapter",
    "drf_mcp_docs.adapters.yasg.YasgAdapter",
    "drf_mcp_docs.adapters.drf.DRFBuiltinAdapter",
]


def get_adapter() -> BaseSchemaAdapter:
    """Get the schema adapter, using settings override or auto-detection."""
    override = get_setting("SCHEMA_ADAPTER")
    if override:
        module_path, class_name = override.rsplit(".", 1)
        try:
            module = importlib.import_module(module_path)
        except ImportError as exc:
            raise ImportError(
                f"Could not import module '{module_path}' for adapter. "
                f"Check your DRF_MCP_DOCS['SCHEMA_ADAPTER'] setting: '{override}'"
            ) from exc
        try:
            adapter_class = getattr(module, class_name)
        except AttributeError as exc:
            raise ImportError(
                f"Module '{module_path}' has no class '{class_name}'. "
                f"Check your DRF_MCP_DOCS['SCHEMA_ADAPTER'] setting: '{override}'"
            ) from exc
        return adapter_class()

    for dotted_path in _ADAPTER_PRIORITY:
        module_path, class_name = dotted_path.rsplit(".", 1)
        module = importlib.import_module(module_path)
        adapter_class = getattr(module, class_name)
        if adapter_class.is_available():
            return adapter_class()

    raise RuntimeError(
        "No schema adapter available. Install drf-spectacular, drf-yasg, "
        "or ensure DRF's built-in schema generation is configured."
    )
