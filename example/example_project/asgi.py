import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "example_project.settings")

django_app = get_asgi_application()

# Mount MCP alongside Django — available at /mcp/ by default
from drf_mcp_docs.urls import mount_mcp  # noqa: E402

application = mount_mcp(django_app)
