from __future__ import annotations

from io import StringIO
from unittest.mock import MagicMock, patch

from django.core.management import call_command


class TestRunMCPServerCommand:
    @patch("drf_mcp_docs.management.commands.runmcpserver.get_mcp_server")
    def test_command_stdio_transport(self, mock_get_server):
        mock_server = MagicMock()
        mock_get_server.return_value = mock_server

        out = StringIO()
        call_command("runmcpserver", "--transport", "stdio", stdout=out)

        mock_server.run.assert_called_once_with(transport="stdio")
        assert "Starting MCP server" in out.getvalue()

    @patch("drf_mcp_docs.management.commands.runmcpserver.get_mcp_server")
    def test_command_http_transport(self, mock_get_server):
        mock_server = MagicMock()
        mock_get_server.return_value = mock_server

        out = StringIO()
        call_command(
            "runmcpserver",
            "--transport",
            "streamable-http",
            "--host",
            "0.0.0.0",
            "--port",
            "9000",
            stdout=out,
        )

        assert mock_server.settings.host == "0.0.0.0"
        assert mock_server.settings.port == 9000
        mock_server.run.assert_called_once_with(transport="streamable-http")

    @patch("drf_mcp_docs.management.commands.runmcpserver.get_mcp_server")
    @patch("drf_mcp_docs.management.commands.runmcpserver.get_setting", return_value="stdio")
    def test_command_default_transport_from_settings(self, mock_setting, mock_get_server):
        mock_server = MagicMock()
        mock_get_server.return_value = mock_server

        out = StringIO()
        call_command("runmcpserver", stdout=out)

        mock_server.run.assert_called_once_with(transport="stdio")
