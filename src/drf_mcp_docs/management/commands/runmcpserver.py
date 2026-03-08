from django.core.management.base import BaseCommand

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

    def handle(self, *args, **options):
        server = get_mcp_server()
        transport = options["transport"] or get_setting("TRANSPORT")

        self.stdout.write(self.style.SUCCESS(f"Starting MCP server ({transport})..."))

        if transport == "stdio":
            server.run(transport="stdio")
        else:
            server.run(
                transport="streamable-http",
                host=options["host"],
                port=options["port"],
            )
