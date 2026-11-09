"""MCP tool handlers exposing repository vetting, scoring, and PDF generation."""

import logging
from datetime import UTC, datetime
from typing import Any

try:
    from mcp.server import MCPServer
except ImportError:
    from mcp.server.fastmcp import FastMCP as MCPServer  # type: ignore[no-redef]

try:
    from mcp.server.mcpserver.exceptions import ToolError
except ImportError:
    try:
        from mcp.server.fastmcp.exceptions import ToolError  # type: ignore[no-redef]
    except ImportError:

        class ToolError(Exception):  # type: ignore[no-redef]
            pass


from repovet_mcp.config.settings import Settings, get_settings
from repovet_mcp.models.audit import AuditReport, AuditTarget
from repovet_mcp.models.evidence import EvidenceConfidence, EvidenceItem, EvidenceSourceType
from repovet_mcp.reporting.pdf_generator import PDFReportGenerator
from repovet_mcp.services.activity_service import ActivityService
from repovet_mcp.services.ci_security_service import CISecurityService
from repovet_mcp.services.contributor_service import ContributorService
from repovet_mcp.services.documentation_service import DocumentationService
from repovet_mcp.services.evidence_validator import EvidenceValidator
from repovet_mcp.services.github_client import GitHubClient, parse_repository_target
from repovet_mcp.services.hard_gates_service import HardGatesService
from repovet_mcp.services.newcomer_service import NewcomerService
from repovet_mcp.services.responsiveness_service import ResponsivenessService
from repovet_mcp.services.scoring_engine import ScoringEngine
from repovet_mcp.services.security import redact_secrets, validate_audit_id
from repovet_mcp.services.storage_service import StorageService

logger = logging.getLogger("repovet_mcp.tools")


