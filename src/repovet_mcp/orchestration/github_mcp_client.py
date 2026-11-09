"""GitHub MCP client connecting to the official GitHub MCP server over local stdio transport."""

import logging
from typing import Any

import mcp.types as mcp_types

from repovet_mcp.config.settings import Settings, get_settings
from repovet_mcp.orchestration.mcp_client import BaseMCPClient, MCPClientError
from repovet_mcp.services.security import redact_secrets, register_secret_for_redaction

logger = logging.getLogger("repovet_mcp.orchestration.github")

# Explicit positive allowlist of verified read-only GitHub MCP tools (Default-Deny)
# Any tool not explicitly listed here is strictly blocked from discovery and execution.
ALLOWED_READ_ONLY_TOOLS = frozenset(
    {
        "get_file_contents",
        "get_issue",
        "list_issues",
        "list_issue_comments",
        "get_pull_request",
        "list_pull_requests",
        "list_pull_request_commits",
        "list_pull_request_files",
        "list_pull_request_reviews",
        "list_pull_request_comments",
        "search_repositories",
        "search_issues",
        "search_pull_requests",
        "search_code",
        "search_commits",
        "list_commits",
        "get_commit",
        "list_branches",
        "get_branch",
        "list_tags",
        "list_releases",
        "get_release",
        "get_repository",
    }
)


class GitHubReadOnlyViolationError(PermissionError):
    """Raised when an attempt is made to discover or invoke write-capable or unpermitted GitHub tools."""


class GitHubMCPClient(BaseMCPClient):
    """Specialized MCP client for interacting with the official GitHub MCP server in strict read-only mode."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

        # Build execution environment with injected authentication token ONLY.
        # Unrelated ambient host credentials (e.g. GEMINI_API_KEY) are never passed.
        env: dict[str, str] = {}
        if self.settings.has_github_auth and self.settings.github_token:
            token_val = self.settings.github_token.get_secret_value().strip()
            env[self.settings.github_mcp_token_env_var] = token_val
            # Also set standard GITHUB_TOKEN fallback for compatibility
            env["GITHUB_TOKEN"] = token_val
            register_secret_for_redaction(token_val)

        super().__init__(
            command=self.settings.github_mcp_command,
            args=self.settings.github_mcp_args,
            env=env,
            timeout=self.settings.mcp_timeout_seconds,
            client_name="github-mcp-client",
        )

    def is_tool_permitted(self, tool_name: str) -> bool:
        """Verify whether a tool is in the explicit positive read-only allowlist (Default-Deny)."""
        clean_name = tool_name.lower().strip()
        return clean_name in ALLOWED_READ_ONLY_TOOLS

    async def discover_tools(self) -> list[mcp_types.Tool]:
        """Discover tools from GitHub MCP server, filtering out everything not in the positive allowlist."""
        raw_tools = await super().discover_tools()

        # Enforce positive allowlist filter
        permitted_tools: list[mcp_types.Tool] = []
        for tool in raw_tools:
            if self.is_tool_permitted(tool.name):
                permitted_tools.append(tool)
            else:
                logger.debug(
                    "Blocked unpermitted or write-capable GitHub MCP tool from discovery: '%s'",
                    tool.name,
                )

        self._discovered_tools = {tool.name: tool for tool in permitted_tools}
        logger.info(
            "GitHub MCP client registered %d read-only tools (filtered out %d unpermitted/write tools)",
            len(permitted_tools),
            len(raw_tools) - len(permitted_tools),
        )
        return permitted_tools

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> Any:
        """Invoke a permitted read-only GitHub MCP tool with strict allowlist enforcement."""
        if not self.is_tool_permitted(name):
            msg = (
                f"Security Violation: Tool '{name}' is not in the explicit read-only allowlist. "
                "GitHub MCP client operates under strict default-deny read-only security."
            )
            logger.error(msg)
            raise GitHubReadOnlyViolationError(msg)

        try:
            return await super().call_tool(name=name, arguments=arguments, timeout=timeout)
        except Exception as exc:
            safe_msg = redact_secrets(str(exc))
            raise MCPClientError(safe_msg) from exc
