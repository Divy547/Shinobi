"""Shinobi MCP client connecting to the local Shinobi vetting engine over stdio transport."""

import logging
import os
import sys
from pathlib import Path
from typing import Any

import mcp.types as mcp_types

from repovet_mcp.config.settings import Settings, get_settings
from repovet_mcp.orchestration.mcp_client import BaseMCPClient, MCPClientError
from repovet_mcp.services.security import redact_secrets

logger = logging.getLogger("repovet_mcp.orchestration.shinobi")

EXPECTED_SHINOBI_TOOLS = {
    "analyze_repository",
    "check_hard_gates",
    "calculate_responsiveness",
    "analyze_contribution_accessibility",
    "calculate_scorecard",
    "validate_evidence",
    "generate_pdf_report",
}


class ShinobiMCPClient(BaseMCPClient):
    """Client for connecting to the local Shinobi MCP server running the deterministic vetting engine."""

    def __init__(
        self,
        settings: Settings | None = None,
        cwd: Path | str | None = None,
    ) -> None:
        self.settings = settings or get_settings()

        # Resolve explicit repository root to decouple subprocess startup from caller's cwd
        repo_root = Path(__file__).resolve().parent.parent.parent.parent
        effective_cwd = Path(cwd) if cwd else repo_root

        # Ensure PYTHONPATH includes src directory for clean module execution
        src_path = str(repo_root / "src")
        existing_pythonpath = os.environ.get("PYTHONPATH", "")
        combined_pythonpath = (
            f"{src_path}{os.pathsep}{existing_pythonpath}" if existing_pythonpath else src_path
        )
        env = {
            "PYTHONPATH": combined_pythonpath,
        }

        # If command is repovet-mcp and repovet-mcp is not on system path, fallback to python -m
        command = self.settings.shinobi_mcp_command
        args = list(self.settings.shinobi_mcp_args)

        # If user did not provide args and command is python or repovet-mcp
        if command in ("repovet-mcp", "python", "python3") and not args:
            command = sys.executable
            args = ["-m", "repovet_mcp.server"]

        super().__init__(
            command=command,
            args=args,
            env=env,
            timeout=self.settings.mcp_timeout_seconds,
            cwd=effective_cwd,
            client_name="shinobi-mcp-client",
        )

    async def discover_tools(self) -> list[mcp_types.Tool]:
        """Discover tools from Shinobi MCP server and verify schema presence."""
        tools = await super().discover_tools()
        discovered_names = {t.name for t in tools}

        missing = EXPECTED_SHINOBI_TOOLS - discovered_names
        if missing:
            logger.warning(
                "Shinobi MCP server missing expected tools: %s. Discovered: %s",
                missing,
                discovered_names,
            )
        else:
            logger.info("Shinobi MCP server successfully registered all 7 deterministic tools.")

        return tools

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> Any:
        """Execute a deterministic Shinobi vetting tool."""
        try:
            return await super().call_tool(name=name, arguments=arguments, timeout=timeout)
        except Exception as exc:
            safe_msg = redact_secrets(str(exc))
            raise MCPClientError(safe_msg) from exc
