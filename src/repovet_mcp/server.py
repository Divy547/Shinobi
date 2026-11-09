"""RepoVet MCP Server entry point."""

import logging
import sys

try:
    from mcp.server import MCPServer
except ImportError:
    from mcp.server.fastmcp import FastMCP as MCPServer  # type: ignore[no-redef]

from repovet_mcp.config.settings import Settings, get_settings
from repovet_mcp.tools.vetting_tools import register_vetting_tools

logger = logging.getLogger("repovet_mcp")


def create_server(settings: Settings | None = None) -> MCPServer:
    """Create and configure the MCP server instance and register all tools."""
    resolved_settings = settings or get_settings()
    resolved_settings.validate_startup_config()
    server = MCPServer(
        name=resolved_settings.server_name,
        version=resolved_settings.server_version,
        instructions=(
            "RepoVet MCP: Autonomous open-source repository vetting server. "
            "Exposes tools to investigate repositories across nine phases, "
            "calculate 10-criterion scorecards, validate evidence, and generate audit reports."
        ),
    )
    register_vetting_tools(server, resolved_settings)
    return server


def main() -> None:
    """CLI entry point for running the RepoVet MCP server."""
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stderr,
    )
    logger.info("Initializing %s v%s", settings.server_name, settings.server_version)

    server = create_server(settings)
    server.run(transport="stdio")
    sys.exit(0)


if __name__ == "__main__":
    main()
