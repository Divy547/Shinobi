"""Unit tests for deterministic scoring engine and decision logic."""

from repovet_mcp.models.audit import AuditDecision, HardGateResult, HardGateStatus
from repovet_mcp.services.activity_service import ActivityService
from repovet_mcp.services.ci_security_service import CISecurityService
from repovet_mcp.services.contributor_service import ContributorService
from repovet_mcp.services.documentation_service import DocumentationService
from repovet_mcp.services.hard_gates_service import HardGatesService
from repovet_mcp.services.newcomer_service import NewcomerService
from repovet_mcp.services.responsiveness_service import ResponsivenessService
from repovet_mcp.services.scoring_engine import ScoringEngine
from tests.fixtures.mock_data import create_mock_repository_data


def test_scoring_engine_healthy_repo_approve() -> None:
    """Verify that an active, well-maintained repository receives high score and APPROVE verdict."""
    data = create_mock_repository_data()
    engine = ScoringEngine()

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
    gates, evidence, _ = HardGatesService().evaluate_gates(
        "audit_1", act, ci_sec, data["repository"]
    )

    scorecard, decision, disqualifiers = engine.evaluate_scorecard(
        audit_id="audit_1",
        activity_metrics=act,
        contributor_metrics=contrib,
        responsiveness_metrics=resp,
        newcomer_metrics=newcomer,
        documentation_metrics=doc,
        ci_security_metrics=ci_sec,
        hard_gates=gates,
        evidence_list=evidence,
        raw_repository=data["repository"],
    )

    assert len(scorecard.criteria_scores) == 10
    assert scorecard.max_possible_score == 20
    assert scorecard.total_score >= 16
    assert decision == AuditDecision.APPROVE
    assert len(disqualifiers) == 0


def test_scoring_engine_hard_gate_failure_reject() -> None:
    """Verify that a critical hard gate failure forces REJECT regardless of numerical score."""
    data = create_mock_repository_data()
    engine = ScoringEngine()

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

    # Force a failing critical hard gate (e.g. unlicensed repository)
    failed_gate = HardGateResult(
        gate_id="unlicensed_repository",
        name="Missing Open Source License",
        status=HardGateStatus.FAIL,
        severity="CRITICAL",
        reason="No open-source license detected.",
    )

    scorecard, decision, disqualifiers = engine.evaluate_scorecard(
        audit_id="audit_failed",
        activity_metrics=act,
        contributor_metrics=contrib,
        responsiveness_metrics=resp,
        newcomer_metrics=newcomer,
        documentation_metrics=doc,
        ci_security_metrics=ci_sec,
        hard_gates=[failed_gate],
        evidence_list=[],
        raw_repository=data["repository"],
    )

    assert decision == AuditDecision.REJECT
    assert len(disqualifiers) >= 1
    assert "Missing Open Source License" in disqualifiers[0]


def test_scoring_engine_unknown_gate_manual_review() -> None:
    """Verify that an UNKNOWN hard gate downgrades verdict to NEEDS_MANUAL_REVIEW."""
    data = create_mock_repository_data()
    engine = ScoringEngine()

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

    unknown_gate = HardGateResult(
        gate_id="failing_default_branch",
        name="Default Branch CI Status",
        status=HardGateStatus.UNKNOWN,
        severity="HIGH",
        reason="No CI workflow runs available to verify build health.",
    )

    scorecard, decision, _ = engine.evaluate_scorecard(
        audit_id="audit_unknown",
        activity_metrics=act,
        contributor_metrics=contrib,
        responsiveness_metrics=resp,
        newcomer_metrics=newcomer,
        documentation_metrics=doc,
        ci_security_metrics=ci_sec,
        hard_gates=[unknown_gate],
        evidence_list=[],
        raw_repository=data["repository"],
    )

    assert decision == AuditDecision.NEEDS_MANUAL_REVIEW
