"""Integration tests for ShinobiMCPClient real subprocess stdio lifecycle and working directory independence."""

from pathlib import Path

import pytest

from repovet_mcp.config.settings import Settings
from repovet_mcp.orchestration.shinobi_mcp_client import (
    EXPECTED_SHINOBI_TOOLS,
    ShinobiMCPClient,
)


@pytest.mark.asyncio
async def test_shinobi_mcp_client_real_subprocess_lifecycle(tmp_path: Path) -> None:
    """Verify real Shinobi MCP server stdio lifecycle: startup, discovery, schemas, and shutdown.

    Runs an actual local Python stdio subprocess without requiring Gemini or GitHub credentials.
    """
    settings = Settings(
        data_dir=tmp_path / "data",
        reports_dir=tmp_path / "reports",
        mcp_timeout_seconds=15.0,
    )

    client = ShinobiMCPClient(settings=settings)
    assert client.is_connected is False

    try:
        await client.connect()
        assert client.is_connected is True

        # Tool discovery
        tools = await client.discover_tools()
        discovered_names = {t.name for t in tools}

        # Assert all 7 deterministic vetting tools are discovered
        assert discovered_names == EXPECTED_SHINOBI_TOOLS
        assert len(tools) == 7

        # Assert valid input schemas
        for tool in tools:
            assert tool.description
            schema = getattr(tool, "input_schema", None) or getattr(tool, "inputSchema", None)
            assert isinstance(schema, dict)
            assert schema.get("type") == "object"
            assert "properties" in schema

    finally:
        await client.disconnect()
        assert client.is_connected is False


@pytest.mark.asyncio
async def test_shinobi_mcp_client_working_directory_independence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify ShinobiMCPClient starts and discovers tools independently of the caller's working directory.

    Simulates execution from an arbitrary temporary directory outside the repository root.
    """
    # Change current working directory to an isolated temporary folder
    monkeypatch.chdir(tmp_path)

    client = ShinobiMCPClient()

    try:
        await client.connect()
        assert client.is_connected is True

        tools = await client.discover_tools()
        assert len(tools) == 7
        assert {t.name for t in tools} == EXPECTED_SHINOBI_TOOLS

    finally:
        await client.disconnect()
        assert client.is_connected is False
