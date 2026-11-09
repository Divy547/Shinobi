"""Unit tests for MCP tool definitions, descriptions, schemas, and error boundaries."""

import pytest

try:
    from mcp.server.mcpserver.exceptions import ToolError
except (ImportError, ModuleNotFoundError):
    try:
        from mcp.server.fastmcp.exceptions import ToolError
    except (ImportError, ModuleNotFoundError):

        class ToolError(Exception):
            pass


from repovet_mcp.server import create_server
from repovet_mcp.tools.vetting_tools import VettingToolHandlers


@pytest.mark.asyncio
async def test_all_seven_tools_registered_with_schemas() -> None:
    """Verify all 7 deterministic vetting tools are registered with schemas and rich descriptions."""
    server = create_server()
    tools = await server.list_tools()
    tool_map = {t.name: t for t in tools}

    expected_tools = {
        "analyze_repository",
        "check_hard_gates",
        "calculate_responsiveness",
        "analyze_contribution_accessibility",
        "calculate_scorecard",
        "validate_evidence",
        "generate_pdf_report",
    }

    assert expected_tools == set(tool_map.keys())

    # Verify analyze_repository schema
    analyze_tool = tool_map["analyze_repository"]
    assert analyze_tool.description and len(analyze_tool.description) > 30
    assert analyze_tool.input_schema["type"] == "object"
    assert "target" in analyze_tool.input_schema["properties"]
    assert analyze_tool.input_schema["properties"]["target"]["type"] == "string"
    assert "target" in analyze_tool.input_schema["required"]
    assert "audit_id" in analyze_tool.input_schema["properties"]

    # Verify the other 6 tools require audit_id
    for name in expected_tools - {"analyze_repository"}:
        tool = tool_map[name]
        assert tool.description and len(tool.description) > 30
        assert tool.input_schema["type"] == "object"
        assert "audit_id" in tool.input_schema["properties"]
        assert tool.input_schema["properties"]["audit_id"]["type"] == "string"
        assert "audit_id" in tool.input_schema["required"]


@pytest.mark.asyncio
async def test_server_instructions() -> None:
    """Verify server instructions explain the AI workflow, rules, and 7 tools."""
    server = create_server()
    assert server.instructions is not None
    assert "Shinobi" in server.instructions
    assert "analyze_repository" in server.instructions
    assert "calculate_scorecard" in server.instructions
    assert "generate_pdf_report" in server.instructions
    assert "APPROVE" in server.instructions


@pytest.mark.asyncio
async def test_tool_error_wrapper_redacts_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify exceptions inside tool execution are caught and secrets are redacted."""
    server = create_server()

    # Monkeypatch analyze_repository on handlers to raise an error containing a secret token
    async def mock_fail(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("GitHub connection failed with token ghp_secretpattoken1234567890")

    monkeypatch.setattr(VettingToolHandlers, "analyze_repository", mock_fail)

    with pytest.raises(ToolError) as exc_info:
        await server.call_tool("analyze_repository", {"target": "psf/requests"})

    err_msg = str(exc_info.value)
    assert "[REDACTED_SECRET]" in err_msg
    assert "ghp_secretpattoken1234567890" not in err_msg
