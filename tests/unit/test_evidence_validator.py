"""Unit tests for evidence grounding and confidence validation."""

from pathlib import Path

from repovet_mcp.models.audit import (
    AuditDecision,
    AuditReport,
    AuditTarget,
    CriterionScore,
    Scorecard,
)
from repovet_mcp.models.evidence import (
    EvidenceConfidence,
    EvidenceItem,
    EvidenceSourceType,
)
from repovet_mcp.models.findings import Finding, FindingCategory, FindingSeverity
from repovet_mcp.services.evidence_validator import EvidenceValidator


def test_evidence_validator_valid_report() -> None:
    """Verify that a fully grounded AuditReport passes validation."""
    ev = EvidenceItem(
        id="ev_01",
        phase="phase_1_identity_and_licensing",
        source_type=EvidenceSourceType.GITHUB_API_REST,
        source_endpoint="https://api.github.com/repos/test/repo",
        confidence=EvidenceConfidence.CONFIRMED,
        summary="Repository has valid Apache-2.0 license",
        verified=True,
    )
    finding = Finding(
        id="find_01",
        phase="phase_1_identity_and_licensing",
        category=FindingCategory.LICENSING,
        severity=FindingSeverity.INFO,
        title="Valid License",
        description="Apache-2.0 confirmed.",
        evidence_ids=["ev_01"],
    )
    crit = CriterionScore(
        criterion_id="docs_and_setup",
        name="Documentation & Local Setup Clarity",
        phase="phase_5_documentation_and_onboarding",
        score=2,
        max_score=2,
        rationale="Comprehensive README and CONTRIBUTING present.",
        evidence_ids=["ev_01"],
    )
    target = AuditTarget(
        owner="test",
        repo="repo",
        url="https://github.com/test/repo",
        default_branch="main",
    )
    report = AuditReport(
        audit_id="audit_valid",
        target=target,
        decision=AuditDecision.APPROVE,
        scorecard=Scorecard(criteria_scores=[crit], total_score=2, max_possible_score=20),
        findings=[finding],
        evidence=[ev],
        summary="Audit summary",
    )

    validator = EvidenceValidator()
    results = validator.validate_audit_evidence(report)

    assert results["is_valid"] is True
    assert results["total_evidence_count"] == 1
    assert len(results["unsupported_findings"]) == 0
    assert len(results["unsupported_criteria"]) == 0
    assert results["confidence_counts"]["CONFIRMED"] == 1


def test_evidence_validator_unsupported_finding() -> None:
    """Verify that findings without valid evidence IDs fail validation."""
    finding = Finding(
        id="find_unsupported",
        phase="phase_2_vitality_and_pulse",
        category=FindingCategory.ACTIVITY,
        severity=FindingSeverity.HIGH,
        title="Unverified Claim",
        description="Claim without evidence.",
        evidence_ids=["non_existent_ev_id"],
    )
    target = AuditTarget(
        owner="test",
        repo="repo",
        url="https://github.com/test/repo",
    )
    report = AuditReport(
        audit_id="audit_invalid",
        target=target,
        decision=AuditDecision.CONDITIONAL,
        scorecard=Scorecard(criteria_scores=[], total_score=0, max_possible_score=20),
        findings=[finding],
        evidence=[],
        summary="Audit summary",
    )

    validator = EvidenceValidator()
    results = validator.validate_audit_evidence(report)

    assert results["is_valid"] is False
    assert "find_unsupported" in results["unsupported_findings"]


