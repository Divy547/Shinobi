"""Unit tests for PDF report generator hardening and PDF structural validation."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

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
from repovet_mcp.reporting.pdf_generator import PDFReportGenerator
from repovet_mcp.reporting.pdf_validator import PDFStructuralValidator


@pytest.fixture
def pdf_env(tmp_path: Path) -> tuple[PDFReportGenerator, PDFStructuralValidator]:
    settings = Settings(
        reports_dir=tmp_path / "reports",
        data_dir=tmp_path / "data",
        logs_dir=tmp_path / "logs",
        config_dir=Path(__file__).parent.parent.parent / "config",
    )
    generator = PDFReportGenerator(settings)
    validator = PDFStructuralValidator()
    return generator, validator


def test_pdf_structural_validator_detects_invalid_files(
    pdf_env: tuple[PDFReportGenerator, PDFStructuralValidator], tmp_path: Path
) -> None:
    """Verify PDFStructuralValidator rejects invalid headers, truncated files, and non-PDFs."""
    _, validator = pdf_env

    # 1. Non-existent file
    res = validator.validate_file(tmp_path / "non_existent.pdf")
    assert not res.is_valid
    assert any("does not exist" in e for e in res.errors)

    # 2. File too small (< 100 bytes)
    tiny = tmp_path / "tiny.pdf"
    tiny.write_bytes(b"%PDF-1.4\nend")
    res = validator.validate_file(tiny)
    assert not res.is_valid
    assert any("too small" in e for e in res.errors)

    # 3. Missing magic header
    no_magic = tmp_path / "no_magic.pdf"
    no_magic.write_bytes(b"INVALID_HEADER" + b" " * 200 + b"%%EOF")
    res = validator.validate_file(no_magic)
    assert not res.is_valid
    assert not res.has_magic_header

    # 4. Missing EOF marker
    no_eof = tmp_path / "no_eof.pdf"
    no_eof.write_bytes(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj" + b" " * 200)
    res = validator.validate_file(no_eof)
    assert not res.is_valid
    assert not res.has_eof_marker


def test_pdf_generation_with_missing_metrics_and_empty_sections(
    pdf_env: tuple[PDFReportGenerator, PDFStructuralValidator],
) -> None:
    """Verify PDF generates cleanly when stats contain None and findings/beginner issues are empty."""
    generator, validator = pdf_env

    target = AuditTarget(
        owner="minimal-owner",
        repo="minimal-repo",
        url="https://github.com/minimal-owner/minimal-repo",
        default_branch="main",
        description=None,
        stars=0,
        forks=0,
        open_issues=0,
        license_spdx=None,
    )
    scorecard = Scorecard(
        total_score=10,
        max_possible_score=20,
        criteria_scores=[
            CriterionScore(
                criterion_id="crit_activity",
                name="Minimal Criterion",
                phase="activity",
                score=1,
                rationale="Criterion evaluated with partial data.",
            )
        ],
    )
    report = AuditReport(
        audit_id="audit_minimal_001",
        target=target,
        decision=AuditDecision.CONDITIONAL,
        scorecard=scorecard,
        hard_gates=[],  # Empty hard gates
        findings=[],  # Empty findings
        evidence=[],  # Empty evidence
        summary="Minimal audit report for hardening verification.",
        activity_stats={
            "days_since_latest_commit": None,
            "commits_last_90d": None,
        },
        responsiveness_stats={
            "median_pr_first_response_hours": None,
            "pr_merge_rate": None,
            "unanswered_issue_percentage": None,
        },
        accessibility_stats={
            "newcomer_merge_rate": None,
            "open_beginner_issues_count": None,
            "open_beginner_issues": [],  # Empty beginner issues
        },
    )

    pdf_path = generator.generate_report(report)
    assert pdf_path.exists()
    assert pdf_path.stat().st_size > 500

    # Structurally validate PDF
    validation = validator.validate_file(pdf_path)
    assert validation.is_valid
    assert validation.has_magic_header
    assert validation.has_eof_marker
    assert validation.has_catalog
    assert validation.has_pages_tree
    assert validation.page_count >= 1


def test_pdf_generation_with_xml_special_characters_and_markup(
    pdf_env: tuple[PDFReportGenerator, PDFStructuralValidator],
) -> None:
    """Verify XML special characters in repo data and findings render without ReportLab syntax crashes."""
    generator, validator = pdf_env

    target = AuditTarget(
        owner="org<with>brackets",
        repo='repo&ampersand"quote',
        url="https://github.com/org/repo?param1=val&param2=val",
        default_branch="main",
        description="Untrusted description with <script>alert('xss')</script> & unclosed <tags",
        stars=150,
        forks=25,
        open_issues=10,
        license_spdx="MIT & Apache-2.0",
    )
    scorecard = Scorecard(
        total_score=14,
        max_possible_score=20,
        criteria_scores=[
            CriterionScore(
                criterion_id="crit_ci_security",
                name="Security & Safe Parsing <AST>",
                phase="ci_security",
                score=2,
                rationale="Validated safe AST parsing with 0 < x && y > 10.",
            )
        ],
    )
    evidence_items = [
        EvidenceItem(
            id=f"ev_injection_{i}",
            phase="governance",
            confidence=EvidenceConfidence.CONFIRMED,
            source_type=EvidenceSourceType.GITHUB_API_REST,
            source_endpoint=f"GET /repos/test/issues?query=<tag>&page={i}",
            summary=f"Observation item {i} with <markup> injection and special 'symbols' & quotes.",
            collected_at=datetime.now(UTC),
        )
        for i in range(25)  # Multi-page evidence list
    ]

    report = AuditReport(
        audit_id="audit_xml_injection_002",
        target=target,
        decision=AuditDecision.APPROVE,
        scorecard=scorecard,
        hard_gates=[
            HardGateResult(
                gate_id="gate_license",
                name="License Check <Permissive>",
                status=HardGateStatus.PASS,
                severity="CRITICAL",
                reason="Permissive MIT license found in LICENSE.md <root>.",
            )
        ],
        findings=[],
        evidence=evidence_items,
        summary="Audit with special characters.",
    )

    pdf_path = generator.generate_report(report)
    assert pdf_path.exists()

    # Structurally validate PDF
    validation = validator.validate_file(pdf_path)
    assert validation.is_valid
    assert validation.page_count >= 2  # Multi-page pagination


def test_pdf_generation_unicode_emoji_and_cjk_fallback(
    pdf_env: tuple[PDFReportGenerator, PDFStructuralValidator],
) -> None:
    """Verify PDF generator handles emojis, CJK scripts, and accented Latin without errors."""
    generator, validator = pdf_env

    target = AuditTarget(
        owner="unicode-org",
        repo="unicode-repo",
        url="https://github.com/unicode-org/unicode-repo",
        default_branch="main",
        description="International project: Café Schrödinger 🚀 ✨ 世界 日本語 résumé",
        stars=420,
        forks=50,
        open_issues=5,
        license_spdx="Apache-2.0",
    )
    scorecard = Scorecard(
        total_score=19,
        max_possible_score=20,
        criteria_scores=[
            CriterionScore(
                criterion_id="crit_docs",
                name="Documentation with Accents (naïve & façade)",
                phase="documentation",
                score=2,
                rationale="Excellent documentation in English and Japanese 日本語 with 🚀 launch guides.",
            )
        ],
    )
    evidence_items = [
        EvidenceItem(
            id="ev_unicode_01",
            phase="governance",
            confidence=EvidenceConfidence.CONFIRMED,
            source_type=EvidenceSourceType.GITHUB_API_REST,
            source_endpoint="https://github.com/unicode-org/unicode-repo/releases/v1.0",
            summary="Release 1.0 ✨ contains internationalization features for 世界 and Café.",
            collected_at=datetime.now(UTC),
        )
    ]

    report = AuditReport(
        audit_id="audit_unicode_fallback_003",
        target=target,
        decision=AuditDecision.APPROVE,
        scorecard=scorecard,
        hard_gates=[
            HardGateResult(
                gate_id="gate_license",
                name="License Check (Apache-2.0)",
                status=HardGateStatus.PASS,
                severity="CRITICAL",
                reason="Permissive Apache-2.0 license verified.",
            )
        ],
        findings=[],
        evidence=evidence_items,
        summary="Audit containing accented Latin, Emojis, and CJK characters.",
    )

    pdf_path = generator.generate_report(report)
    assert pdf_path.exists()

    # Validate structural compliance
    validation = validator.validate_file(pdf_path)
    assert validation.is_valid
    assert validation.has_magic_header
    assert validation.has_eof_marker
    assert validation.has_catalog
    assert validation.has_pages_tree
    assert validation.page_count >= 1
    assert pdf_path.stat().st_size > 1000
