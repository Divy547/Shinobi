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


def test_scoring_engine_gsoc_without_doc_scores_zero_and_marked_unknown() -> None:
    """Verify that absent GSoC ideas document yields 0 points and UNKNOWN status."""
    data = create_mock_repository_data(has_gsoc_ideas=False)
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

    scorecard, _, _ = engine.evaluate_scorecard(
        audit_id="audit_no_gsoc",
        activity_metrics=act,
        contributor_metrics=contrib,
        responsiveness_metrics=resp,
        newcomer_metrics=newcomer,
        documentation_metrics=doc,
        ci_security_metrics=ci_sec,
        hard_gates=[],
        evidence_list=[],
        raw_repository=data["repository"],
    )

    gsoc_crit = next(c for c in scorecard.criteria_scores if c.criterion_id == "gsoc_history")
    assert gsoc_crit.score == 0
    assert "Missing historical GSoC archive evidence" in gsoc_crit.rationale
    assert "UNKNOWN" in gsoc_crit.rationale
    assert "umbrella foundation" in gsoc_crit.rationale


def test_scoring_engine_newcomer_rationale_includes_sample_and_denominator() -> None:
    """Verify that newcomer PR rationale includes sample size, closed PRs, and evaluated slice."""
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

    scorecard, _, _ = engine.evaluate_scorecard(
        audit_id="audit_newcomer_rat",
        activity_metrics=act,
        contributor_metrics=contrib,
        responsiveness_metrics=resp,
        newcomer_metrics=newcomer,
        documentation_metrics=doc,
        ci_security_metrics=ci_sec,
        hard_gates=[],
        evidence_list=[],
        raw_repository=data["repository"],
    )

    newcomer_crit = next(
        c for c in scorecard.criteria_scores if c.criterion_id == "newcomer_prs_merged"
    )
    assert "merged out of" in newcomer_crit.rationale
    assert "newcomer PRs evaluated in" in newcomer_crit.rationale


def test_scoring_engine_newcomer_denominator_closed_vs_evaluated() -> None:
    """Verify that newcomer PR merge-rate denominator is closed newcomer PRs, with total evaluated visible."""
    # Scenario: 100 recent PRs evaluated.
    # 15 are newcomer PRs: 3 open, 12 closed, 0 merged.
    pull_requests = []
    # 3 open newcomer PRs
    for i in range(1, 4):
        pull_requests.append(
            {
                "number": i,
                "state": "open",
                "user": {"login": f"newbie_{i}", "type": "User"},
                "author_association": "FIRST_TIME_CONTRIBUTOR",
                "merged_at": None,
            }
        )
    # 12 closed newcomer PRs (none merged)
    for i in range(4, 16):
        pull_requests.append(
            {
                "number": i,
                "state": "closed",
                "user": {"login": f"newbie_{i}", "type": "User"},
                "author_association": "NONE",
                "merged_at": None,
            }
        )
    # 85 member PRs to reach 100 total
    for i in range(16, 101):
        pull_requests.append(
            {
                "number": i,
                "state": "closed",
                "user": {"login": f"maintainer_{i}", "type": "User"},
                "author_association": "MEMBER",
                "merged_at": "2026-11-01T00:00:00Z",
            }
        )

    newcomer_service = NewcomerService()
    newcomer_metrics = newcomer_service.analyze_newcomers(issues=[], pull_requests=pull_requests)

    assert newcomer_metrics["newcomer_prs_sample_count"] == 15
    assert newcomer_metrics["newcomer_prs_closed"] == 12
    assert newcomer_metrics["newcomer_prs_merged"] == 0
    assert newcomer_metrics["newcomer_merge_rate"] == 0.0

    engine = ScoringEngine()
    # Test production input contract: raw_repository is repo_meta (no "pull_requests" key)
    repo_meta = {
        "name": "pipelines",
        "owner": {"login": "kubeflow"},
        "html_url": "https://github.com/kubeflow/pipelines",
        "default_branch": "master",
    }
    responsiveness_metrics = {
        "total_prs_evaluated": len(pull_requests),
        "prs_with_human_response_count": 0,
    }

    scorecard, _, _ = engine.evaluate_scorecard(
        audit_id="audit_denominator_check",
        activity_metrics={},
        contributor_metrics={},
        responsiveness_metrics=responsiveness_metrics,
        newcomer_metrics=newcomer_metrics,
        documentation_metrics={},
        ci_security_metrics={},
        hard_gates=[],
        evidence_list=[],
        raw_repository=repo_meta,
    )

    newcomer_crit = next(
        c for c in scorecard.criteria_scores if c.criterion_id == "newcomer_prs_merged"
    )
    expected_rationale = "Zero newcomer PRs merged out of 12 closed newcomer PRs (15 evaluated in the 100 most recent PRs)."
    assert newcomer_crit.rationale == expected_rationale


def test_scoring_engine_newcomer_sample_window_from_actual_input_contract() -> None:
    """Verify scorecard correctly reports sample-window count when raw_repository has no pull_requests."""
    pull_requests = [
        {
            "number": 1,
            "state": "closed",
            "author_association": "NONE",
            "merged_at": None,
            "user": {"login": "u1"},
        }
    ] + [
        {
            "number": i,
            "state": "closed",
            "author_association": "MEMBER",
            "merged_at": "2026-11-01T00:00:00Z",
            "user": {"login": f"m{i}"},
        }
        for i in range(2, 51)
    ]
    # 50 PRs evaluated, 1 newcomer closed PR (0 merged)
    newcomer_service = NewcomerService()
    newcomer_metrics = newcomer_service.analyze_newcomers(issues=[], pull_requests=pull_requests)
    assert newcomer_metrics["total_prs_evaluated"] == 50

    # Pass repo_meta without pull_requests
    repo_meta = {"name": "test-repo", "owner": {"login": "org"}}
    resp_metrics = {"total_prs_evaluated": 50}

    engine = ScoringEngine()
    scorecard, _, _ = engine.evaluate_scorecard(
        audit_id="audit_contract_check",
        activity_metrics={},
        contributor_metrics={},
        responsiveness_metrics=resp_metrics,
        newcomer_metrics=newcomer_metrics,
        documentation_metrics={},
        ci_security_metrics={},
        hard_gates=[],
        evidence_list=[],
        raw_repository=repo_meta,
    )

    newcomer_crit = next(
        c for c in scorecard.criteria_scores if c.criterion_id == "newcomer_prs_merged"
    )
    assert "1 evaluated in the 50 most recent PRs" in newcomer_crit.rationale
    assert " 0 most recent PRs" not in newcomer_crit.rationale


def test_scoring_engine_community_capped_at_one_without_verified_chat() -> None:
    """Verify that discussions/chat cannot score 2 points without verified interaction activity."""
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

    scorecard, _, _ = engine.evaluate_scorecard(
        audit_id="audit_comm",
        activity_metrics=act,
        contributor_metrics=contrib,
        responsiveness_metrics=resp,
        newcomer_metrics=newcomer,
        documentation_metrics=doc,
        ci_security_metrics=ci_sec,
        hard_gates=[],
        evidence_list=[],
        raw_repository=data["repository"],
    )

    comm_crit = next(
        c for c in scorecard.criteria_scores if c.criterion_id == "community_tone_and_chat"
    )
    assert comm_crit.score == 1
    assert "unverified" in comm_crit.rationale.lower()
