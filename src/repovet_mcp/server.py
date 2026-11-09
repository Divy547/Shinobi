"""RepoVet MCP Server entry point."""

import logging
import sys

try:
    from mcp.server import MCPServer
except ImportError:
    from mcp.server.fastmcp import FastMCP as MCPServer  # type: ignore[no-redef]

from repovet_mcp.config.settings import Settings, get_settings

logger = logging.getLogger("repovet_mcp")


def create_server(settings: Settings | None = None) -> MCPServer:
    """Create and configure the MCP server instance."""
    resolved_settings = settings or get_settings()
    return MCPServer(
        name=resolved_settings.server_name,
        version=resolved_settings.server_version,
        instructions=(
            "RepoVet MCP: Autonomous open-source repository vetting server. "
            "Exposes tools to investigate repositories across nine phases, "
            "calculate 10-criterion scorecards, and generate audit reports."
        ),
    )


def main() -> None:
    """CLI entry point for running the RepoVet MCP server."""
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger.info("Initializing %s v%s", settings.server_name, settings.server_version)

    server = create_server(settings)
    server.run(transport="stdio")
    sys.exit(0)


if __name__ == "__main__":
    main()
