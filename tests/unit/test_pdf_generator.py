"""Unit tests for the ReportLab PDF audit report generator."""

from pathlib import Path

from repovet_mcp.config.settings import Settings
from repovet_mcp.models.audit import (
    AuditDecision,
    AuditReport,
    AuditTarget,
    CriterionScore,
    HardGateResult,
    HardGateStatus,
    Scorecard,
)
from repovet_mcp.models.evidence import (
    EvidenceConfidence,
    EvidenceItem,
    EvidenceSourceType,
)
from repovet_mcp.models.findings import Finding, FindingCategory, FindingSeverity
from repovet_mcp.reporting.pdf_generator import PDFReportGenerator


def test_pdf_report_generator(tmp_path: Path) -> None:
    """Verify compilation of a professional multi-section PDF audit report."""
    test_settings = Settings(reports_dir=tmp_path / "reports")
    generator = PDFReportGenerator(test_settings)

    target = AuditTarget(
        owner="pallets",
        repo="flask",
        url="https://github.com/pallets/flask",
        default_branch="main",
        description="The Python micro framework for building web applications.",
        stars=68000,
        forks=16000,
        open_issues=24,
        license_spdx="BSD-3-Clause",
    )

    ev1 = EvidenceItem(
        id="ev_flask_01",
        phase="phase_1_identity_and_licensing",
        source_type=EvidenceSourceType.GITHUB_API_REST,
        source_endpoint="https://api.github.com/repos/pallets/flask/license",
        confidence=EvidenceConfidence.CONFIRMED,
        summary="Repository licensed under standard BSD-3-Clause.",
        verified=True,
    )

    finding = Finding(
        id="find_flask_01",
        phase="phase_5_documentation_and_onboarding",
        category=FindingCategory.DOCUMENTATION,
        severity=FindingSeverity.INFO,
        title="Comprehensive Documentation",
        description="Pallets documentation ecosystem is exemplary with Sphinx docs.",
        evidence_ids=[ev1.id],
        remediation_recommendation="Continue maintaining current docs.",
    )

    gate = HardGateResult(
        gate_id="unlicensed_repository",
        name="Open Source License Validity",
        status=HardGateStatus.PASS,
        severity="CRITICAL",
        reason="BSD-3-Clause is an approved OSI open-source license.",
        evidence_ids=[ev1.id],
    )

    crit_scores = [
        CriterionScore(
            criterion_id="commit_activity",
            name="Commit Activity & Maintenance Cadence",
            phase="phase_2_vitality_and_pulse",
            score=2,
            max_score=2,
            rationale="Continuous regular commits and active maintenance.",
            evidence_ids=[ev1.id],
        ),
        CriterionScore(
            criterion_id="pr_first_response",
            name="PR First Human Response Time",
            phase="phase_4_responsiveness_and_velocity",
            score=2,
            max_score=2,
            rationale="Rapid maintainer reviews provided within 48 hours.",
            evidence_ids=[ev1.id],
        ),
    ]

    report = AuditReport(
        audit_id="audit_flask_test_01",
        target=target,
        decision=AuditDecision.APPROVE,
        scorecard=Scorecard(criteria_scores=crit_scores, total_score=18, max_possible_score=20),
        hard_gates=[gate],
        findings=[finding],
        evidence=[ev1],
        summary="Pallets Flask demonstrates exemplary health and responsiveness.",
        activity_stats={"days_since_latest_commit": 3, "commits_last_90d": 42},
        responsiveness_stats={
            "median_pr_first_response_hours": 24.5,
            "pr_merge_rate": 88.0,
            "unanswered_issue_percentage": 5.0,
        },
        accessibility_stats={
            "open_beginner_issues_count": 4,
            "newcomer_merge_rate": 75.0,
            "newcomer_prs_merged": 6,
            "open_beginner_issues": [
                {
                    "number": 4501,
                    "title": "Improve error handling",
                    "url": "https://github.com/...",
                    "labels": ["good first issue"],
                }
            ],
        },
    )

    pdf_path = generator.generate_report(report)

    assert pdf_path.exists()
    assert pdf_path.is_file()
    assert pdf_path.suffix == ".pdf"
    assert pdf_path.stat().st_size > 1000

    # Verify standard PDF header magic bytes
    with pdf_path.open("rb") as f:
        header = f.read(5)
        assert header == b"%PDF-"
