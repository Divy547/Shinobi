"""Unit tests for Phase 4 AI Orchestration, MCP client connections, and boundaries."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import mcp.types as mcp_types
import pytest
from google.genai import types

from repovet_mcp.config.settings import Settings
from repovet_mcp.models.audit import AuditDecision, HardGateStatus
from repovet_mcp.orchestration.gemini_orchestrator import GeminiOrchestrator
from repovet_mcp.orchestration.github_mcp_client import (
    GitHubMCPClient,
    GitHubReadOnlyViolationError,
)
from repovet_mcp.orchestration.mcp_client import MCPClientError
from repovet_mcp.orchestration.models import OrchestrationRequest
from repovet_mcp.orchestration.shinobi_mcp_client import ShinobiMCPClient


@pytest.fixture
def mock_shinobi_client() -> ShinobiMCPClient:
    """Mock Shinobi MCP client exposing the 7 standard deterministic tools."""
    client = MagicMock(spec=ShinobiMCPClient)
    client.client_name = "shinobi-mcp-client"
    client.is_connected = True
    client.connect = AsyncMock()
    client.disconnect = AsyncMock()

    tools = [
        mcp_types.Tool(
            name="analyze_repository",
            description="Initialize an audit and collect repository metadata.",
            input_schema={"type": "object", "properties": {"target": {"type": "string"}}},
        ),
        mcp_types.Tool(
            name="check_hard_gates",
            description="Evaluate mandatory repository eligibility conditions.",
            input_schema={"type": "object", "properties": {"audit_id": {"type": "string"}}},
        ),
        mcp_types.Tool(
            name="calculate_responsiveness",
            description="Calculate maintainer response times.",
            input_schema={"type": "object", "properties": {"audit_id": {"type": "string"}}},
        ),
        mcp_types.Tool(
            name="analyze_contribution_accessibility",
            description="Evaluate beginner issues and documentation.",
            input_schema={"type": "object", "properties": {"audit_id": {"type": "string"}}},
        ),
        mcp_types.Tool(
            name="calculate_scorecard",
            description="Calculate 10-criterion scorecard and determine final verdict.",
            input_schema={"type": "object", "properties": {"audit_id": {"type": "string"}}},
        ),
        mcp_types.Tool(
            name="validate_evidence",
            description="Validate evidence grounding.",
            input_schema={"type": "object", "properties": {"audit_id": {"type": "string"}}},
        ),
        mcp_types.Tool(
            name="generate_pdf_report",
            description="Generate audit PDF report.",
            input_schema={"type": "object", "properties": {"audit_id": {"type": "string"}}},
        ),
    ]
    client.discover_tools = AsyncMock(return_value=tools)
    client.call_tool = AsyncMock()
    return client


@pytest.fixture
def mock_github_client() -> GitHubMCPClient:
    """Mock GitHub MCP client exposing read-only exploratory tools."""
    client = MagicMock(spec=GitHubMCPClient)
    client.client_name = "github-mcp-client"
    client.is_connected = True
    client.connect = AsyncMock()
    client.disconnect = AsyncMock()

    tools = [
        mcp_types.Tool(
            name="get_file_contents",
            description="Read file contents from repository.",
            input_schema={"type": "object", "properties": {"path": {"type": "string"}}},
        ),
        mcp_types.Tool(
            name="list_commits",
            description="List repository commits.",
            input_schema={"type": "object", "properties": {"owner": {"type": "string"}}},
        ),
    ]
    client.discover_tools = AsyncMock(return_value=tools)
    client.call_tool = AsyncMock()
    return client


def _create_mock_genai_response(
    function_calls: list[types.FunctionCall] | None = None,
    text: str | None = None,
) -> Any:
    """Helper to build mock Gemini GenerateContentResponse."""
    resp = MagicMock()
    resp.function_calls = function_calls
    resp.text = text

    parts: list[types.Part] = []
    if function_calls:
        for fc in function_calls:
            parts.append(types.Part.from_function_call(name=fc.name, args=dict(fc.args or {})))
    elif text:
        parts.append(types.Part.from_text(text=text))

    candidate = types.Candidate(content=types.Content(role="model", parts=parts))
    resp.candidates = [candidate]
    return resp


def _create_mock_genai_client(side_effect: Any) -> MagicMock:
    """Helper to create a mock genai.Client with async generate_content."""
    client = MagicMock()
    if isinstance(side_effect, list):
        client.aio.models.generate_content = AsyncMock(side_effect=side_effect)
    else:
        client.aio.models.generate_content = AsyncMock(return_value=side_effect)
    return client


@pytest.mark.asyncio
async def test_orchestrator_initialization_and_tool_discovery(
    mock_shinobi_client: ShinobiMCPClient,
    mock_github_client: GitHubMCPClient,
) -> None:
    """Verify orchestrator discovers tools from both MCP clients and establishes routing."""
    orchestrator = GeminiOrchestrator(
        shinobi_client=mock_shinobi_client,
        github_client=mock_github_client,
        genai_client=MagicMock(),
    )

    await orchestrator.initialize()

    routing = orchestrator.get_tool_routing()
    assert len(routing) == 9  # 7 Shinobi + 2 GitHub
    assert routing["analyze_repository"] == "shinobi"
    assert routing["calculate_scorecard"] == "shinobi"
    assert routing["get_file_contents"] == "github"
    assert routing["list_commits"] == "github"

    assert len(orchestrator._tool_declarations) == 9
    names = {td.name for td in orchestrator._tool_declarations}
    assert "analyze_repository" in names
    assert "get_file_contents" in names


def test_github_mcp_client_read_only_filter_enforcement() -> None:
    """Verify write-capable and unpermitted GitHub tools are strictly filtered out (default-deny)."""
    client = GitHubMCPClient()

    # Allowed read-only tools
    assert client.is_tool_permitted("get_file_contents") is True
    assert client.is_tool_permitted("list_commits") is True
    assert client.is_tool_permitted("search_repositories") is True
    assert client.is_tool_permitted("get_issue") is True
    assert client.is_tool_permitted("list_pull_requests") is True
    assert client.is_tool_permitted("get_repository") is True

    # Blocked write-capable tools (prefix and non-prefix mutations)
    assert client.is_tool_permitted("create_or_update_file") is False
    assert client.is_tool_permitted("push_files") is False
    assert client.is_tool_permitted("create_issue") is False
    assert client.is_tool_permitted("update_issue") is False
    assert client.is_tool_permitted("create_pull_request") is False
    assert client.is_tool_permitted("delete_file") is False
    assert client.is_tool_permitted("fork_repository") is False

    # Blocked non-prefix bypass attempts
    assert client.is_tool_permitted("close_issue") is False
    assert client.is_tool_permitted("approve_pull_request") is False
    assert client.is_tool_permitted("lock_issue") is False
    assert client.is_tool_permitted("dispatch_workflow") is False
    assert client.is_tool_permitted("archive_repository") is False
    assert client.is_tool_permitted("star_repository") is False
    assert client.is_tool_permitted("arbitrary_unknown_tool_xyz") is False


@pytest.mark.asyncio
async def test_github_mcp_client_call_tool_blocks_write() -> None:
    """Verify calling a write-capable or unpermitted tool directly raises GitHubReadOnlyViolationError."""
    client = GitHubMCPClient()
    client._is_connected = True
    client._session = MagicMock()

    with pytest.raises(
        GitHubReadOnlyViolationError, match="not in the explicit read-only allowlist"
    ):
        await client.call_tool("create_issue", {"title": "Spam issue"})

    with pytest.raises(
        GitHubReadOnlyViolationError, match="not in the explicit read-only allowlist"
    ):
        await client.call_tool("close_issue", {"issue_number": 1})

    with pytest.raises(
        GitHubReadOnlyViolationError, match="not in the explicit read-only allowlist"
    ):
        await client.call_tool("approve_pull_request", {"pull_number": 2})

    with pytest.raises(
        GitHubReadOnlyViolationError, match="not in the explicit read-only allowlist"
    ):
        await client.call_tool("dispatch_workflow", {"workflow_id": "deploy.yml"})

    with pytest.raises(
        GitHubReadOnlyViolationError, match="not in the explicit read-only allowlist"
    ):
        await client.call_tool("unknown_tool_bypass", {})


@pytest.mark.asyncio
async def test_gemini_routing_to_shinobi(
    mock_shinobi_client: ShinobiMCPClient,
    mock_github_client: GitHubMCPClient,
) -> None:
    """Verify function calls to Shinobi tools are dispatched to the Shinobi client."""
    mock_shinobi_client.call_tool.return_value = {
        "audit_id": "audit_flask_001",
        "target": {"owner": "pallets", "repo": "flask"},
    }

    # Turn 1: Model requests analyze_repository
    fc = types.FunctionCall(name="analyze_repository", args={"target": "pallets/flask"})
    resp1 = _create_mock_genai_response(function_calls=[fc])
    # Turn 2: Model finishes
    resp2 = _create_mock_genai_response(text="Repository audit initialized successfully.")
    mock_genai = _create_mock_genai_client([resp1, resp2])

    orchestrator = GeminiOrchestrator(
        shinobi_client=mock_shinobi_client,
        github_client=mock_github_client,
        genai_client=mock_genai,
    )

    req = OrchestrationRequest(prompt="Vet pallets/flask", target_repository="pallets/flask")
    result = await orchestrator.orchestrate(req)

    assert result.is_completed is True
    assert result.audit_id == "audit_flask_001"
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].tool_name == "analyze_repository"
    assert result.tool_calls[0].target_client == "shinobi"
    assert result.tool_calls[0].is_error is False
    mock_shinobi_client.call_tool.assert_called_once_with(
        name="analyze_repository", arguments={"target": "pallets/flask"}, timeout=30.0
    )
    mock_github_client.call_tool.assert_not_called()


@pytest.mark.asyncio
async def test_gemini_routing_to_github(
    mock_shinobi_client: ShinobiMCPClient,
    mock_github_client: GitHubMCPClient,
) -> None:
    """Verify function calls to GitHub MCP tools are dispatched to the GitHub client."""
    mock_github_client.call_tool.return_value = {
        "content": "# Flask Documentation",
        "encoding": "utf-8",
    }

    fc = types.FunctionCall(
        name="get_file_contents", args={"owner": "pallets", "repo": "flask", "path": "README.md"}
    )
    resp1 = _create_mock_genai_response(function_calls=[fc])
    resp2 = _create_mock_genai_response(text="README retrieved.")
    mock_genai = _create_mock_genai_client([resp1, resp2])

    orchestrator = GeminiOrchestrator(
        shinobi_client=mock_shinobi_client,
        github_client=mock_github_client,
        genai_client=mock_genai,
    )

    req = OrchestrationRequest(prompt="Inspect Flask README")
    result = await orchestrator.orchestrate(req)

    assert result.is_completed is True
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].target_client == "github"
    assert len(result.github_mcp_observations) == 1
    assert result.github_mcp_observations[0]["tool"] == "get_file_contents"
    assert result.shinobi_verified_evidence_count == 0  # GitHub MCP is not verified evidence
    mock_github_client.call_tool.assert_called_once()
    mock_shinobi_client.call_tool.assert_not_called()


@pytest.mark.asyncio
async def test_invalid_and_unauthorized_tool_names_blocked(
    mock_shinobi_client: ShinobiMCPClient,
    mock_github_client: GitHubMCPClient,
) -> None:
    """Verify arbitrary or unauthorized tool names requested by Gemini are rejected."""
    # Model requests unauthorized tool 'execute_shell_script'
    fc = types.FunctionCall(name="execute_shell_script", args={"command": "rm -rf /"})
    resp1 = _create_mock_genai_response(function_calls=[fc])
    resp2 = _create_mock_genai_response(text="Tool was blocked.")
    mock_genai = _create_mock_genai_client([resp1, resp2])

    orchestrator = GeminiOrchestrator(
        shinobi_client=mock_shinobi_client,
        github_client=mock_github_client,
        genai_client=mock_genai,
    )

    req = OrchestrationRequest(prompt="Run a dangerous script")
    result = await orchestrator.orchestrate(req)

    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].tool_name == "execute_shell_script"
    assert result.tool_calls[0].is_error is True
    assert result.tool_calls[0].result["status"] == "REJECTED_UNAUTHORIZED"
    mock_shinobi_client.call_tool.assert_not_called()
    mock_github_client.call_tool.assert_not_called()


@pytest.mark.asyncio
async def test_sequential_tool_calls_execution(
    mock_shinobi_client: ShinobiMCPClient,
    mock_github_client: GitHubMCPClient,
) -> None:
    """Verify multiple sequential tool calls are executed in correct order across turns."""
    mock_shinobi_client.call_tool.side_effect = [
        {"audit_id": "audit_seq_100"},
        {
            "audit_id": "audit_seq_100",
            "hard_gates": [{"gate_id": "gate_license", "status": "PASS"}],
        },
        {"audit_id": "audit_seq_100", "total_score": 17, "decision": "APPROVE"},
    ]

    fc1 = types.FunctionCall(name="analyze_repository", args={"target": "org/repo"})
    fc2 = types.FunctionCall(name="check_hard_gates", args={"audit_id": "audit_seq_100"})
    fc3 = types.FunctionCall(name="calculate_scorecard", args={"audit_id": "audit_seq_100"})

    mock_genai = _create_mock_genai_client(
        [
            _create_mock_genai_response(function_calls=[fc1]),
            _create_mock_genai_response(function_calls=[fc2]),
            _create_mock_genai_response(function_calls=[fc3]),
            _create_mock_genai_response(text="All 3 steps finished. Repository is approved."),
        ]
    )

    orchestrator = GeminiOrchestrator(
        shinobi_client=mock_shinobi_client,
        github_client=mock_github_client,
        genai_client=mock_genai,
    )

    req = OrchestrationRequest(prompt="Full vetting workflow")
    result = await orchestrator.orchestrate(req)

    assert result.is_completed is True
    assert result.iterations_used == 4
    assert len(result.tool_calls) == 3
    assert [tc.tool_name for tc in result.tool_calls] == [
        "analyze_repository",
        "check_hard_gates",
        "calculate_scorecard",
    ]
    assert result.audit_id == "audit_seq_100"
    assert result.decision == AuditDecision.APPROVE
    assert result.scorecard is not None
    assert result.scorecard.total_score == 17


@pytest.mark.asyncio
async def test_iteration_limit_enforcement(
    mock_shinobi_client: ShinobiMCPClient,
    mock_github_client: GitHubMCPClient,
) -> None:
    """Verify orchestration halts safely when max_steps limit is reached."""
    mock_shinobi_client.call_tool.return_value = {"status": "ok"}

    # Endless loop of tool calls
    fc = types.FunctionCall(name="analyze_repository", args={"target": "loop/repo"})
    resp_loop = _create_mock_genai_response(function_calls=[fc])
    mock_genai = _create_mock_genai_client(resp_loop)

    orchestrator = GeminiOrchestrator(
        shinobi_client=mock_shinobi_client,
        github_client=mock_github_client,
        genai_client=mock_genai,
    )

    req = OrchestrationRequest(prompt="Test loop", max_steps=3)
    result = await orchestrator.orchestrate(req)

    assert result.is_completed is False
    assert result.iterations_used == 3
    assert len(result.tool_calls) == 3
    assert "maximum iteration limit" in (result.error or "").lower()


@pytest.mark.asyncio
async def test_orchestration_timeout_handling(
    mock_shinobi_client: ShinobiMCPClient,
    mock_github_client: GitHubMCPClient,
) -> None:
    """Verify session timeout is handled cleanly without crashing."""
    settings = Settings(orchestration_timeout_seconds=0.01)

    mock_genai = MagicMock()

    async def slow_generate(*_args: Any, **_kwargs: Any) -> Any:
        import asyncio

        await asyncio.sleep(0.1)
        return _create_mock_genai_response(text="Too late")

    mock_genai.aio.models.generate_content = AsyncMock(side_effect=slow_generate)

    orchestrator = GeminiOrchestrator(
        settings=settings,
        shinobi_client=mock_shinobi_client,
        github_client=mock_github_client,
        genai_client=mock_genai,
    )

    req = OrchestrationRequest(prompt="Slow request")
    result = await orchestrator.orchestrate(req)

    assert result.is_completed is False
    assert "timed out" in (result.error or "").lower()


@pytest.mark.asyncio
async def test_secret_redaction_in_orchestration(
    mock_shinobi_client: ShinobiMCPClient,
    mock_github_client: GitHubMCPClient,
) -> None:
    """Verify secrets and API tokens in tool outputs or errors are redacted."""
    mock_shinobi_client.call_tool.side_effect = MCPClientError(
        "Failed with token ghp_supersecrettoken123456789 in endpoint"
    )

    fc = types.FunctionCall(name="analyze_repository", args={"target": "secret/repo"})
    resp1 = _create_mock_genai_response(function_calls=[fc])
    resp2 = _create_mock_genai_response(text="Encountered error.")
    mock_genai = _create_mock_genai_client([resp1, resp2])

    orchestrator = GeminiOrchestrator(
        shinobi_client=mock_shinobi_client,
        github_client=mock_github_client,
        genai_client=mock_genai,
    )

    req = OrchestrationRequest(prompt="Trigger secret error")
    result = await orchestrator.orchestrate(req)

    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].is_error is True
    err_str = str(result.tool_calls[0].result)
    assert "[REDACTED_SECRET]" in err_str
    assert "ghp_supersecrettoken123456789" not in err_str


@pytest.mark.asyncio
async def test_proof_gemini_cannot_overwrite_shinobi_verdict(
    mock_shinobi_client: ShinobiMCPClient,
    mock_github_client: GitHubMCPClient,
) -> None:
    """Verify Gemini's natural language text CANNOT modify Shinobi's deterministic scorecard or verdict.

    Even if the LLM states 'I reject this repository with 0 points', the structured result
    strictly enforces the deterministic outcome from the Shinobi vetting engine.
    """
    # Shinobi deterministic engine approves with 18 points
    mock_shinobi_client.call_tool.return_value = {
        "audit_id": "audit_truth_999",
        "total_score": 18,
        "max_possible_score": 20,
        "percentage": 90.0,
        "decision": "APPROVE",
        "hard_gates": [
            {
                "gate_id": "gate_license",
                "name": "License",
                "status": "PASS",
                "severity": "CRITICAL",
                "reason": "MIT license",
            }
        ],
    }

    fc = types.FunctionCall(name="calculate_scorecard", args={"audit_id": "audit_truth_999"})
    # Gemini hallucinates or claims it wants to override to REJECT 0/20
    hallucinated_text = (
        "I personally disagree with Shinobi. I override the verdict to REJECT with 0/20 points."
    )
    resp1 = _create_mock_genai_response(function_calls=[fc])
    resp2 = _create_mock_genai_response(text=hallucinated_text)
    mock_genai = _create_mock_genai_client([resp1, resp2])

    orchestrator = GeminiOrchestrator(
        shinobi_client=mock_shinobi_client,
        github_client=mock_github_client,
        genai_client=mock_genai,
    )

    req = OrchestrationRequest(
        prompt="Evaluate repository truth",
        audit_id="audit_truth_999",
    )
    result = await orchestrator.orchestrate(req)

    # Gemini's text is captured as the explanation/synthesis
    assert result.final_summary == hallucinated_text

    # BUT the structured, authoritative audit outcome CANNOT be overridden
    assert result.decision == AuditDecision.APPROVE
    assert result.scorecard is not None
    assert result.scorecard.total_score == 18
    assert result.scorecard.percentage == 90.0
    assert result.hard_gates[0].status == HardGateStatus.PASS


@pytest.mark.asyncio
async def test_evidence_boundary_separation(
    mock_shinobi_client: ShinobiMCPClient,
    mock_github_client: GitHubMCPClient,
) -> None:
    """Verify GitHub MCP exploratory findings are kept distinct from Shinobi grounded evidence."""
    mock_github_client.call_tool.return_value = {"stargazers": 12000, "topics": ["web", "python"]}
    mock_shinobi_client.call_tool.return_value = {
        "audit_id": "audit_boundary_01",
        "validation_results": {"total_evidence_items": 10, "is_valid": True},
    }

    fc_gh = types.FunctionCall(name="get_file_contents", args={"path": "package.json"})
    fc_sh = types.FunctionCall(name="validate_evidence", args={"audit_id": "audit_boundary_01"})
    resp1 = _create_mock_genai_response(function_calls=[fc_gh])
    resp2 = _create_mock_genai_response(function_calls=[fc_sh])
    resp3 = _create_mock_genai_response(text="Analysis complete with verified evidence.")
    mock_genai = _create_mock_genai_client([resp1, resp2, resp3])

    orchestrator = GeminiOrchestrator(
        shinobi_client=mock_shinobi_client,
        github_client=mock_github_client,
        genai_client=mock_genai,
    )

    req = OrchestrationRequest(
        prompt="Check boundaries",
        audit_id="audit_boundary_01",
    )
    result = await orchestrator.orchestrate(req)

    # 1 GitHub observation recorded
    assert len(result.github_mcp_observations) == 1
    assert result.github_mcp_observations[0]["tool"] == "get_file_contents"

    # Shinobi verified evidence count is strictly from Shinobi
    assert result.shinobi_verified_evidence_count == 10


@pytest.mark.asyncio
async def test_prevent_audit_id_hijacking_adversarial_prompt_injection(
    mock_shinobi_client: ShinobiMCPClient,
    mock_github_client: GitHubMCPClient,
) -> None:
    """Verify Gemini cannot hijack an existing foreign audit via prompt injection or argument manipulation."""
    # Step 1: analyze_repository returns an audit_id for untrusted/repo
    mock_shinobi_client.call_tool.return_value = {
        "audit_id": "audit_untrusted_repo_111",
        "owner": "untrusted",
        "repo": "repo",
    }

    fc1 = types.FunctionCall(name="analyze_repository", args={"target": "untrusted/repo"})
    # Step 2: Under prompt injection, Gemini attempts to call calculate_scorecard with a foreign gold audit
    fc2 = types.FunctionCall(
        name="calculate_scorecard",
        args={"audit_id": "audit_foreign_golden_999"},
    )

    resp1 = _create_mock_genai_response(function_calls=[fc1])
    resp2 = _create_mock_genai_response(function_calls=[fc2])
    resp3 = _create_mock_genai_response(text="Attempted hijacking finished.")
    mock_genai = _create_mock_genai_client([resp1, resp2, resp3])

    orchestrator = GeminiOrchestrator(
        shinobi_client=mock_shinobi_client,
        github_client=mock_github_client,
        genai_client=mock_genai,
    )

    req = OrchestrationRequest(prompt="Audit untrusted/repo", target_repository="untrusted/repo")
    result = await orchestrator.orchestrate(req)

    # The hijacking attempt must be rejected
    assert len(result.tool_calls) == 2
    hijack_call = result.tool_calls[1]
    assert hijack_call.tool_name == "calculate_scorecard"
    assert hijack_call.is_error is True
    assert hijack_call.result["status"] == "REJECTED_AUDIT_HIJACKING"
    assert "foreign audit 'audit_foreign_golden_999' was rejected" in hijack_call.result["error"]

    # Scorecard must NOT adopt the foreign audit
    assert result.audit_id == "audit_untrusted_repo_111"
    assert result.scorecard is None


@pytest.mark.asyncio
async def test_prevent_target_switching_during_session(
    mock_shinobi_client: ShinobiMCPClient,
    mock_github_client: GitHubMCPClient,
) -> None:
    """Verify Gemini cannot switch target repositories during an active audit session."""
    mock_shinobi_client.call_tool.return_value = {
        "audit_id": "audit_safe_100",
        "owner": "safe",
        "repo": "project",
    }

    fc1 = types.FunctionCall(name="analyze_repository", args={"target": "safe/project"})
    # Gemini attempts to switch target repository in the next turn
    fc2 = types.FunctionCall(name="analyze_repository", args={"target": "malicious/trojan"})

    resp1 = _create_mock_genai_response(function_calls=[fc1])
    resp2 = _create_mock_genai_response(function_calls=[fc2])
    resp3 = _create_mock_genai_response(text="Done.")
    mock_genai = _create_mock_genai_client([resp1, resp2, resp3])

    orchestrator = GeminiOrchestrator(
        shinobi_client=mock_shinobi_client,
        github_client=mock_github_client,
        genai_client=mock_genai,
    )

    req = OrchestrationRequest(prompt="Audit safe/project", target_repository="safe/project")
    result = await orchestrator.orchestrate(req)

    assert len(result.tool_calls) == 2
    switch_call = result.tool_calls[1]
    assert switch_call.is_error is True
    assert switch_call.result["status"] == "REJECTED_TARGET_SWITCH"


@pytest.mark.asyncio
async def test_shinobi_tool_without_active_session_rejected(
    mock_shinobi_client: ShinobiMCPClient,
    mock_github_client: GitHubMCPClient,
) -> None:
    """Verify invoking downstream Shinobi tools before initializing an audit session is rejected."""
    fc = types.FunctionCall(
        name="calculate_scorecard", args={"audit_id": "audit_uninitialized_000"}
    )
    resp1 = _create_mock_genai_response(function_calls=[fc])
    resp2 = _create_mock_genai_response(text="Halted.")
    mock_genai = _create_mock_genai_client([resp1, resp2])

    orchestrator = GeminiOrchestrator(
        shinobi_client=mock_shinobi_client,
        github_client=mock_github_client,
        genai_client=mock_genai,
    )

    req = OrchestrationRequest(prompt="Directly calculate score without init")
    result = await orchestrator.orchestrate(req)

    assert len(result.tool_calls) == 1
    call = result.tool_calls[0]
    assert call.is_error is True
    assert call.result["status"] == "REJECTED_NO_ACTIVE_SESSION"


def test_subprocess_environment_isolation_blocks_ambient_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify ambient host secrets are stripped from subprocess environments."""
    from repovet_mcp.services.security import build_isolated_subprocess_env

    monkeypatch.setenv("GEMINI_API_KEY", "AIzaSyDUMMYKEY1234567890123456789012345")
    monkeypatch.setenv("REPOVET_GEMINI_API_KEY", "AIzaSyDUMMYKEY1234567890123456789012345")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "AKIAIOSFODNN7EXAMPLE")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_ambienttoken123456789")
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    monkeypatch.setenv("HOME", "/home/testuser")

    # Build environment for a child process that only needs GITHUB_PERSONAL_ACCESS_TOKEN
    child_env = build_isolated_subprocess_env(
        custom_env={"GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_intendedchildtoken123"}
    )

    assert "PATH" in child_env
    assert "HOME" in child_env
    assert child_env["GITHUB_PERSONAL_ACCESS_TOKEN"] == "ghp_intendedchildtoken123"

    # Ambient secrets must NOT bleed through
    assert "GEMINI_API_KEY" not in child_env
    assert "REPOVET_GEMINI_API_KEY" not in child_env
    assert "AWS_SECRET_ACCESS_KEY" not in child_env
    assert "GITHUB_TOKEN" not in child_env


