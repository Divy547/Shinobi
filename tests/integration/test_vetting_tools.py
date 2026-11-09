"""Integration tests for all seven RepoVet MCP tools end-to-end."""

from pathlib import Path

import pytest

from repovet_mcp.config.settings import Settings
from repovet_mcp.tools.vetting_tools import VettingToolHandlers
from tests.fixtures.mock_data import create_mock_repository_data


@pytest.mark.asyncio
async def test_full_vetting_tools_workflow(tmp_path: Path) -> None:
    """Execute all seven MCP tools sequentially on an initialized audit dataset."""
    test_settings = Settings(
        data_dir=tmp_path / "data",
        reports_dir=tmp_path / "reports",
    )
    handlers = VettingToolHandlers(test_settings)
    audit_id = "audit_integration_test_100"

    # Seed storage with realistic mock repository dataset
    mock_data = create_mock_repository_data(owner="psf", repo="requests")
    handlers.storage.save_raw_data(audit_id, mock_data)

    # 1. Tool: check_hard_gates
    gate_res = await handlers.check_hard_gates(audit_id)
    assert gate_res["audit_id"] == audit_id
    assert "hard_gates" in gate_res
    assert len(gate_res["hard_gates"]) == 4
    assert gate_res["all_gates_passed"] is True

    # 2. Tool: calculate_responsiveness
    resp_res = await handlers.calculate_responsiveness(audit_id)
    assert resp_res["audit_id"] == audit_id
    metrics = resp_res["responsiveness_metrics"]
    assert metrics["median_pr_first_response_hours"] == 12.0
    assert metrics["pr_merge_rate"] == 100.0

    # 3. Tool: analyze_contribution_accessibility
    acc_res = await handlers.analyze_contribution_accessibility(audit_id)
    assert acc_res["audit_id"] == audit_id
    assert acc_res["documentation"]["has_readme"] is True
    assert acc_res["newcomer_accessibility"]["open_beginner_issues_count"] == 3

    # 4. Tool: calculate_scorecard
    score_res = await handlers.calculate_scorecard(audit_id)
    assert score_res["audit_id"] == audit_id
    assert score_res["decision"] == "APPROVE"
    assert score_res["total_score"] >= 16
    assert len(score_res["criteria_scores"]) == 10
    assert len(score_res["hard_gates"]) == 4

    # 5. Tool: validate_evidence
    val_res = await handlers.validate_evidence(audit_id)
    assert val_res["audit_id"] == audit_id
    assert val_res["validation_results"]["is_valid"] is True
    assert val_res["validation_results"]["total_evidence_count"] >= 10

    # 6. Tool: generate_pdf_report
    pdf_res = await handlers.generate_pdf_report(audit_id)
    assert pdf_res["audit_id"] == audit_id
    assert pdf_res["status"] == "SUCCESS"
    pdf_path = Path(pdf_res["report_path"])
    assert pdf_path.exists()
    assert pdf_path.stat().st_size > 1000
