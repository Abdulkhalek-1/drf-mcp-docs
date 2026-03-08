# Contributing

Thanks for your interest in contributing to drf-mcp-docs! This guide covers everything you need to get started.

## Development Setup

### 1. Clone and install

```bash
git clone https://github.com/Abdulkhalek-1/drf-mcp-docs.git
cd drf-mcp-docs
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -e ".[dev]"
```

### 2. Run tests

```bash
pytest
```

With verbose output:

```bash
pytest -v
```

### 3. Run a specific test file

```bash
pytest tests/test_processor.py
pytest tests/test_tools.py::TestGenerateCodeSnippet
```

## Project Structure

```
drf-mcp-docs/
├── src/drf_mcp_docs/         # Package source code
│   ├── adapters/        # Schema generator adapters
│   ├── schema/          # Types and processor
│   ├── server/          # MCP server, resources, tools
│   └── management/      # Django management commands
├── tests/               # Test suite
│   ├── testapp/         # Minimal Django app for testing
│   ├── conftest.py      # Fixtures and sample OpenAPI schema
│   └── test_*.py        # Test modules
└── docs/                # Documentation
```

See [Architecture](architecture.md) for detailed internals.

## What to Contribute

### Good first issues

- Add more string format examples to `_string_example()` in `processor.py`
- Add more HTTP client templates (e.g., `ofetch`, `got`)
- Improve TypeScript type generation for complex schemas
- Add response type generation to code snippets

### Medium complexity

- Add Vue composable / React hook code generation templates
- Support `allOf` / `oneOf` / `anyOf` in schema processing
- Add endpoint filtering by `SCHEMA_PATH_PREFIX` and `EXCLUDE_PATHS`
- Add pagination schema support (cursor, page number, limit/offset)

### Larger features

- Add a new schema adapter for another generator
- Add prompt templates for common AI workflows
- Add MCP sampling support for interactive documentation exploration

## Code Style

- Follow existing patterns in the codebase
- Use type hints for function signatures
- Use `from __future__ import annotations` for forward references
- Keep functions focused and concise
- No unnecessary abstractions — prefer simple, direct code

## Writing Tests

Tests are in `tests/` and use pytest with pytest-django.

### Test fixtures

`tests/conftest.py` provides:

- `SAMPLE_OPENAPI_SCHEMA` — a realistic OpenAPI 3.x dict with products/categories endpoints
- `openapi_schema` fixture — returns the sample schema
- `processor` fixture — returns a `SchemaProcessor` initialized with the sample schema

### Mocking the processor

For resource and tool tests, mock `get_processor` to avoid needing Django schema generation:

```python
from unittest.mock import patch
from drf_mcp_docs.schema.processor import SchemaProcessor
from tests.conftest import SAMPLE_OPENAPI_SCHEMA

@pytest.fixture(autouse=True)
def mock_processor():
    processor = SchemaProcessor(SAMPLE_OPENAPI_SCHEMA)
    with patch("drf_mcp_docs.server.tools.get_processor", return_value=processor):
        yield processor
```

### Test categories

| File | Tests |
|---|---|
| `test_adapters.py` | Adapter availability, schema generation, auto-detection |
| `test_processor.py` | Overview, endpoints, schemas, search, examples, $ref resolution |
| `test_resources.py` | MCP resource output format and content |
| `test_tools.py` | MCP tool output, code generation, error handling |

## Pull Request Process

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes
4. Add/update tests
5. Ensure all tests pass: `pytest`
6. Commit with a clear message
7. Push to your fork and open a PR

### PR guidelines

- Keep PRs focused — one feature or fix per PR
- Include tests for new functionality
- Update docs if adding user-facing features
- Follow existing code patterns and naming conventions
- Fill out the PR template

## Reporting Issues

Use the [issue templates](https://github.com/Abdulkhalek-1/drf-mcp-docs/issues/new/choose):

- **Bug Report** — for unexpected behavior or errors
- **Feature Request** — for new functionality
- **Question** — for usage questions

Include reproduction steps, environment details, and error messages when reporting bugs.

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](../LICENSE).
