"""Integration test for server initialization with configuration."""

import pytest

from repovet_mcp.config.settings import Settings
from repovet_mcp.server import create_server


def test_server_initialization_with_settings(
    monkeypatch: pytest.MonkeyPatch, clean_settings: Settings
) -> None:
    """Verify that FastMCP server initializes using configured settings."""
    assert clean_settings.server_name == "repovet-mcp"
    monkeypatch.setenv("REPOVET_SERVER_NAME", "custom-repovet-mcp")
    server = create_server()
    assert server is not None
    assert server.name == "custom-repovet-mcp"
