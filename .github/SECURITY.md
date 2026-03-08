# Security Policy

## drf-mcp-docs Security Model

drf-mcp-docs is a **read-only documentation tool**. It exposes API schema information (endpoint paths, parameter types, response formats) — not actual data. It does not execute API calls or access your database.

However, your API schema may contain information you consider sensitive (internal endpoint paths, field names, authentication schemes). Consider this when deploying.

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes       |

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly:

1. **Do not** open a public GitHub issue
2. Email the maintainer directly with:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
3. Allow reasonable time for a fix before public disclosure

## Security Best Practices

- In production, restrict MCP endpoint access via firewall, VPN, or reverse proxy rules
- Use `EXCLUDE_PATHS` to hide sensitive internal endpoints from the schema
- Set `CACHE_SCHEMA: True` in production to avoid repeated schema generation
- Review your OpenAPI schema output to ensure no sensitive information is exposed