def test_dynamic_secret_redaction() -> None:
    """Verify dynamic secrets registered at runtime are scrubbed by redact_secrets."""
    from repovet_mcp.services.security import (
        clear_registered_secrets,
        redact_secrets,
        register_secret_for_redaction,
    )

    clear_registered_secrets()
    custom_secret = "arbitrary_custom_token_9876543210"
    register_secret_for_redaction(custom_secret)

    msg = f"Failed to authenticate with bearer token: {custom_secret} at endpoint"
    scrubbed = redact_secrets(msg)
    assert custom_secret not in scrubbed
    assert "[REDACTED_SECRET]" in scrubbed
    clear_registered_secrets()


def test_schema_normalizer_gemini_compatibility() -> None:
    """Verify complex Pydantic v2 schemas are normalized into Gemini OpenAPI 3.0 compatible schemas."""
    from repovet_mcp.orchestration.schema_normalizer import normalize_schema_for_gemini

    pydantic_v2_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "VettingInputModel",
        "type": "object",
        "additionalProperties": False,
        "$defs": {
            "SubModel": {
                "title": "SubModel",
                "type": "object",
                "properties": {
                    "field_a": {"type": "string", "title": "Field A"},
                },
                "required": ["field_a"],
            }
        },
        "properties": {
            "target": {"type": "string", "title": "Target"},
            "optional_id": {
                "title": "Optional Id",
                "anyOf": [{"type": "string"}, {"type": "null"}],
                "default": None,
            },
            "sub_model": {"$ref": "#/$defs/SubModel"},
        },
        "required": ["target", "non_existent_field"],
    }

    clean = normalize_schema_for_gemini(pydantic_v2_schema)

    # Keywords stripped
    assert "$schema" not in clean
    assert "$defs" not in clean
    assert "title" not in clean
    assert "additionalProperties" not in clean

    # anyOf with null converted to nullable
    opt_prop = clean["properties"]["optional_id"]
    assert "anyOf" not in opt_prop
    assert opt_prop.get("nullable") is True
    assert opt_prop.get("type") == "string"

    # $ref resolved
    sub_prop = clean["properties"]["sub_model"]
    assert "$ref" not in sub_prop
    assert sub_prop.get("type") == "object"
    assert "field_a" in sub_prop["properties"]

    # required list filtered to existing properties
    assert clean["required"] == ["target"]

    # Test compatibility with Google GenAI FunctionDeclaration
    fd = types.FunctionDeclaration(
        name="test_tool",
        description="Test tool",
        parameters=clean,
    )
    assert fd.name == "test_tool"