class VettingToolHandlers:
    """Encapsulates business operations for the 7 RepoVet MCP tools."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.storage = StorageService(self.settings)
        self.activity_service = ActivityService()
        self.contributor_service = ContributorService()
        self.responsiveness_service = ResponsivenessService()
        self.newcomer_service = NewcomerService()
        self.documentation_service = DocumentationService()
        self.ci_security_service = CISecurityService()
        self.hard_gates_service = HardGatesService()
        self.scoring_engine = ScoringEngine(self.settings)
        self.evidence_validator = EvidenceValidator()
        self.pdf_generator = PDFReportGenerator(self.settings)

    def _get_github_client(self) -> GitHubClient:
        token = (
            self.settings.github_token.get_secret_value() if self.settings.github_token else None
        )
        return GitHubClient(token=token, base_url=self.settings.github_api_url)

    async def analyze_repository(self, target: str, audit_id: str | None = None) -> dict[str, Any]:
        """Fetch repository data, initialize audit record, and cache raw payloads."""
        owner, repo = parse_repository_target(target)
        assigned_id = (
            validate_audit_id(audit_id)
            if audit_id
            else f"audit_{owner}_{repo}_{int(datetime.now(UTC).timestamp())}"
        )

        client = self._get_github_client()
        raw_data = await client.collect_repository_data(owner, repo)
        self.storage.save_raw_data(assigned_id, raw_data)

        repo_meta = raw_data.get("repository", {})
        return {
            "audit_id": assigned_id,
            "owner": owner,
            "repo": repo,
            "url": repo_meta.get("html_url"),
            "default_branch": repo_meta.get("default_branch", "main"),
            "description": repo_meta.get("description"),
            "stars": repo_meta.get("stargazers_count", 0),
            "forks": repo_meta.get("forks_count", 0),
            "open_issues": repo_meta.get("open_issues_count", 0),
            "license_spdx": (repo_meta.get("license") or {}).get("spdx_id"),
            "status": "INITIALIZED",
            "message": f"Repository data collected for {owner}/{repo}. Audit ID: {assigned_id}",
        }

    async def check_hard_gates(self, audit_id: str) -> dict[str, Any]:
        """Evaluate mandatory eligibility gates (license, activity, safety, build)."""
        valid_audit_id = validate_audit_id(audit_id)
        raw_data = self.storage.load_raw_data(valid_audit_id)
        repo_meta = raw_data.get("repository", {})
        commits = raw_data.get("commits", [])
        releases = raw_data.get("releases", [])
        workflows = raw_data.get("workflows", [])
        workflow_runs = raw_data.get("workflow_runs", [])
        root_contents = raw_data.get("root_contents", [])
        collection_errors = raw_data.get("errors", {})
        commits_failed = "commits" in collection_errors

        activity_metrics = self.activity_service.analyze_activity(
            repo_meta, commits, releases, commits_collection_failed=commits_failed
        )
        ci_security_metrics = self.ci_security_service.analyze_ci_and_security(
            repo_meta, workflows, workflow_runs, root_contents
        )

        gates, evidence, findings = self.hard_gates_service.evaluate_gates(
            valid_audit_id, activity_metrics, ci_security_metrics, repo_meta
        )

        return {
            "audit_id": valid_audit_id,
            "hard_gates": [gate.model_dump() for gate in gates],
            "critical_blockers_count": sum(
                1 for g in gates if g.status == "FAIL" and g.severity == "CRITICAL"
            ),
            "all_gates_passed": all(g.status == "PASS" for g in gates),
        }

    async def calculate_responsiveness(self, audit_id: str) -> dict[str, Any]:
        """Calculate first human response times and triage rates distinguishing bots."""
        valid_audit_id = validate_audit_id(audit_id)
        raw_data = self.storage.load_raw_data(valid_audit_id)
        issues = raw_data.get("issues", [])
        pulls = raw_data.get("pull_requests", [])
        issue_comments = raw_data.get("sampled_issue_comments", {})
        pr_reviews = raw_data.get("sampled_pr_reviews", {})
        pr_comments = raw_data.get("sampled_pr_comments", {})

        metrics = self.responsiveness_service.analyze_responsiveness(
            issues=issues,
            pull_requests=pulls,
            sampled_issue_comments=issue_comments,
            sampled_pr_reviews=pr_reviews,
            sampled_pr_comments=pr_comments,
        )

        return {
            "audit_id": valid_audit_id,
            "responsiveness_metrics": metrics,
        }

    async def analyze_contribution_accessibility(self, audit_id: str) -> dict[str, Any]:
        """Evaluate documentation clarity, beginner issues, and newcomer accessibility."""
        valid_audit_id = validate_audit_id(audit_id)
        raw_data = self.storage.load_raw_data(valid_audit_id)
        repo_meta = raw_data.get("repository", {})
        root_contents = raw_data.get("root_contents", [])
        community_profile = raw_data.get("community_profile", {})
        issues = raw_data.get("issues", [])
        pulls = raw_data.get("pull_requests", [])

        targeted_contents = raw_data.get("targeted_contents") or raw_data.get("nested_contents", {})
        doc_metrics = self.documentation_service.analyze_documentation(
            root_contents, community_profile, repo_meta, nested_contents=targeted_contents
        )
        newcomer_metrics = self.newcomer_service.analyze_newcomers(issues, pulls)

        return {
            "audit_id": valid_audit_id,
            "documentation": doc_metrics,
            "newcomer_accessibility": newcomer_metrics,
        }

    async def calculate_scorecard(self, audit_id: str) -> dict[str, Any]:
        """Calculate 10-criterion scorecard and final verdict, persisting the report."""
        valid_audit_id = validate_audit_id(audit_id)
        raw_data = self.storage.load_raw_data(valid_audit_id)
        repo_meta = raw_data.get("repository", {})
        commits = raw_data.get("commits", [])
        contributors = raw_data.get("contributors", [])
        issues = raw_data.get("issues", [])
        pulls = raw_data.get("pull_requests", [])
        releases = raw_data.get("releases", [])
        workflows = raw_data.get("workflows", [])
        workflow_runs = raw_data.get("workflow_runs", [])
        root_contents = raw_data.get("root_contents", [])
        community_profile = raw_data.get("community_profile", {})
        issue_comments = raw_data.get("sampled_issue_comments", {})
        pr_reviews = raw_data.get("sampled_pr_reviews", {})
        pr_comments = raw_data.get("sampled_pr_comments", {})

        collection_errors = raw_data.get("errors", {})
        commits_failed = "commits" in collection_errors

        # Compute analytics
        act_metrics = self.activity_service.analyze_activity(
            repo_meta, commits, releases, commits_collection_failed=commits_failed
        )
        contrib_metrics = self.contributor_service.analyze_contributors(contributors)
        resp_metrics = self.responsiveness_service.analyze_responsiveness(
            issues, pulls, issue_comments, pr_reviews, pr_comments
        )
        newcomer_metrics = self.newcomer_service.analyze_newcomers(issues, pulls)
        targeted_contents = raw_data.get("targeted_contents") or raw_data.get("nested_contents", {})
        doc_metrics = self.documentation_service.analyze_documentation(
            root_contents, community_profile, repo_meta, nested_contents=targeted_contents
        )
        ci_sec_metrics = self.ci_security_service.analyze_ci_and_security(
            repo_meta, workflows, workflow_runs, root_contents
        )

        # Evaluate Hard Gates
        gates, gate_evidence, gate_findings = self.hard_gates_service.evaluate_gates(
            valid_audit_id, act_metrics, ci_sec_metrics, repo_meta
        )

        # Build grounded evidence items across all 10 scorecard criteria
        now = datetime.now(UTC)
        repo_url = repo_meta.get("html_url", "")
        evidence_list: list[EvidenceItem] = list(gate_evidence)

        # Criterion 1 Evidence (Phase 9: GSoC History & Mentorship Track Record)
        has_gsoc_doc = doc_metrics.get("has_gsoc_doc", False)
        gsoc_doc_path = doc_metrics.get("gsoc_doc_path")
        gsoc_endpoint = (
            f"{repo_url}/contents/{gsoc_doc_path}" if gsoc_doc_path else f"{repo_url}/contents"
        )
        c1_summary = (
            f"Dedicated GSoC / project ideas document verified in repository contents ({gsoc_doc_path})."
            if has_gsoc_doc and gsoc_doc_path
            else (
                "Dedicated GSoC / project ideas document verified in repository contents."
                if has_gsoc_doc
                else (
                    "No dedicated GSoC ideas document in repository contents. GSoC status is UNKNOWN "
                    "(repository-level absence does not preclude participation under an umbrella organization/foundation archives)."
                )
            )
        )
        evidence_list.append(
            EvidenceItem(
                id=f"{audit_id}_ev_c1_gsoc",
                phase="phase_9_mentorship_and_gsoc",
                source_type=EvidenceSourceType.GITHUB_API_REST,
                source_endpoint=gsoc_endpoint,
                collected_at=now,
                confidence=EvidenceConfidence.CONFIRMED
                if has_gsoc_doc
                else EvidenceConfidence.UNKNOWN,
                summary=c1_summary,
                verified=has_gsoc_doc,
            )
        )

        # Criterion 2 Evidence (Phase 2: Commit Activity & Cadence)
        commit_hist_ok = act_metrics.get("commit_history_available", True)
        evidence_list.append(
            EvidenceItem(
                id=f"{audit_id}_ev_c2_commits",
                phase="phase_2_vitality_and_pulse",
                source_type=EvidenceSourceType.GITHUB_API_REST,
                source_endpoint=f"{repo_url}/commits",
                collected_at=now,
                confidence=EvidenceConfidence.CONFIRMED
                if commit_hist_ok
                else EvidenceConfidence.UNKNOWN,
                summary=(
                    f"Latest commit: {act_metrics.get('days_since_latest_commit')} days ago. Last 90d commits: {act_metrics.get('commits_last_90d')}."
                    if commit_hist_ok
                    else "Commit history could not be retrieved due to API collection error."
                ),
                verified=commit_hist_ok,
            )
        )

        # Criterion 3 Evidence (Phase 3: Contributor Spread & Decentralization)
        evidence_list.append(
            EvidenceItem(
                id=f"{audit_id}_ev_c3_contributors",
                phase="phase_3_governance_and_culture",
                source_type=EvidenceSourceType.GITHUB_API_REST,
                source_endpoint=f"{repo_url}/contributors",
                collected_at=now,
                confidence=EvidenceConfidence.CONFIRMED,
                summary=f"Total contributors: {contrib_metrics.get('total_contributors')}. Top contributor share: {contrib_metrics.get('top_contributor_share')}%.",
                verified=True,
            )
        )

        # Criterion 4 Evidence (Phase 4: PR First Human Response Time)
        prs_with_human = resp_metrics.get("prs_with_human_response_count", 0)
        median_pr_hours = resp_metrics.get("median_pr_first_response_hours")
        if prs_with_human > 0 and median_pr_hours is not None:
            c4_summary = f"PR median first human response: {median_pr_hours} hours across {prs_with_human} evaluated reviews."
        else:
            c4_summary = f"PR median first human response: unobserved (no human responses observed across {prs_with_human} evaluated PR reviews/comments)."

        evidence_list.append(
            EvidenceItem(
                id=f"{audit_id}_ev_c4_pr_response",
                phase="phase_4_responsiveness_and_velocity",
                source_type=EvidenceSourceType.GITHUB_API_REST,
                source_endpoint=f"{repo_url}/pulls",
                collected_at=now,
                confidence=EvidenceConfidence.CONFIRMED,
                summary=c4_summary,
                verified=True,
            )
        )

        # Criterion 5 Evidence (Phase 4: Issue Human Response Rate)
        evidence_list.append(
            EvidenceItem(
                id=f"{audit_id}_ev_c5_issue_response",
                phase="phase_4_responsiveness_and_velocity",
                source_type=EvidenceSourceType.GITHUB_API_REST,
                source_endpoint=f"{repo_url}/issues",
                collected_at=now,
                confidence=EvidenceConfidence.CONFIRMED,
                summary=f"Open issues evaluated: {resp_metrics.get('open_issues_evaluated')}. Unanswered issue percentage: {resp_metrics.get('unanswered_issue_percentage')}%.",
                verified=True,
            )
        )

        # Criterion 6 Evidence (Phase 6: Newcomer PRs Acceptance & Merge Rate)
        newcomer_sample = newcomer_metrics.get("newcomer_prs_sample_count", 0)
        newcomer_closed = newcomer_metrics.get("newcomer_prs_closed", 0)
        newcomer_merged = newcomer_metrics.get("newcomer_prs_merged", 0)
        newcomer_rate = newcomer_metrics.get("newcomer_merge_rate", 0.0)
        total_prs = len(raw_data.get("pull_requests", []))
        evidence_list.append(
            EvidenceItem(
                id=f"{audit_id}_ev_c6_newcomer_prs",
                phase="phase_6_issue_hygiene_and_accessibility",
                source_type=EvidenceSourceType.GITHUB_API_REST,
                source_endpoint=f"{repo_url}/pulls",
                collected_at=now,
                confidence=EvidenceConfidence.CONFIRMED,
                summary=(
                    f"Newcomer PRs: {newcomer_merged} merged out of {newcomer_closed} closed newcomer PRs "
                    f"({newcomer_rate}% merge rate across {newcomer_sample} newcomer PRs identified in {total_prs} recent PRs)."
                ),
                verified=True,
            )
        )

        # Criterion 7 Evidence (Phase 6: Beginner Issues & Newcomer Hygiene)
        evidence_list.append(
            EvidenceItem(
                id=f"{audit_id}_ev_c7_beginner_issues",
                phase="phase_6_issue_hygiene_and_accessibility",
                source_type=EvidenceSourceType.GITHUB_API_REST,
                source_endpoint=f"{repo_url}/issues",
                collected_at=now,
                confidence=EvidenceConfidence.CONFIRMED,
                summary=f"Open beginner-labeled issues count: {newcomer_metrics.get('open_beginner_issues_count')}.",
                verified=True,
            )
        )

        # Criterion 8 Evidence (Phase 5: Documentation & Local Setup Clarity)
        evidence_list.append(
            EvidenceItem(
                id=f"{audit_id}_ev_c8_docs",
                phase="phase_5_documentation_and_onboarding",
                source_type=EvidenceSourceType.GITHUB_API_REST,
                source_endpoint=f"{repo_url}/blob/main/README.md",
                collected_at=now,
                confidence=EvidenceConfidence.CONFIRMED,
                summary=f"README present: {doc_metrics.get('has_readme')} ({doc_metrics.get('readme_size_bytes')} bytes). CONTRIBUTING guide: {doc_metrics.get('has_contributing')}.",
                verified=True,
            )
        )

        # Criterion 9 Evidence (Phase 7: CI Workflows & Automated Testing)
        evidence_list.append(
            EvidenceItem(
                id=f"{audit_id}_ev_c9_ci",
                phase="phase_7_ci_cd_and_testing",
                source_type=EvidenceSourceType.GITHUB_API_REST,
                source_endpoint=f"{repo_url}/actions",
                collected_at=now,
                confidence=EvidenceConfidence.CONFIRMED,
                summary=f"CI Workflows configured: {ci_sec_metrics.get('has_ci_workflows')}. Default branch passing: {ci_sec_metrics.get('ci_passing_on_default_branch')}. Tests directory: {ci_sec_metrics.get('has_tests_directory')}.",
                verified=True,
            )
        )

        # Criterion 10 Evidence (Phase 3: Community Tone & Discussion Channels)
        has_coc = doc_metrics.get("has_code_of_conduct", False)
        evidence_list.append(
            EvidenceItem(
                id=f"{audit_id}_ev_c10_community",
                phase="phase_3_governance_and_culture",
                source_type=EvidenceSourceType.GITHUB_API_REST,
                source_endpoint=f"{repo_url}/blob/main/CODE_OF_CONDUCT.md" if has_coc else repo_url,
                collected_at=now,
                confidence=EvidenceConfidence.CONFIRMED if has_coc else EvidenceConfidence.UNKNOWN,
                summary=(
                    f"Code of Conduct present: {has_coc}. Discussions enabled: {doc_metrics.get('has_discussions_enabled')}. Note: Community chat/Discussions activity unverified via REST API."
                ),
                verified=has_coc,
            )
        )

        # Evaluate Scorecard & Final Decision
        scorecard, decision, disqualifiers = self.scoring_engine.evaluate_scorecard(
            audit_id=audit_id,
            activity_metrics=act_metrics,
            contributor_metrics=contrib_metrics,
            responsiveness_metrics=resp_metrics,
            newcomer_metrics=newcomer_metrics,
            documentation_metrics=doc_metrics,
            ci_security_metrics=ci_sec_metrics,
            hard_gates=gates,
            evidence_list=evidence_list,
            raw_repository=repo_meta,
        )

        target_model = AuditTarget(
            owner=repo_meta.get("owner", {}).get("login", ""),
            repo=repo_meta.get("name", ""),
            url=repo_url,
            default_branch=repo_meta.get("default_branch", "main"),
            description=repo_meta.get("description"),
            stars=repo_meta.get("stargazers_count", 0),
            forks=repo_meta.get("forks_count", 0),
            open_issues=repo_meta.get("open_issues_count", 0),
            license_spdx=ci_sec_metrics.get("license_spdx"),
        )

        report = AuditReport(
            audit_id=valid_audit_id,
            target=target_model,
            decision=decision,
            scorecard=scorecard,
            hard_gates=gates,
            findings=gate_findings,
            evidence=evidence_list,
            summary=f"Repository audit completed with decision {decision.value} ({scorecard.total_score}/20 points).",
            disqualifiers_triggered=disqualifiers,
            responsiveness_stats=resp_metrics,
            activity_stats=act_metrics,
            accessibility_stats=newcomer_metrics,
        )

        self.storage.save_audit_report(report)
        self.storage.save_evidence(valid_audit_id, evidence_list)
        self.storage.create_audit_manifest(valid_audit_id, overwrite=True)

        return {
            "audit_id": valid_audit_id,
            "target": target_model.model_dump(),
            "decision": decision.value,
            "total_score": scorecard.total_score,
            "max_possible_score": scorecard.max_possible_score,
            "percentage": scorecard.percentage,
            "criteria_scores": [c.model_dump() for c in scorecard.criteria_scores],
            "disqualifiers_triggered": disqualifiers,
            "hard_gates": [g.model_dump() for g in gates],
        }

    async def validate_evidence(self, audit_id: str) -> dict[str, Any]:
        """Validate evidence grounding, citations, and confidence classifications."""
        valid_audit_id = validate_audit_id(audit_id)
        report = self.storage.load_audit_report(valid_audit_id)
        if not report:
            # If scorecard not yet calculated, calculate it now
            await self.calculate_scorecard(valid_audit_id)
            report = self.storage.load_audit_report(valid_audit_id)

        if not report:
            msg = f"Unable to load or compute audit report for {valid_audit_id}"
            raise ValueError(msg)

        validation = self.evidence_validator.validate_audit_evidence(report)
        return {
            "audit_id": valid_audit_id,
            "validation_results": validation,
        }

    async def generate_pdf_report(self, audit_id: str) -> dict[str, Any]:
        """Generate executive multi-section PDF audit report in reports/generated/."""
        valid_audit_id = validate_audit_id(audit_id)
        report = self.storage.load_audit_report(valid_audit_id)
        if not report:
            await self.calculate_scorecard(valid_audit_id)
            report = self.storage.load_audit_report(valid_audit_id)

        if not report:
            msg = f"Unable to locate audit report for {valid_audit_id}"
            raise ValueError(msg)

        pdf_path = self.pdf_generator.generate_report(report)
        return {
            "audit_id": valid_audit_id,
            "report_path": str(pdf_path),
            "file_name": pdf_path.name,
            "file_size_bytes": pdf_path.stat().st_size,
            "status": "SUCCESS",
            "message": f"Audit report PDF generated at: {pdf_path}",
        }


def register_vetting_tools(
    server: MCPServer, settings: Settings | None = None
) -> VettingToolHandlers:
    """Register all seven RepoVet MCP tools onto the server instance."""
    handlers = VettingToolHandlers(settings)

    async def _safe_execute(tool_name: str, coro: Any) -> Any:
        try:
            return await coro
        except ToolError:
            raise
        except Exception as exc:
            msg = redact_secrets(str(exc))
            logger.error("Tool '%s' execution failed: %s", tool_name, msg)
            raise ToolError(msg) from None

    @server.tool(
        name="analyze_repository",
        description=(
            "Mandatory first step for repository vetting. Ingests verified GitHub REST primary evidence "
            "(metadata, commits, PRs, issues, community profile, workflows) into local snapshot storage "
            "and returns an audit_id required for all downstream analysis."
        ),
    )
    async def analyze_repository(target: str, audit_id: str | None = None) -> dict[str, Any]:
        """Initialize an audit and collect repository primary data from GitHub REST API.

        Args:
            target: Repository identifier in 'owner/repo' format or full GitHub URL.
            audit_id: Optional custom audit identifier (alphanumeric, dashes, underscores).
                If omitted, an ID in the format 'audit_{owner}_{repo}_{timestamp}' is generated.

        Returns:
            Dictionary containing assigned audit_id, repository metadata, star/fork counts, and status.
        """
        return await _safe_execute(
            "analyze_repository", handlers.analyze_repository(target, audit_id)
        )

    @server.tool(
        name="check_hard_gates",
        description=(
            "Evaluate mandatory eligibility gates (OSI-approved license, dormancy/recent commits, "
            "default branch CI pass/fail, and root directory binary checks). Returns pass/fail status and critical blockers."
        ),
    )
    async def check_hard_gates(audit_id: str) -> dict[str, Any]:
        """Evaluate mandatory repository eligibility conditions.

        Args:
            audit_id: Identifier of an existing initialized repository audit.

        Returns:
            Dictionary containing gate evaluations, critical blockers count, and overall pass/fail boolean.
        """
        return await _safe_execute("check_hard_gates", handlers.check_hard_gates(audit_id))

    @server.tool(
        name="calculate_responsiveness",
        description=(
            "Calculate first human response times and triage velocity for PRs and issues. "
            "Filters out automated bot comments and reviews to measure real maintainer engagement."
        ),
    )
    async def calculate_responsiveness(audit_id: str) -> dict[str, Any]:
        """Calculate maintainer responsiveness metrics with bot filtering.

        Args:
            audit_id: Identifier of an existing initialized repository audit.

        Returns:
            Dictionary containing PR median response hours, issue response rates, and bot filtering statistics.
        """
        return await _safe_execute(
            "calculate_responsiveness", handlers.calculate_responsiveness(audit_id)
        )

    @server.tool(
        name="analyze_contribution_accessibility",
        description=(
            "Evaluate onboarding documentation (README, CONTRIBUTING, Code of Conduct) and newcomer accessibility "
            "(good-first-issue labeling, newcomer PR merge rates, and issue hygiene)."
        ),
    )
    async def analyze_contribution_accessibility(audit_id: str) -> dict[str, Any]:
        """Evaluate onboarding clarity and newcomer accessibility.

        Args:
            audit_id: Identifier of an existing initialized repository audit.

        Returns:
            Dictionary containing documentation assessment and newcomer PR / issue metrics.
        """
        return await _safe_execute(
            "analyze_contribution_accessibility",
            handlers.analyze_contribution_accessibility(audit_id),
        )

    @server.tool(
        name="calculate_scorecard",
        description=(
            "Execute the deterministic scoring engine across all 10 rubric criteria (0-2 scale, 20 max points). "
            "Determines the immutable verdict (APPROVE, FLAG, REJECT) and persists the audit report and manifest."
        ),
    )
    async def calculate_scorecard(audit_id: str) -> dict[str, Any]:
        """Compute 10-criterion scorecard and immutable audit decision.

        Args:
            audit_id: Identifier of an existing initialized repository audit.

        Returns:
            Dictionary containing total score, percentage, verdict (APPROVE/FLAG/REJECT), and per-criterion scores.
        """
        return await _safe_execute("calculate_scorecard", handlers.calculate_scorecard(audit_id))

    @server.tool(
        name="validate_evidence",
        description=(
            "Verify evidence grounding and citations across all criteria. Ensures every finding is grounded "
            "in primary GitHub data with explicit CONFIRMED/INFERRED/UNKNOWN confidence ratings."
        ),
    )
    async def validate_evidence(audit_id: str) -> dict[str, Any]:
        """Validate evidence grounding, citations, and confidence classifications.

        Args:
            audit_id: Identifier of an existing initialized repository audit.

        Returns:
            Dictionary containing validation results, verified citation percentages, and confidence breakdowns.
        """
        return await _safe_execute("validate_evidence", handlers.validate_evidence(audit_id))

    @server.tool(
        name="generate_pdf_report",
        description=(
            "Generate an executive multi-section PDF audit report in reports/generated/ "
            "with verdict, scorecard, hard gates, and full evidence appendix. "
            "Note: The compiled PDF report is generated in reports/generated/ and is outside the data/ SHA-256 integrity manifest."
        ),
    )
    async def generate_pdf_report(audit_id: str) -> dict[str, Any]:
        """Generate an executive PDF audit report.

        Args:
            audit_id: Identifier of an existing initialized repository audit.

        Returns:
            Dictionary containing generated PDF file path, file size in bytes, and generation status.
        """
        return await _safe_execute("generate_pdf_report", handlers.generate_pdf_report(audit_id))

    return handlers
