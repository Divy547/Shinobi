"""Unit tests for the modular analytics services and hard gates evaluator."""

from datetime import UTC, datetime

from repovet_mcp.models.audit import HardGateStatus
from repovet_mcp.services.activity_service import ActivityService
from repovet_mcp.services.ci_security_service import CISecurityService
from repovet_mcp.services.contributor_service import ContributorService
from repovet_mcp.services.documentation_service import DocumentationService
from repovet_mcp.services.hard_gates_service import HardGatesService
from repovet_mcp.services.newcomer_service import NewcomerService
from repovet_mcp.services.responsiveness_service import ResponsivenessService
from tests.fixtures.mock_data import create_mock_repository_data


def test_activity_service() -> None:
    """Verify commit recency, frequency buckets, and release cadence."""
    data = create_mock_repository_data(days_since_latest_commit=2)
    service = ActivityService()
    now = datetime.now(UTC)

    metrics = service.analyze_activity(
        data["repository"], data["commits"], data["releases"], now=now
    )

    assert metrics["is_archived"] is False
    assert metrics["is_dormant"] is False
    assert metrics["days_since_latest_commit"] == 2
    assert metrics["commits_last_30d"] == 2
    assert metrics["commits_last_90d"] == 2
    assert metrics["commits_last_365d"] == 3
    assert metrics["total_releases"] == 2
    assert metrics["latest_release_tag"] == "v1.2.0"


def test_contributor_service() -> None:
    """Verify contributor diversity, top contributor share, and bus factor assessment."""
    data = create_mock_repository_data()
    service = ContributorService()

    metrics = service.analyze_contributors(data["contributors"])

    assert metrics["total_contributors"] == 5
    assert metrics["top_contributor_login"] == "alice"
    assert metrics["top_contributor_contributions"] == 45
    # Total = 45+30+25+15+10 = 125 -> Alice is 36%
    assert metrics["top_contributor_share"] == 36.0
    assert metrics["bus_factor_risk"] == "LOW"
    assert metrics["is_decentralized"] is True


def test_responsiveness_service_bot_filtering() -> None:
    """Verify bot comments are accurately distinguished from human interactions."""
    service = ResponsivenessService()

    assert service.is_bot_user({"login": "dependabot[bot]", "type": "Bot"}) is True
    assert service.is_bot_user({"login": "github-actions", "type": "User"}) is True
    assert service.is_bot_user({"login": "alice", "type": "User"}) is False
    assert service.is_bot_user(None) is False


def test_responsiveness_service_metrics() -> None:
    """Verify PR first human response time, merge velocity, and issue triage rate."""
    data = create_mock_repository_data()
    service = ResponsivenessService()

    metrics = service.analyze_responsiveness(
        issues=data["issues"],
        pull_requests=data["pull_requests"],
        sampled_issue_comments=data["sampled_issue_comments"],
        sampled_pr_reviews=data["sampled_pr_reviews"],
        sampled_pr_comments=data["sampled_pr_comments"],
    )

    assert metrics["total_prs_evaluated"] == 2
    assert metrics["median_pr_first_response_hours"] is not None
    # Bob commented at 12 hours, review submitted at 18 hours -> first human is Bob at 12 hours
    assert metrics["median_pr_first_response_hours"] == 12.0
    assert metrics["human_comments_count"] >= 2
    assert metrics["bot_comments_count"] >= 1
    assert metrics["pr_merge_rate"] == 100.0  # 1 closed PR which was merged


def test_newcomer_service() -> None:
    """Verify newcomer PR acceptance rate and beginner-labeled issues detection."""
    data = create_mock_repository_data()
    service = NewcomerService()

    metrics = service.analyze_newcomers(data["issues"], data["pull_requests"])

    assert metrics["total_prs_evaluated"] == len(data["pull_requests"])
    assert metrics["newcomer_prs_sample_count"] == 1
    assert metrics["newcomer_prs_merged"] == 1
    assert metrics["newcomer_merge_rate"] == 100.0
    assert metrics["open_beginner_issues_count"] == 3  # Issues 201, 202, 203
    assert len(metrics["open_beginner_issues"]) == 3


def test_documentation_service() -> None:
    """Verify detection of README, CONTRIBUTING, Code of Conduct, and templates."""
    data = create_mock_repository_data()
    service = DocumentationService()

    metrics = service.analyze_documentation(
        data["root_contents"], data["community_profile"], data["repository"]
    )

    assert metrics["has_readme"] is True
    assert metrics["readme_size_bytes"] == 3400
    assert metrics["has_contributing"] is True
    assert metrics["has_code_of_conduct"] is True
    assert metrics["has_security_policy"] is True
    assert metrics["has_license_file"] is True
    assert metrics["has_pr_template"] is True
    assert metrics["has_issue_template"] is True
    assert metrics["has_discussions_enabled"] is True


def test_ci_security_service() -> None:
    """Verify OSI license validation, test directory presence, and CI passing status."""
    data = create_mock_repository_data(license_spdx="Apache-2.0", has_ci_failing=False)
    service = CISecurityService()

    metrics = service.analyze_ci_and_security(
        data["repository"], data["workflows"], data["workflow_runs"], data["root_contents"]
    )

    assert metrics["license_spdx"] == "Apache-2.0"
    assert metrics["is_osi_approved"] is True
    assert metrics["has_tests_directory"] is True
    assert metrics["has_ci_workflows"] is True
    assert metrics["ci_passing_on_default_branch"] is True
    assert metrics["suspicious_install_scripts"] is False


