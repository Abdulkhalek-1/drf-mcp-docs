# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.2] - 2026-03-09

### Added

- **Schema cache TTL (`CACHE_TTL` setting)** — Optional time-to-live (in seconds) for the schema cache; when set, the cached schema processor is automatically rebuilt after the TTL expires (default: `None` — no expiration, preserving existing behavior)
- **`invalidate_schema_cache()` function** — Public, thread-safe API to force-clear the cached schema processor on demand (e.g., from a Django signal handler or management command); importable from `drf_mcp_docs` or `drf_mcp_docs.server`
- **Pagination-aware code generation** — Detects DRF pagination patterns (page number, limit/offset, cursor) from OpenAPI response schemas and generates helper iterators that fetch all pages automatically for every supported client (fetch, axios, ky, requests, httpx)
- **cURL code generation** — New `curl` output language for `generate_code_snippet` with proper method, auth headers, query params, and JSON body formatting; also accepts `shell`, `sh`, or `bash` as aliases
- **`PaginationInfo` dataclass** — New frozen dataclass capturing pagination style, results field name, and count availability
- **`checkmcpconfig` management command** — Validates settings (unknown keys with typo hints, transport, language, client compatibility, `CACHE_TTL`, path prefixes), tests adapter detection, and verifies schema generation before running the server
- **`--reload` flag on `runmcpserver`** — Uses Django's built-in autoreload mechanism to restart the MCP server when source files change during development; only supported with streamable-http transport
- **Structured debug logging** — Added `logging.getLogger(__name__)` to 11 modules covering adapter selection, schema processing, cache lifecycle, tool invocations, resource access, ASGI routing, and settings resolution; enable via Django's standard `LOGGING` config under the `drf_mcp_docs` namespace
- **Daphne ASGI server compatibility** — Refactored `mount_mcp()` to directly manage the MCP session manager lifecycle instead of relying on Starlette's lifespan middleware, fixing the "Task group is not initialized" error on servers that do not send lifespan events
- **Detailed default server instructions** — Replaced generic default instructions with structured workflow guidance describing all available resources and tools, helping AI agents effectively navigate the API documentation
- **MCP client integration tests** — End-to-end tests that boot a real uvicorn server and connect an actual MCP client via streamable-http transport, catching protocol and transport-level issues that unit tests cannot detect
- **Cache invalidation tests** — TTL expiration, manual invalidation, backward compatibility, top-level import, and concurrent invalidation stress test
- **Config validation tests** — Comprehensive tests for `checkmcpconfig` covering unknown keys, typo detection, transport/language/client compatibility, and adapter verification
- **Logging tests** — Tests verifying debug log output across all 11 instrumented modules

### Fixed

- **`list_schemas` token overflow** — Slimmed `list_schemas` output to return only schema name and description, preventing MCP token limit issues on large APIs; full schema details remain available via `get_schema_detail`

### Documentation

- **Troubleshooting guide** — Comprehensive guide covering adapter detection, schema generation, ASGI integration, connection/transport, configuration, caching, and debug logging, all in symptom-cause-solution format
- **Example bookstore project** — Minimal Author/Book project with drf-spectacular and drf-mcp-docs pre-configured, including ASGI mount, both transport modes, and AI tool configuration snippets
- **Lifespan forwarding guide** — Instructions for custom ASGI wrappers that need to forward lifespan events to `mount_mcp()`

## [0.1.1] - 2026-03-09

### Fixed

- **`SCHEMA_PATH_PREFIX` and `EXCLUDE_PATHS`** — These settings were defined and documented but never implemented; paths are now filtered in `get_processor()` before schema processing
- **Streamable-HTTP test** — Fixed incorrect test assertion that checked `run()` kwargs instead of `server.settings` attributes
- **Claude Code config path** — Updated documentation to use `~/.claude.json` instead of the incorrect `~/.claude/claude_code_config.json`
- **Thread safety** — Added double-checked locking with `threading.Lock()` to `get_mcp_server()` and `get_processor()` singletons, preventing race conditions under multi-worker deployments
- **Recursion depth limits** — `resolve_ref()`, `generate_example_from_schema()`, and `generate_example_value()` now enforce a max depth of 10 to prevent stack overflow from circular `$ref` chains
- **Input validation** — All MCP tool functions now validate `path` (must start with `/`) and `method` (must be a valid HTTP method) before processing
- **Code generation safety** — Added `_sanitize_identifier()` and `_sanitize_string_literal()` to prevent code injection in generated JS/TS snippets from malicious schema values
- **`servers[0]["url"]` KeyError** — Safely handle server entries missing the `url` key
- **Empty enum guard** — `generate_example_value()` returns `None` instead of crashing on empty enum lists
- **Adapter error messages** — Override adapter loading now provides descriptive `ImportError` messages when module or class is not found
- **Streamable-HTTP transport** — Fixed `TypeError` in `runmcpserver` command when using `--transport streamable-http`; `host` and `port` are now set via `server.settings` instead of being passed as `run()` kwargs

