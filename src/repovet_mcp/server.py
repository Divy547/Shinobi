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
            "Shinobi (RepoVet MCP): Deterministic open-source repository vetting server.\n\n"
            "Exposes 7 deterministic tools to investigate repositories, verify hard gates, "
            "calculate 10-criterion scorecards (0-100), validate evidence grounding, and generate executive PDF reports with SHA-256 artifact integrity manifests.\n\n"
            "Recommended Workflow:\n"
            "1. analyze_repository(owner, repo, audit_id=None): Mandatory first step. Ingests verified GitHub REST primary evidence "
            "into local snapshot storage and returns an audit_id.\n"
            "2. Optional diagnostics: check_hard_gates(audit_id), calculate_responsiveness(audit_id), analyze_contribution_accessibility(audit_id).\n"
            "3. calculate_scorecard(audit_id): Evaluates all 10 weighted vetting criteria and renders an immutable audit decision (APPROVE, FLAG, REJECT).\n"
            "4. validate_evidence(audit_id): Verifies evidence grounding, URLs, and integrity against Shinobi's confidence taxonomy.\n"
            "5. generate_pdf_report(audit_id): Compiles a formal ReportLab PDF report under reports/generated/ (note: the compiled PDF is generated outside the data/ SHA-256 integrity manifest).\n\n"
            "Important Rules:\n"
            "- Scores, hard gates, and decisions are computed deterministically from verified evidence and cannot be overridden by conversational AI.\n"
            "- Stored audit contracts (raw_data.json, audit.json, evidence.json) are hashed with SHA-256 in manifest.json for tamper detection.\n"
            "- If independent GitHub MCP tools are used for exploration, clearly separate their observations from Shinobi-verified evidence."
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
