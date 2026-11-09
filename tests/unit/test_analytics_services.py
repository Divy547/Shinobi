"""Unit tests for the modular analytics services and hard gates evaluator."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

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
    assert service.is_bot_user({"login": "zulipbot", "type": "User"}) is True
    assert service.is_bot_user({"login": "k8s-ci-robot", "type": "User"}) is True
    assert service.is_bot_user({"login": "google-cla", "type": "User"}) is True
    assert service.is_bot_user({"login": "cla-assistant", "type": "User"}) is True
    assert service.is_bot_user({"login": "custom-bot", "type": "User"}) is True
    assert service.is_bot_user({"login": "deploy_bot", "type": "User"}) is True
    assert service.is_bot_user({"login": "alice", "type": "User"}) is False
    assert service.is_bot_user({"login": "talbot", "type": "User"}) is False
    assert service.is_bot_user(None) is False


def test_responsiveness_service_excludes_user_type_bots_and_reports_unobserved() -> None:
    """Verify comments from User-type bots like zulipbot are excluded and yield unobserved metric."""
    now = datetime.now(UTC)
    pr_created = now - timedelta(hours=2)
    service = ResponsivenessService()

    pull_requests = [
        {
            "number": 40617,
            "created_at": pr_created.isoformat(),
            "updated_at": (pr_created + timedelta(seconds=6)).isoformat(),
            "state": "open",
            "user": {"login": "contributor", "type": "User"},
        }
    ]
    # zulipbot commented 6 seconds after creation
    sampled_pr_comments = {
        40617: [
            {
                "user": {"login": "zulipbot", "type": "User"},
                "created_at": (pr_created + timedelta(seconds=6)).isoformat(),
                "body": "Welcome! Please follow the contribution guide.",
            }
        ]
    }
    sampled_pr_reviews: dict[int, list[dict[str, Any]]] = {}

    metrics = service.analyze_responsiveness(
        issues=[],
        pull_requests=pull_requests,
        sampled_issue_comments={},
        sampled_pr_reviews=sampled_pr_reviews,
        sampled_pr_comments=sampled_pr_comments,
        now=now,
    )

    # zulipbot must be excluded, resulting in unobserved human response (None), not 0.0h
    assert metrics["total_prs_evaluated"] == 1
    assert metrics["prs_with_human_response_count"] == 0
    assert metrics["median_pr_first_response_hours"] is None
    assert metrics["bot_comments_count"] == 1
    assert metrics["human_comments_count"] == 0


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


def test_documentation_service_nested_gsoc_discovery() -> None:
    """Verify discovery of GSoC docs across docs/outreach/, docs/, and .github/."""
    service = DocumentationService()

    # 1. GSoC doc nested in docs/outreach/ (e.g., Zulip style)
    nested_zulip = {
        "docs/outreach": [
            {"name": "apply.md", "path": "docs/outreach/apply.md"},
            {"name": "gsoc.md", "path": "docs/outreach/gsoc.md"},
            {"name": "mentoring.md", "path": "docs/outreach/mentoring.md"},
        ]
    }
    m1 = service.analyze_documentation([], {}, nested_contents=nested_zulip)
    assert m1["has_gsoc_doc"] is True
    assert m1["gsoc_doc_path"] == "docs/outreach/gsoc.md"

    # 2. GSoC doc in docs/
    nested_docs = {
        "docs": [
            {"name": "index.md", "path": "docs/index.md"},
            {"name": "summer-of-code.md", "path": "docs/summer-of-code.md"},
        ]
    }
    m2 = service.analyze_documentation([], {}, nested_contents=nested_docs)
    assert m2["has_gsoc_doc"] is True
    assert m2["gsoc_doc_path"] == "docs/summer-of-code.md"

    # 3. GSoC doc in .github/
    nested_gh = {
        ".github": [
            {"name": "GSOC.md", "path": ".github/GSOC.md"},
        ]
    }
    m3 = service.analyze_documentation([], {}, nested_contents=nested_gh)
    assert m3["has_gsoc_doc"] is True
    assert m3["gsoc_doc_path"] == ".github/GSOC.md"


def test_documentation_service_unknown_when_unverified() -> None:
    """Verify that absence of GSoC documentation across root and nested dirs reports has_gsoc_doc=False."""
    service = DocumentationService()
    root_files = [
        {"name": "README.md", "type": "file"},
        {"name": "CONTRIBUTING.md", "type": "file"},
    ]
    nested = {
        "docs": [{"name": "architecture.md", "type": "file"}],
        ".github": [{"name": "workflows", "type": "dir"}],
    }
    metrics = service.analyze_documentation(root_files, {}, nested_contents=nested)
    assert metrics["has_gsoc_doc"] is False
    assert metrics["gsoc_doc_path"] is None


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


def test_ci_security_service_discovers_default_branch_after_first_ten_pr_runs() -> None:
    """Verify default-branch run is discovered even when preceded by more than 10 PR runs."""
    service = CISecurityService()
    # 14 PR runs followed by 1 successful default branch run on 'main'
    runs: list[dict[str, Any]] = []
    for i in range(14):
        runs.append(
            {
                "id": 1000 + i,
                "name": f"PR Check {i}",
                "head_branch": f"feature-pr-{i}",
                "conclusion": "success",
                "status": "completed",
            }
        )
    runs.append(
        {
            "id": 1015,
            "name": "Default Branch CI",
            "head_branch": "main",
            "conclusion": "success",
            "status": "completed",
        }
    )

    metrics = service.analyze_ci_and_security(
        repository_data={"default_branch": "main"},
        workflows=[{"id": 1, "name": "CI"}],
        workflow_runs=runs,
        root_contents=[],
    )

    assert metrics["ci_passing_on_default_branch"] is True
    assert metrics["latest_default_branch_ci_conclusion"] == "success"


def test_ci_security_service_distinguishes_confirmed_failing_on_custom_default_branch() -> None:
    """Verify confirmed failing CI on custom default branch (e.g., 'trunk') after PR runs."""
    service = CISecurityService()
    runs: list[dict[str, Any]] = []
    for i in range(12):
        runs.append(
            {
                "id": 2000 + i,
                "head_branch": f"patch-{i}",
                "conclusion": "success",
                "status": "completed",
            }
        )
    runs.append(
        {
            "id": 2013,
            "head_branch": "trunk",
            "conclusion": "failure",
            "status": "completed",
        }
    )

    metrics = service.analyze_ci_and_security(
        repository_data={"default_branch": "trunk"},
        workflows=[{"id": 1, "name": "CI"}],
        workflow_runs=runs,
        root_contents=[],
    )

    assert metrics["ci_passing_on_default_branch"] is False
    assert metrics["latest_default_branch_ci_conclusion"] == "failure"


def test_ci_security_service_distinguishes_genuinely_unavailable_when_no_default_runs() -> None:
    """Verify UNKNOWN / unavailable CI status when all workflow runs belong to feature branches."""
    service = CISecurityService()
    runs = [
        {
            "id": 3000 + i,
            "head_branch": f"feature-{i}",
            "conclusion": "success",
            "status": "completed",
        }
        for i in range(15)
    ]

    metrics = service.analyze_ci_and_security(
        repository_data={"default_branch": "main"},
        workflows=[{"id": 1, "name": "CI"}],
        workflow_runs=runs,
        root_contents=[],
    )

    assert metrics["ci_passing_on_default_branch"] is None
    assert metrics["latest_default_branch_ci_conclusion"] is None

    # Hard gate evaluation on unavailable CI status
    gate_service = HardGatesService()
    gates, _, _ = gate_service.evaluate_gates(
        "audit_test_ci_unknown",
        {"is_abandoned": False, "latest_commit_date": "2026-11-01T00:00:00Z"},
        metrics,
        {"default_branch": "main", "license": {"spdx_id": "MIT"}},
    )
    ci_gate = next(g for g in gates if g.gate_id == "failing_default_branch")
    assert ci_gate.status == HardGateStatus.UNKNOWN
    assert "no recent workflow run logs were retrieved" in ci_gate.reason


def test_ci_security_service_handles_in_progress_and_completed_runs() -> None:
    """Verify that an in-progress run does not mask the latest completed build conclusion."""
    service = CISecurityService()
    runs = [
        # In-progress run on main
        {"id": 4001, "head_branch": "main", "conclusion": None, "status": "in_progress"},
        # Prior completed run on main
        {"id": 4000, "head_branch": "main", "conclusion": "success", "status": "completed"},
    ]

    metrics = service.analyze_ci_and_security(
        repository_data={"default_branch": "main"},
        workflows=[{"id": 1, "name": "CI"}],
        workflow_runs=runs,
        root_contents=[],
    )

    assert metrics["ci_passing_on_default_branch"] is True
    assert metrics["latest_default_branch_ci_conclusion"] == "success"


@pytest.mark.parametrize(
    ("conclusion", "expected_passing", "expected_gate_status"),
    [
        ("success", True, HardGateStatus.PASS),
        ("failure", False, HardGateStatus.FAIL),
        ("timed_out", False, HardGateStatus.FAIL),
        ("cancelled", False, HardGateStatus.FAIL),
        ("action_required", False, HardGateStatus.FAIL),
        ("startup_failure", False, HardGateStatus.FAIL),
        ("neutral", None, HardGateStatus.UNKNOWN),
        ("skipped", None, HardGateStatus.UNKNOWN),
        ("stale", None, HardGateStatus.UNKNOWN),
    ],
)
def test_ci_security_service_explicit_conclusions_mapping(
    conclusion: str, expected_passing: bool | None, expected_gate_status: HardGateStatus
) -> None:
    """Verify that every documented GitHub Actions conclusion maps to PASS, FAIL, or UNKNOWN."""
    service = CISecurityService()
    runs = [
        {
            "id": 5001,
            "head_branch": "main",
            "conclusion": conclusion,
            "status": "completed",
        }
    ]

    metrics = service.analyze_ci_and_security(
        repository_data={"default_branch": "main"},
        workflows=[{"id": 1, "name": "CI"}],
        workflow_runs=runs,
        root_contents=[],
    )

    assert metrics["ci_passing_on_default_branch"] is expected_passing
    assert metrics["latest_default_branch_ci_conclusion"] == conclusion

    # Verify hard gate mapping
    gate_service = HardGatesService()
    gates, _, findings = gate_service.evaluate_gates(
        f"audit_test_ci_{conclusion}",
        {"is_abandoned": False, "latest_commit_date": "2026-11-01T00:00:00Z"},
        metrics,
        {"default_branch": "main", "license": {"spdx_id": "MIT"}},
    )
    ci_gate = next(g for g in gates if g.gate_id == "failing_default_branch")
    assert ci_gate.status == expected_gate_status

    if expected_gate_status == HardGateStatus.FAIL:
        assert any(f.id.endswith("_find_broken_ci") for f in findings)
    elif expected_gate_status == HardGateStatus.UNKNOWN:
        assert not any(f.id.endswith("_find_broken_ci") for f in findings)
        assert f"concluded with '{conclusion}'" in ci_gate.reason


def test_ci_security_service_in_progress_does_not_mask_prior_failure() -> None:
    """Verify that an in-progress run does not mask a prior failed build conclusion."""
    service = CISecurityService()
    runs = [
        {"id": 6002, "head_branch": "main", "conclusion": None, "status": "in_progress"},
        {"id": 6001, "head_branch": "main", "conclusion": "failure", "status": "completed"},
    ]

    metrics = service.analyze_ci_and_security(
        repository_data={"default_branch": "main"},
        workflows=[{"id": 1, "name": "CI"}],
        workflow_runs=runs,
        root_contents=[],
    )

    assert metrics["ci_passing_on_default_branch"] is False
    assert metrics["latest_default_branch_ci_conclusion"] == "failure"


def test_ci_security_service_only_in_progress_or_queued_runs() -> None:
    """Verify that when only in-progress or queued runs exist, status is UNKNOWN."""
    service = CISecurityService()
    runs = [
        {"id": 7002, "head_branch": "main", "conclusion": None, "status": "in_progress"},
        {"id": 7001, "head_branch": "main", "conclusion": None, "status": "queued"},
    ]

    metrics = service.analyze_ci_and_security(
        repository_data={"default_branch": "main"},
        workflows=[{"id": 1, "name": "CI"}],
        workflow_runs=runs,
        root_contents=[],
    )

    assert metrics["ci_passing_on_default_branch"] is None
    assert metrics["latest_default_branch_ci_conclusion"] == "in_progress"

    gate_service = HardGatesService()
    gates, _, _ = gate_service.evaluate_gates(
        "audit_test_ci_in_progress",
        {"is_abandoned": False, "latest_commit_date": "2026-11-01T00:00:00Z"},
        metrics,
        {"default_branch": "main", "license": {"spdx_id": "MIT"}},
    )
    ci_gate = next(g for g in gates if g.gate_id == "failing_default_branch")
    assert ci_gate.status == HardGateStatus.UNKNOWN
    assert "currently 'in_progress'" in ci_gate.reason


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
