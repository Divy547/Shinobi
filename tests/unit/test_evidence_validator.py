"""Unit tests for evidence grounding and confidence validation."""

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