def test_evidence_validator_full_scorecard_grounding(tmp_path: Path) -> None:
    """Verify that a 10-criterion scorecard with dedicated evidence items validates cleanly."""
    from repovet_mcp.config.settings import Settings
    from repovet_mcp.services.activity_service import ActivityService
    from repovet_mcp.services.ci_security_service import CISecurityService
    from repovet_mcp.services.contributor_service import ContributorService
    from repovet_mcp.services.documentation_service import DocumentationService
    from repovet_mcp.services.hard_gates_service import HardGatesService
    from repovet_mcp.services.newcomer_service import NewcomerService
    from repovet_mcp.services.responsiveness_service import ResponsivenessService
    from repovet_mcp.services.scoring_engine import ScoringEngine
    from repovet_mcp.tools.vetting_tools import VettingToolHandlers
    from tests.fixtures.mock_data import create_mock_repository_data

    settings = Settings(
        data_dir=tmp_path / "data",
        reports_dir=tmp_path / "reports",
        logs_dir=tmp_path / "logs",
        config_dir=Path(__file__).parent.parent.parent / "config",
    )
    data = create_mock_repository_data()
    handlers = VettingToolHandlers(settings)
    audit_id = "test_audit_grounding"
    handlers.storage.save_raw_data(audit_id, data)

    act = ActivityService().analyze_activity(data["repository"], data["commits"], data["releases"])
    contrib = ContributorService().analyze_contributors(data["contributors"])
    resp = ResponsivenessService().analyze_responsiveness(
        data["issues"],
        data["pull_requests"],
        data["sampled_issue_comments"],
        data["sampled_pr_reviews"],
        data["sampled_pr_comments"],
    )
    newcomer = NewcomerService().analyze_newcomers(data["issues"], data["pull_requests"])
    doc = DocumentationService().analyze_documentation(
        data["root_contents"], data["community_profile"], data["repository"]
    )
    ci_sec = CISecurityService().analyze_ci_and_security(
        data["repository"], data["workflows"], data["workflow_runs"], data["root_contents"]
    )
    gates, gate_evidence, gate_findings = HardGatesService().evaluate_gates(
        audit_id, act, ci_sec, data["repository"]
    )

    # Use handlers logic or build full evidence list
    now = data["commits"][0]["commit"]["committer"]["date"]
    from datetime import datetime

    collected_now = datetime.fromisoformat(now)

    evidence_list = list(gate_evidence)
    evidence_list.append(
        EvidenceItem(
            id=f"{audit_id}_ev_c1_gsoc",
            phase="phase_9_mentorship_and_gsoc",
            source_type=EvidenceSourceType.GITHUB_API_REST,
            source_endpoint="https://github.com/test-org/sample-lib/contents",
            collected_at=collected_collected_at
            if (collected_collected_at := collected_now)
            else collected_now,
            confidence=EvidenceConfidence.CONFIRMED,
            summary="GSoC ideas doc verified.",
            verified=True,
        )
    )
    evidence_list.append(
        EvidenceItem(
            id=f"{audit_id}_ev_c2_commits",
            phase="phase_2_vitality_and_pulse",
            source_type=EvidenceSourceType.GITHUB_API_REST,
            source_endpoint="https://github.com/test-org/sample-lib/commits",
            collected_at=collected_now,
            confidence=EvidenceConfidence.CONFIRMED,
            summary="Commits verified.",
            verified=True,
        )
    )
    evidence_list.append(
        EvidenceItem(
            id=f"{audit_id}_ev_c3_contributors",
            phase="phase_3_governance_and_culture",
            source_type=EvidenceSourceType.GITHUB_API_REST,
            source_endpoint="https://github.com/test-org/sample-lib/contributors",
            collected_at=collected_now,
            confidence=EvidenceConfidence.CONFIRMED,
            summary="Contributors verified.",
            verified=True,
        )
    )
    evidence_list.append(
        EvidenceItem(
            id=f"{audit_id}_ev_c4_pr_response",
            phase="phase_4_responsiveness_and_velocity",
            source_type=EvidenceSourceType.GITHUB_API_REST,
            source_endpoint="https://github.com/test-org/sample-lib/pulls",
            collected_at=collected_now,
            confidence=EvidenceConfidence.CONFIRMED,
            summary="PR response verified.",
            verified=True,
        )
    )
    evidence_list.append(
        EvidenceItem(
            id=f"{audit_id}_ev_c5_issue_response",
            phase="phase_4_responsiveness_and_velocity",
            source_type=EvidenceSourceType.GITHUB_API_REST,
            source_endpoint="https://github.com/test-org/sample-lib/issues",
            collected_at=collected_now,
            confidence=EvidenceConfidence.CONFIRMED,
            summary="Issue response verified.",
            verified=True,
        )
    )
    evidence_list.append(
        EvidenceItem(
            id=f"{audit_id}_ev_c6_newcomer_prs",
            phase="phase_6_issue_hygiene_and_accessibility",
            source_type=EvidenceSourceType.GITHUB_API_REST,
            source_endpoint="https://github.com/test-org/sample-lib/pulls",
            collected_at=collected_now,
            confidence=EvidenceConfidence.CONFIRMED,
            summary="Newcomer PRs verified.",
            verified=True,
        )
    )
    evidence_list.append(
        EvidenceItem(
            id=f"{audit_id}_ev_c7_beginner_issues",
            phase="phase_6_issue_hygiene_and_accessibility",
            source_type=EvidenceSourceType.GITHUB_API_REST,
            source_endpoint="https://github.com/test-org/sample-lib/issues",
            collected_at=collected_now,
            confidence=EvidenceConfidence.CONFIRMED,
            summary="Beginner issues verified.",
            verified=True,
        )
    )
    evidence_list.append(
        EvidenceItem(
            id=f"{audit_id}_ev_c8_docs",
            phase="phase_5_documentation_and_onboarding",
            source_type=EvidenceSourceType.GITHUB_API_REST,
            source_endpoint="https://github.com/test-org/sample-lib/blob/main/README.md",
            collected_at=collected_now,
            confidence=EvidenceConfidence.CONFIRMED,
            summary="Docs verified.",
            verified=True,
        )
    )
    evidence_list.append(
        EvidenceItem(
            id=f"{audit_id}_ev_c9_ci",
            phase="phase_7_ci_cd_and_testing",
            source_type=EvidenceSourceType.GITHUB_API_REST,
            source_endpoint="https://github.com/test-org/sample-lib/actions",
            collected_at=collected_now,
            confidence=EvidenceConfidence.CONFIRMED,
            summary="CI verified.",
            verified=True,
        )
    )
    evidence_list.append(
        EvidenceItem(
            id=f"{audit_id}_ev_c10_community",
            phase="phase_3_governance_and_culture",
            source_type=EvidenceSourceType.GITHUB_API_REST,
            source_endpoint="https://github.com/test-org/sample-lib/blob/main/CODE_OF_CONDUCT.md",
            collected_at=collected_now,
            confidence=EvidenceConfidence.CONFIRMED,
            summary="Community verified.",
            verified=True,
        )
    )

    scorecard, decision, _ = ScoringEngine().evaluate_scorecard(
        audit_id=audit_id,
        activity_metrics=act,
        contributor_metrics=contrib,
        responsiveness_metrics=resp,
        newcomer_metrics=newcomer,
        documentation_metrics=doc,
        ci_security_metrics=ci_sec,
        hard_gates=gates,
        evidence_list=evidence_list,
        raw_repository=data["repository"],
    )

    report = AuditReport(
        audit_id=audit_id,
        target=AuditTarget(
            owner="test-org",
            repo="sample-lib",
            url="https://github.com/test-org/sample-lib",
        ),
        decision=decision,
        scorecard=scorecard,
        hard_gates=gates,
        findings=gate_findings,
        evidence=evidence_list,
        summary="Audit summary",
    )

    validation = EvidenceValidator().validate_audit_evidence(report)
    assert validation["is_valid"] is True
    assert len(validation["unsupported_criteria"]) == 0
    assert len(validation["unsupported_findings"]) == 0
    assert validation["total_evidence_count"] >= 14
