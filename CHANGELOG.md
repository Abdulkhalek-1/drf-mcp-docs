# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
