from __future__ import annotations

from abc import ABC, abstractmethod


class BaseSchemaAdapter(ABC):
    """Abstract base for OpenAPI schema adapters."""

    @abstractmethod
    def get_schema(self) -> dict:
        """Return a normalized OpenAPI 3.x dict."""

    @classmethod
    @abstractmethod
    def is_available(cls) -> bool:
        """Check if the required package is installed and usable."""