def test_hard_gates_service_pass() -> None:
    """Verify hard gates pass on healthy repository."""
    data = create_mock_repository_data()
    act = ActivityService().analyze_activity(data["repository"], data["commits"], data["releases"])
    ci_sec = CISecurityService().analyze_ci_and_security(
        data["repository"], data["workflows"], data["workflow_runs"], data["root_contents"]
    )

    service = HardGatesService()
    gates, evidence, findings = service.evaluate_gates(
        "test_audit", act, ci_sec, data["repository"]
    )

    assert len(gates) == 4
    assert all(g.status == HardGateStatus.PASS for g in gates)
    assert len(findings) == 0
    assert len(evidence) >= 4

    binary_gate = next(g for g in gates if g.gate_id == "untrusted_malicious_code")
    assert binary_gate.name == "Root Directory Binary Check"
    assert binary_gate.status == HardGateStatus.PASS
    assert "No precompiled executable files" in binary_gate.reason
    assert "subdirectories and package build scripts are not scanned" in binary_gate.reason


def test_hard_gates_service_root_binary_failure() -> None:
    """Verify hard gate failure when a precompiled binary exists in repository root."""
    data = create_mock_repository_data()
    data["root_contents"].append({"name": "suspicious_payload.exe", "type": "file"})

    act = ActivityService().analyze_activity(data["repository"], data["commits"], data["releases"])
    ci_sec = CISecurityService().analyze_ci_and_security(
        data["repository"], data["workflows"], data["workflow_runs"], data["root_contents"]
    )
    assert ci_sec["root_binary_detected"] is True

    service = HardGatesService()
    gates, evidence, findings = service.evaluate_gates(
        "test_audit_bin", act, ci_sec, data["repository"]
    )

    binary_gate = next(g for g in gates if g.gate_id == "untrusted_malicious_code")
    assert binary_gate.name == "Root Directory Binary Check"
    assert binary_gate.status == HardGateStatus.FAIL
    assert "Precompiled binary file(s) detected in repository root" in binary_gate.reason
    assert any(f.id.endswith("_find_suspicious_binaries") for f in findings)


def test_hard_gates_service_unlicensed_failure() -> None:
    """Verify hard gate failure when repository has no license."""
    data = create_mock_repository_data(license_spdx="None")
    data["repository"]["license"] = None

    act = ActivityService().analyze_activity(data["repository"], data["commits"], data["releases"])
    ci_sec = CISecurityService().analyze_ci_and_security(
        data["repository"], data["workflows"], data["workflow_runs"], data["root_contents"]
    )

    service = HardGatesService()
    gates, evidence, findings = service.evaluate_gates(
        "test_audit", act, ci_sec, data["repository"]
    )

    license_gate = next(g for g in gates if g.gate_id == "unlicensed_repository")
    assert license_gate.status == HardGateStatus.FAIL
    assert len(findings) >= 1
    assert findings[0].severity == "CRITICAL"


def test_newcomer_service_filters_bots() -> None:
    """Verify that automated bot PRs are excluded from newcomer metrics."""
    service = NewcomerService()
    pulls = [
        {
            "number": 1,
            "user": {"login": "dependabot[bot]", "type": "Bot"},
            "author_association": "NONE",
            "state": "closed",
            "merged_at": "2026-11-01T00:00:00Z",
        },
        {
            "number": 2,
            "user": {"login": "renovate-bot", "type": "User"},
            "author_association": "NONE",
            "state": "closed",
            "merged_at": "2026-11-02T00:00:00Z",
        },
        {
            "number": 3,
            "user": {"login": "human_newcomer", "type": "User"},
            "author_association": "FIRST_TIME_CONTRIBUTOR",
            "state": "closed",
            "merged_at": "2026-11-03T00:00:00Z",
        },
    ]
    res = service.analyze_newcomers(issues=[], pull_requests=pulls)
    # Only the human newcomer should be counted
    assert res["newcomer_prs_sample_count"] == 1
    assert res["newcomer_prs_merged"] == 1
    assert res["newcomer_merge_rate"] == 100.0


def test_activity_service_collection_failure() -> None:
    """Verify activity service marks history unavailable when API call failed."""
    service = ActivityService()
    res = service.analyze_activity(
        repository_data={"archived": False},
        commits=[],
        releases=[],
        commits_collection_failed=True,
    )
    assert res["commit_history_available"] is False
    assert res["days_since_latest_commit"] is None
    assert res["is_abandoned"] is False


def test_hard_gates_service_commit_collection_failure_unknown() -> None:
    """Verify hard gate returns UNKNOWN rather than CRITICAL failure when commits API fails."""
    data = create_mock_repository_data()
    act = ActivityService().analyze_activity(
        data["repository"],
        commits=[],
        releases=[],
        commits_collection_failed=True,
    )
    ci_sec = CISecurityService().analyze_ci_and_security(
        data["repository"], data["workflows"], data["workflow_runs"], data["root_contents"]
    )

    service = HardGatesService()
    gates, evidence, findings = service.evaluate_gates(
        "test_audit_err", act, ci_sec, data["repository"]
    )

    dormancy_gate = next(g for g in gates if g.gate_id == "abandoned_repository")
    assert dormancy_gate.status == HardGateStatus.UNKNOWN
    assert dormancy_gate.severity == "HIGH"
    assert "UNKNOWN" in dormancy_gate.reason
    # Should not produce critical abandoned finding
    assert not any(f.id.endswith("_find_dormant") for f in findings)
