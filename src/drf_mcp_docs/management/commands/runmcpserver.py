from django.core.management.base import BaseCommand
from django.utils import autoreload

from drf_mcp_docs.server import get_mcp_server
from drf_mcp_docs.settings import get_setting


class Command(BaseCommand):
    help = "Start the drf-mcp-docs MCP server"

    def add_arguments(self, parser):
        parser.add_argument(
            "--transport",
            choices=["stdio", "streamable-http"],
            default=None,
            help="Transport type (default: from settings or 'stdio')",
        )
        parser.add_argument(
            "--host",
            default="localhost",
            help="Host for HTTP transport (default: localhost)",
        )
        parser.add_argument(
            "--port",
            type=int,
            default=8100,
            help="Port for HTTP transport (default: 8100)",
        )
        parser.add_argument(
            "--reload",
            action="store_true",
            default=False,
            help="Auto-restart the server on code changes (streamable-http only).",
        )

    def handle(self, *args, **options):
        transport = options["transport"] or get_setting("TRANSPORT")
        use_reload = options["reload"]

        if use_reload and transport == "stdio":
            self.stderr.write(
                self.style.WARNING("Warning: --reload is not compatible with stdio transport. Ignoring --reload.")
            )
            use_reload = False

        options["_resolved_transport"] = transport

        if use_reload:
            autoreload.run_with_reloader(self.inner_run, **options)
        else:
            self.inner_run(**options)

    def inner_run(self, *args, **options):
        transport = options["_resolved_transport"]
        server = get_mcp_server()

        self.stdout.write(self.style.SUCCESS(f"Starting MCP server ({transport})..."))

        if transport == "stdio":
            server.run(transport="stdio")
        else:
            server.settings.host = options["host"]
            server.settings.port = options["port"]
            server.run(transport="streamable-http")
