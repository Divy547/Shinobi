"""Integration tests for the external AI-client vetting workflow across all 7 tools."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from repovet_mcp.config.settings import Settings
from repovet_mcp.tools.vetting_tools import VettingToolHandlers
from tests.fixtures.mock_data import create_mock_repository_data


@pytest.mark.asyncio
async def test_complete_client_vetting_sequence(tmp_path: Path) -> None:
    """Execute complete 7-tool vetting workflow simulating an AI orchestrator client.

    Verifies tool execution order, data persistence, integrity manifest generation,
    and ReportLab PDF compilation.
    """
    settings = Settings(
        data_dir=tmp_path / "data",
        reports_dir=tmp_path / "reports",
        logs_dir=tmp_path / "logs",
    )
    handlers = VettingToolHandlers(settings)

    owner = "octocat"
    repo = "Spoon-Knife"
    mock_payload = create_mock_repository_data(owner=owner, repo=repo)

    # 1. Step 1: analyze_repository (Mandatory first step)
    with patch(
        "repovet_mcp.tools.vetting_tools.GitHubClient.collect_repository_data",
        new_callable=AsyncMock,
        return_value=mock_payload,
    ):
        init_res = await handlers.analyze_repository(f"{owner}/{repo}")

    audit_id = init_res["audit_id"]
    assert audit_id.startswith(f"audit_{owner}_{repo}_")
    assert init_res["owner"] == owner
    assert init_res["repo"] == repo
    assert init_res["status"] == "INITIALIZED"

    # Verify raw data was stored
    raw_data = handlers.storage.load_raw_data(audit_id)
    assert raw_data["repository"]["name"] == repo

    # 2. Step 2 (Diagnostic): check_hard_gates
    gates_res = await handlers.check_hard_gates(audit_id)
    assert gates_res["audit_id"] == audit_id
    assert gates_res["all_gates_passed"] is True
    assert gates_res["critical_blockers_count"] == 0
    assert len(gates_res["hard_gates"]) == 4

    # 3. Step 3 (Diagnostic): calculate_responsiveness
    resp_res = await handlers.calculate_responsiveness(audit_id)
    assert resp_res["audit_id"] == audit_id
    assert "responsiveness_metrics" in resp_res
    assert resp_res["responsiveness_metrics"]["median_pr_first_response_hours"] == 12.0

    # 4. Step 4 (Diagnostic): analyze_contribution_accessibility
    acc_res = await handlers.analyze_contribution_accessibility(audit_id)
    assert acc_res["audit_id"] == audit_id
    assert acc_res["documentation"]["has_readme"] is True
    assert acc_res["newcomer_accessibility"]["open_beginner_issues_count"] == 3

    # 5. Step 5 (Core): calculate_scorecard
    score_res = await handlers.calculate_scorecard(audit_id)
    assert score_res["audit_id"] == audit_id
    assert score_res["decision"] == "APPROVE"
    assert score_res["total_score"] >= 16
    assert score_res["max_possible_score"] == 20
    assert len(score_res["criteria_scores"]) == 10

    # Verify audit.json and evidence.json were persisted
    audit_report = handlers.storage.load_audit_report(audit_id)
    assert audit_report is not None
    assert audit_report.audit_id == audit_id
    assert audit_report.decision.value == "APPROVE"

    evidence_items = handlers.storage.load_evidence(audit_id)
    assert len(evidence_items) >= 10

    # 6. Step 6: validate_evidence
    val_res = await handlers.validate_evidence(audit_id)
    assert val_res["audit_id"] == audit_id
    assert val_res["validation_results"]["is_valid"] is True
    assert val_res["validation_results"]["total_evidence_count"] >= 10

    # 7. Step 7: generate_pdf_report
    pdf_res = await handlers.generate_pdf_report(audit_id)
    assert pdf_res["audit_id"] == audit_id
    assert pdf_res["status"] == "SUCCESS"
    pdf_path = Path(pdf_res["report_path"])
    assert pdf_path.exists()
    assert pdf_path.stat().st_size > 1000

    # Step 8: Verify SHA-256 integrity manifest
    manifest_verification = handlers.storage.verify_audit_reproducibility(audit_id)
    assert manifest_verification["is_reproducible"] is True
    assert manifest_verification["is_tampered"] is False
    assert manifest_verification["integrity_status"] == "VERIFIED"
    assert len(manifest_verification["tampered_files"]) == 0
    assert len(manifest_verification["missing_files"]) == 0


@pytest.mark.asyncio
async def test_manifest_tamper_detection(tmp_path: Path) -> None:
    """Verify SHA-256 manifest detects external tampering of stored audit artifacts."""
    settings = Settings(
        data_dir=tmp_path / "data",
        reports_dir=tmp_path / "reports",
    )
    handlers = VettingToolHandlers(settings)
    audit_id = "audit_tamper_test_001"

    # Seed mock data and calculate scorecard
    mock_payload = create_mock_repository_data(owner="tamper", repo="check")
    handlers.storage.save_raw_data(audit_id, mock_payload)
    await handlers.calculate_scorecard(audit_id)

    # Initial verification passes
    initial_check = handlers.storage.verify_audit_reproducibility(audit_id)
    assert initial_check["is_reproducible"] is True
    assert initial_check["is_tampered"] is False

    # Tamper with audit.json directly on disk
    audit_json_path = settings.data_dir / audit_id / "audit.json"
    content = audit_json_path.read_text(encoding="utf-8")
    tampered_content = content.replace('"APPROVE"', '"REJECT"')
    audit_json_path.write_text(tampered_content, encoding="utf-8")

    # Verification must now fail and identify the tampered file
    tampered_check = handlers.storage.verify_audit_reproducibility(audit_id)
    assert tampered_check["is_reproducible"] is False
    assert tampered_check["is_tampered"] is True
    assert tampered_check["integrity_status"] == "TAMPERED"
    assert "audit.json" in tampered_check["tampered_files"]


@pytest.mark.asyncio
async def test_analyze_repository_overwrite_behavior(tmp_path: Path) -> None:
    """Verify re-running analyze_repository with the same audit_id safely overwrites raw snapshot."""
    settings = Settings(
        data_dir=tmp_path / "data",
        reports_dir=tmp_path / "reports",
    )
    handlers = VettingToolHandlers(settings)
    audit_id = "audit_overwrite_test_001"

    mock_v1 = create_mock_repository_data(owner="test", repo="repo")
    mock_v1["repository"]["stargazers_count"] = 100

    with patch(
        "repovet_mcp.tools.vetting_tools.GitHubClient.collect_repository_data",
        new_callable=AsyncMock,
        return_value=mock_v1,
    ):
        await handlers.analyze_repository("test/repo", audit_id=audit_id)

    loaded_v1 = handlers.storage.load_raw_data(audit_id)
    assert loaded_v1["repository"]["stargazers_count"] == 100

    # Now re-run with updated snapshot
    mock_v2 = create_mock_repository_data(owner="test", repo="repo")
    mock_v2["repository"]["stargazers_count"] = 500

    with patch(
        "repovet_mcp.tools.vetting_tools.GitHubClient.collect_repository_data",
        new_callable=AsyncMock,
        return_value=mock_v2,
    ):
        await handlers.analyze_repository("test/repo", audit_id=audit_id)

    loaded_v2 = handlers.storage.load_raw_data(audit_id)
    assert loaded_v2["repository"]["stargazers_count"] == 500
