"""Unit tests to verify clean package imports and baseline data model instantiation."""

import pytest

import repovet_mcp
from repovet_mcp.config import Settings, get_settings
from repovet_mcp.models import (
    AuditDecision,
    AuditReport,
    AuditTarget,
    CriterionScore,
    EvidenceConfidence,
    EvidenceItem,
    EvidenceSourceType,
    Finding,
    FindingCategory,
    FindingSeverity,
    Scorecard,
)
from repovet_mcp.server import create_server, parse_args


def test_package_metadata() -> None:
    """Verify package version and exports."""
    assert hasattr(repovet_mcp, "__version__")
    assert repovet_mcp.__version__ == "0.1.0"


def test_config_imports() -> None:
    """Verify configuration symbols are importable and callable."""
    assert Settings is not None
    assert callable(get_settings)


def test_model_instantiations() -> None:
    """Verify baseline Pydantic data models instantiate cleanly."""
    evidence = EvidenceItem(
        id="ev-test-1",
        phase="phase_1_identity_and_licensing",
        source_type=EvidenceSourceType.GITHUB_API_REST,
        source_endpoint="GET /repos/test/repo/license",
        confidence=EvidenceConfidence.CONFIRMED,
        summary="MIT License found",
        verified=True,
    )
    assert evidence.id == "ev-test-1"
    assert evidence.confidence == EvidenceConfidence.CONFIRMED

    finding = Finding(
        id="find-test-1",
        phase="phase_1_identity_and_licensing",
        category=FindingCategory.LICENSING,
        severity=FindingSeverity.INFO,
        title="Valid OSI License",
        description="Repository is licensed under MIT.",
        evidence_ids=[evidence.id],
    )
    assert finding.id == "find-test-1"
    assert finding.category == FindingCategory.LICENSING

    target = AuditTarget(
        owner="octocat",
        repo="Hello-World",
        url="https://github.com/octocat/Hello-World",
        default_branch="master",
    )
    assert target.owner == "octocat"

    crit_score = CriterionScore(
        criterion_id="security_and_licensing",
        name="Security Posture & License Compliance",
        phase="phase_1_identity_and_licensing",
        score=2,
        max_score=2,
        rationale="Valid MIT license present with clean attribution.",
        evidence_ids=[evidence.id],
    )
    assert crit_score.score == 2

    scorecard = Scorecard(
        criteria_scores=[crit_score],
        total_score=2,
        max_possible_score=20,
    )
    assert scorecard.percentage == 10.0

    report = AuditReport(
        audit_id="audit-test-001",
        target=target,
        decision=AuditDecision.CONDITIONAL,
        scorecard=scorecard,
        findings=[finding],
        evidence=[evidence],
        summary="Test audit report",
    )
    assert report.decision == AuditDecision.CONDITIONAL
    assert len(report.findings) == 1


def test_server_creation() -> None:
    """Verify FastMCP server initializes without errors."""
    server = create_server()
    assert server is not None
    assert server.name == "repovet-mcp"


def test_cli_parse_args_empty() -> None:
    """Verify default CLI arguments return without error."""
    args = parse_args([])
    assert args is not None


def test_cli_parse_args_help(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify --help outputs usage information and exits immediately with code 0."""
    with pytest.raises(SystemExit) as exc_info:
        parse_args(["--help"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "usage:" in captured.out
    assert "repovet-mcp" in captured.out


def test_cli_parse_args_version(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify --version outputs program version and exits immediately with code 0."""
    with pytest.raises(SystemExit) as exc_info:
        parse_args(["--version"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "repovet-mcp" in captured.out
    assert "0.1.0" in captured.out
