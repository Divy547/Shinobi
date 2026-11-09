"""Orchestration layer combining Gemini function calling with Shinobi and GitHub MCP clients."""

from repovet_mcp.orchestration.gemini_orchestrator import GeminiOrchestrator
from repovet_mcp.orchestration.github_mcp_client import (
    ALLOWED_READ_ONLY_TOOLS,
    GitHubMCPClient,
    GitHubReadOnlyViolationError,
)
from repovet_mcp.orchestration.mcp_client import (
    BaseMCPClient,
    MCPClientError,
    MCPToolExecutionError,
)
from repovet_mcp.orchestration.models import (
    OrchestrationRequest,
    OrchestrationResult,
    ToolCallRecord,
)
from repovet_mcp.orchestration.schema_normalizer import normalize_schema_for_gemini
from repovet_mcp.orchestration.shinobi_mcp_client import ShinobiMCPClient

__all__ = [
    "ALLOWED_READ_ONLY_TOOLS",
    "BaseMCPClient",
    "GeminiOrchestrator",
    "GitHubMCPClient",
    "GitHubReadOnlyViolationError",
    "MCPClientError",
    "MCPToolExecutionError",
    "OrchestrationRequest",
    "OrchestrationResult",
    "ShinobiMCPClient",
    "ToolCallRecord",
    "normalize_schema_for_gemini",
]