### Changed

- **Frozen dataclasses** — All 8 schema dataclasses (`Endpoint`, `Parameter`, `Response`, etc.) are now immutable with `frozen=True`
- **Public API** — Renamed `_generate_example_value()` to `generate_example_value()` (public method)
- **Removed `format` parameter** — `get_request_example()` no longer accepts the unused `format` parameter
- **Removed `default_app_config`** — Removed deprecated Django attribute (deprecated since Django 3.2; minimum supported version is 4.2)

### Added

- **Python code generation** — New `requests` (sync) and `httpx` (async) HTTP client generators with TypedDict definitions, type hints, and Google-style docstrings
- **Real TypeScript interfaces** — Code snippets now generate actual TypeScript interfaces from OpenAPI schemas instead of placeholder types (`RequestData`, `QueryParams`)
- **JSDoc and docstrings** — Generated code includes JSDoc (JS/TS) or Google-style docstrings (Python) with `@param`, `@returns`, `@deprecated`, `@throws` annotations
- **Usage examples** — Generated snippets include commented usage examples with realistic data from the schema
- **Base URL from spec** — Generated code pulls the base URL from the OpenAPI `servers[0].url` field
- **Auth method handling** — Code generation now supports bearer, basic, and apiKey authentication based on actual security schemes (not just hardcoded Bearer)
- **Enriched JSON output** — `generate_code_snippet` returns a `metadata` object with function name, endpoint info, auth details, parameter breakdown, and response summary
- **Auto-client selection** — Automatically selects the appropriate HTTP client for the language (e.g., `python` + `fetch` → `requests`)
- **`$ref` caching** — `SchemaProcessor` now caches resolved `$ref` pointers for improved performance on large schemas
- **yasg logging** — Unknown parameter locations in Swagger 2.0 → OpenAPI 3.0 conversion now emit warnings via `logging`
- **Management command tests** — New `tests/test_management.py` covering `runmcpserver` command
- **Concurrency tests** — New `tests/test_concurrency.py` verifying thread-safe singleton behavior
- **Edge-case tests** — Tests for circular refs, empty enums, missing server URLs, schemas with no paths/components, malformed operations, and frozen dataclass immutability
- **Path filtering tests** — New `tests/test_filtering.py` covering `SCHEMA_PATH_PREFIX` and `EXCLUDE_PATHS`
- **Settings tests** — New `tests/test_settings.py` covering `get_setting()` and `get_all_settings()`
- **ASGI mount tests** — New `tests/test_urls.py` covering `mount_mcp()` routing

## [0.1.0] - 2026-03-08

### Added

- Initial release
- Schema adapter layer with support for drf-spectacular, drf-yasg, and DRF built-in
- Auto-detection of installed schema generators
- Schema processor with OpenAPI 3.x parsing, `$ref` resolution, and example generation
- 6 MCP resources: `api://overview`, `api://endpoints`, `api://endpoints/{method}/{path}`, `api://schemas`, `api://schemas/{name}`, `api://auth`
- 7 MCP tools: `search_endpoints`, `get_endpoint_detail`, `get_request_example`, `get_response_example`, `generate_code_snippet`, `list_schemas`, `get_schema_detail`
- Code generation for fetch, axios, and ky in JavaScript and TypeScript
- Django management command `runmcpserver` with stdio and streamable-http transport
- ASGI mount helper for embedding MCP alongside Django
- Configurable settings via `DRF_MCP_DOCS` dict
- Full test suite (62 tests)
