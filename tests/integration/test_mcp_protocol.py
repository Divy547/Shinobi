"""Integration tests for MCP stdio protocol, tool discovery, and error handling."""

import sys
from pathlib import Path

import pytest
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


@pytest.mark.asyncio
async def test_mcp_protocol_stdio_lifecycle() -> None:
    """Verify MCP server lifecycle: initialize, list_tools, call_tool, and error handling over stdio."""
    repo_root = Path(__file__).parent.parent.parent
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "repovet_mcp.server"],
        cwd=str(repo_root),
    )

    async with (
        stdio_client(server_params) as (read_stream, write_stream),
        ClientSession(read_stream, write_stream) as session,
    ):
        # 1. Initialize MCP Protocol
        init_res = await session.initialize()
        assert init_res.server_info.name == "repovet-mcp"
        assert init_res.server_info.version == "0.1.0"

        # 2. Discover Registered Tools
        tools_res = await session.list_tools()
        tool_names = {t.name for t in tools_res.tools}
        expected_tools = {
            "analyze_repository",
            "check_hard_gates",
            "calculate_responsiveness",
            "analyze_contribution_accessibility",
            "calculate_scorecard",
            "validate_evidence",
            "generate_pdf_report",
        }
        assert expected_tools.issubset(tool_names)

        # Check schemas and descriptions
        for tool in tools_res.tools:
            assert tool.description
            assert tool.input_schema is not None
            assert tool.input_schema.get("type") == "object"

        # 3. Call Tool with Missing Arguments -> Returns is_error=True with schema validation failure
        missing_args_res = await session.call_tool("check_hard_gates", {})
        assert missing_args_res.is_error is True
        assert any("validation error" in str(c.text).lower() for c in missing_args_res.content)

        # 4. Call Tool with Non-Existent Audit ID -> Returns is_error=True with actionable error message
        not_found_res = await session.call_tool(
            "check_hard_gates", {"audit_id": "non_existent_audit_id_123"}
        )
        assert not_found_res.is_error is True
        assert any("No raw data found" in str(c.text) for c in not_found_res.content)

        # 5. Call Tool with Path Traversal Audit ID -> Returns is_error=True with traversal rejection
        traversal_res = await session.call_tool("check_hard_gates", {"audit_id": "../traversal_id"})
        assert traversal_res.is_error is True
        assert any("Invalid audit ID" in str(c.text) for c in traversal_res.content)


@pytest.mark.asyncio
async def test_mcp_protocol_cwd_independence(tmp_path: Path) -> None:
    """Verify MCP server starts cleanly and lists tools regardless of current working directory."""
    repo_root = Path(__file__).parent.parent.parent
    src_dir = repo_root / "src"

    import os

    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{src_dir}:{existing_pythonpath}" if existing_pythonpath else str(src_dir)

    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "repovet_mcp.server"],
        cwd=str(tmp_path),
        env=env,
    )

    async with (
        stdio_client(server_params) as (read_stream, write_stream),
        ClientSession(read_stream, write_stream) as session,
    ):
        init_res = await session.initialize()
        assert init_res.server_info.name == "repovet-mcp"
        tools_res = await session.list_tools()
        assert len(tools_res.tools) >= 7
