from __future__ import annotations

import difflib
import importlib
import sys

from django.conf import settings as django_settings
from django.core.management.base import BaseCommand

from drf_mcp_docs.adapters import get_adapter
from drf_mcp_docs.schema.processor import SchemaProcessor
from drf_mcp_docs.server.instance import _filter_paths
from drf_mcp_docs.settings import DEFAULTS, get_setting

_VALID_TRANSPORTS = {"stdio", "streamable-http"}
_VALID_LANGUAGES = {"javascript", "typescript", "python"}
_VALID_CLIENTS = {"fetch", "axios", "ky", "requests", "httpx"}
_JS_CLIENTS = {"fetch", "axios", "ky"}
_PY_CLIENTS = {"requests", "httpx"}

_ADAPTER_NAMES = [
    ("drf_mcp_docs.adapters.spectacular", "SpectacularAdapter"),
    ("drf_mcp_docs.adapters.yasg", "YasgAdapter"),
    ("drf_mcp_docs.adapters.drf", "DRFBuiltinAdapter"),
]


class Command(BaseCommand):
    help = "Validate drf-mcp-docs configuration and report diagnostics"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.errors: list[str] = []
        self.warnings: list[str] = []

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _section(self, title: str) -> None:
        self.stdout.write(f"\n--- {title} ---")

    def _ok(self, msg: str) -> None:
        self.stdout.write(self.style.SUCCESS(f"  OK: {msg}"))

    def _warn(self, msg: str) -> None:
        self.warnings.append(msg)
        self.stdout.write(self.style.WARNING(f"  WARNING: {msg}"))

    def _error(self, msg: str) -> None:
        self.errors.append(msg)
        self.stdout.write(self.style.ERROR(f"  ERROR: {msg}"))

    # ------------------------------------------------------------------
    # Settings checks
    # ------------------------------------------------------------------

    def _check_settings(self) -> None:
        self._section("Settings")
        user_settings = getattr(django_settings, "DRF_MCP_DOCS", {})

        # Unknown keys
        known = set(DEFAULTS)
        for key in user_settings:
            if key not in known:
                matches = difflib.get_close_matches(key, known, n=1, cutoff=0.6)
                hint = f" (did you mean '{matches[0]}'?)" if matches else ""
                self._warn(f"Unknown setting '{key}' in DRF_MCP_DOCS{hint}")

        # TRANSPORT
        transport = get_setting("TRANSPORT")
        if transport not in _VALID_TRANSPORTS:
            self._error(f"TRANSPORT = {transport!r} (must be one of {sorted(_VALID_TRANSPORTS)})")
        else:
            self._ok(f"TRANSPORT = {transport!r}")

        # DEFAULT_CODE_LANGUAGE
        lang = get_setting("DEFAULT_CODE_LANGUAGE")
        if lang not in _VALID_LANGUAGES:
            self._error(f"DEFAULT_CODE_LANGUAGE = {lang!r} (must be one of {sorted(_VALID_LANGUAGES)})")
        else:
            self._ok(f"DEFAULT_CODE_LANGUAGE = {lang!r}")

        # DEFAULT_HTTP_CLIENT
        client = get_setting("DEFAULT_HTTP_CLIENT")
        if client not in _VALID_CLIENTS:
            self._error(f"DEFAULT_HTTP_CLIENT = {client!r} (must be one of {sorted(_VALID_CLIENTS)})")
        else:
            self._ok(f"DEFAULT_HTTP_CLIENT = {client!r}")
            # Cross-check language/client compatibility
            if lang in _VALID_LANGUAGES and client in _VALID_CLIENTS:
                if lang == "python" and client in _JS_CLIENTS:
                    self._warn(
                        f"DEFAULT_HTTP_CLIENT = {client!r} will be auto-corrected to 'requests' for language '{lang}'"
                    )
                elif lang in {"javascript", "typescript"} and client in _PY_CLIENTS:
                    self._warn(
                        f"DEFAULT_HTTP_CLIENT = {client!r} will be auto-corrected to 'fetch' for language '{lang}'"
                    )

        # CACHE_TTL
        ttl = get_setting("CACHE_TTL")
        if ttl is None:
            self._ok("CACHE_TTL = None (no expiry)")
        elif isinstance(ttl, int | float) and ttl > 0:
            self._ok(f"CACHE_TTL = {ttl}")
        else:
            self._error(f"CACHE_TTL = {ttl!r} (must be None or a positive number)")

        # SCHEMA_PATH_PREFIX
        prefix = get_setting("SCHEMA_PATH_PREFIX")
        if prefix and not prefix.startswith("/"):
            self._error(f"SCHEMA_PATH_PREFIX = {prefix!r} (must start with '/')")
        else:
            self._ok(f"SCHEMA_PATH_PREFIX = {prefix!r}")

        # MCP_ENDPOINT
        endpoint = get_setting("MCP_ENDPOINT")
        if endpoint and not endpoint.startswith("/"):
            self._error(f"MCP_ENDPOINT = {endpoint!r} (must start with '/')")
        else:
            self._ok(f"MCP_ENDPOINT = {endpoint!r}")

        # EXCLUDE_PATHS
        exclude = get_setting("EXCLUDE_PATHS")
        if not isinstance(exclude, list):
            self._error(f"EXCLUDE_PATHS = {exclude!r} (must be a list)")
        else:
            self._ok(f"EXCLUDE_PATHS = {exclude!r}")

    # ------------------------------------------------------------------
    # Adapter checks
    # ------------------------------------------------------------------

    def _check_adapters(self) -> None:
        self._section("Adapters")

        # Report availability of each built-in adapter
        for module_path, class_name in _ADAPTER_NAMES:
            module = importlib.import_module(module_path)
            adapter_class = getattr(module, class_name)
            status = "available" if adapter_class.is_available() else "not available"
            self.stdout.write(f"  {class_name}: {status}")

        # Check override setting
        override = get_setting("SCHEMA_ADAPTER")
        if override:
            self.stdout.write(f"  SCHEMA_ADAPTER override: {override!r}")

        # Try to get the active adapter
        try:
            adapter = get_adapter()
            label = "override" if override else "auto-detected"
            self._ok(f"Active adapter: {type(adapter).__name__} ({label})")
        except (ImportError, RuntimeError) as exc:
            self._error(str(exc))

    # ------------------------------------------------------------------
    # Schema generation check
    # ------------------------------------------------------------------

    def _check_schema_generation(self) -> None:
        self._section("Schema Generation")

        if any("adapter" in e.lower() or "schema adapter" in e.lower() for e in self.errors):
            self.stdout.write("  Skipped (adapter errors above)")
            return

        try:
            adapter = get_adapter()
            raw_schema = adapter.get_schema()
        except Exception as exc:
            self._error(f"Schema generation failed: {exc}")
            return

        raw_paths = raw_schema.get("paths", {})
        raw_count = sum(
            1
            for methods in raw_paths.values()
            for m in methods
            if m in ("get", "post", "put", "patch", "delete", "head", "options")
        )

        if raw_count == 0:
            self._warn("Adapter returned a schema with 0 endpoints")

        filtered_schema = _filter_paths(raw_schema)
        processor = SchemaProcessor(filtered_schema)
        overview = processor.get_overview()
        schemas = processor.get_schemas()

        self._ok("Schema generated successfully")
        self._ok(f"{overview.endpoint_count} endpoint(s) after path filtering")
        self._ok(f"{len(schemas)} schema definition(s) found")

        if raw_count > 0 and overview.endpoint_count == 0:
            prefix = get_setting("SCHEMA_PATH_PREFIX")
            self._warn(
                f"Path filtering reduced {raw_count} endpoint(s) to 0. "
                f"Check SCHEMA_PATH_PREFIX ({prefix!r}) and EXCLUDE_PATHS."
            )

    # ------------------------------------------------------------------
    # Main handler
    # ------------------------------------------------------------------

    def handle(self, *args, **options):
        self.stdout.write("drf-mcp-docs configuration check")
        self.stdout.write("=" * 35)

        self._check_settings()
        self._check_adapters()
        self._check_schema_generation()

        self.stdout.write("\n" + "=" * 35)
        n_err = len(self.errors)
        n_warn = len(self.warnings)

        if n_err:
            self.stdout.write(self.style.ERROR(f"Check complete. {n_err} error(s), {n_warn} warning(s) found."))
            sys.exit(1)
        else:
            msg = f"All checks passed. {n_warn} warning(s)."
            self.stdout.write(self.style.SUCCESS(msg))
