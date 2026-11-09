"""Unit tests for storage service: isolation, atomicity, traversal, corruption, and reproducibility."""

from pathlib import Path

import pytest

from repovet_mcp.config.settings import Settings
from repovet_mcp.models.audit import (
    AuditDecision,
    AuditReport,
    AuditTarget,
    HardGateResult,
    HardGateStatus,
    Scorecard,
)
from repovet_mcp.services.storage_service import StorageCorruptionError, StorageService


@pytest.fixture
def temp_storage(tmp_path: Path) -> StorageService:
    settings = Settings(
        data_dir=tmp_path / "data",
        reports_dir=tmp_path / "reports",
        logs_dir=tmp_path / "logs",
        config_dir=Path(__file__).parent.parent.parent / "config",
    )
    return StorageService(settings)


def test_storage_audit_isolation(temp_storage: StorageService) -> None:
    """Verify audits are stored strictly in isolated directory structures."""
    audit_id = "audit_pallets_flask_12345"
    test_data = {"repository": {"name": "flask", "owner": {"login": "pallets"}}}

    path = temp_storage.save_raw_data(audit_id, test_data)
    assert path.exists()
    assert audit_id in str(path)

    loaded = temp_storage.load_raw_data(audit_id)
    assert loaded["repository"]["name"] == "flask"


def test_storage_path_traversal_rejection(temp_storage: StorageService) -> None:
    """Verify invalid or path traversal audit IDs are rejected before filesystem operations."""
    with pytest.raises(ValueError, match="Invalid audit ID"):
        temp_storage.save_raw_data("../escaped_id", {"test": True})

    with pytest.raises(ValueError, match="Invalid audit ID"):
        temp_storage.load_raw_data("../../escaped_id")


def test_storage_atomic_json_write(temp_storage: StorageService) -> None:
    """Verify JSON files are written atomically without leaving partial or corrupted files."""
    audit_id = "audit_atomic_test_999"
    payload = {"key": "value", "numbers": list(range(100))}

    path = temp_storage.save_raw_data(audit_id, payload)
    assert path.exists()

    # Verify no leftover temp files in directory
    parent_dir = path.parent
    tmp_files = list(parent_dir.glob("*.tmp*"))
    assert len(tmp_files) == 0

    # Content correctly written and readable
    loaded = temp_storage.load_raw_data(audit_id)
    assert loaded["numbers"] == list(range(100))


def test_storage_corruption_handling(temp_storage: StorageService) -> None:
    """Verify empty or non-JSON files raise StorageCorruptionError."""
    audit_id = "audit_corrupted_123"
    audit_dir = temp_storage.base_data_dir / audit_id
    audit_dir.mkdir(parents=True, exist_ok=True)

    # Empty file (0 bytes)
    raw_path = audit_dir / "raw_data.json"
    raw_path.touch()

    with pytest.raises(StorageCorruptionError, match="empty"):
        temp_storage.load_raw_data(audit_id)

    # Malformed JSON file
    raw_path.write_text("{ incomplete json: ", encoding="utf-8")
    with pytest.raises(StorageCorruptionError, match="[Mm]alformed JSON"):
        temp_storage.load_raw_data(audit_id)


def test_storage_verify_audit_reproducibility(temp_storage: StorageService) -> None:
    """Verify audit verification calculates sha256 checksums and validates completeness."""
    audit_id = "audit_repro_test_100"

    # Initially missing
    result = temp_storage.verify_audit_reproducibility(audit_id)
    assert result["is_reproducible"] is False
    assert result["files"]["raw_data"]["exists"] is False

    # Save raw data
    temp_storage.save_raw_data(audit_id, {"status": "ok"})

    # Save audit report
    target = AuditTarget(
        owner="test-org",
        repo="test-repo",
        url="https://github.com/test-org/test-repo",
        default_branch="main",
    )
    scorecard = Scorecard(
        total_score=15,
        max_possible_score=20,
        criteria_scores=[],
    )
    report = AuditReport(
        audit_id=audit_id,
        target=target,
        decision=AuditDecision.APPROVE,
        scorecard=scorecard,
        hard_gates=[
            HardGateResult(
                gate_id="gate_license",
                name="License Check",
                status=HardGateStatus.PASS,
                severity="CRITICAL",
                reason="Permissive license present",
            )
        ],
        findings=[],
        evidence=[],
        summary="Test audit report",
    )
    temp_storage.save_audit_report(report)
    temp_storage.save_evidence(audit_id, [])
    # Create manifest
    manifest = temp_storage.create_audit_manifest(audit_id)
    assert manifest["manifest_version"] == "1.0"
    assert "raw_data.json" in manifest["files"]

    # Check reproducibility report
    repro = temp_storage.verify_audit_reproducibility(audit_id)
    assert repro["is_reproducible"] is True
    assert repro["integrity_status"] == "VERIFIED"
    assert repro["is_tampered"] is False
    assert "raw_data" in repro["files"]
    assert "sha256" in repro["files"]["raw_data"]
    assert repro["files"]["raw_data"]["size_bytes"] > 0


def _create_sample_audit(storage: StorageService, audit_id: str) -> None:
    """Helper to populate raw_data, audit, and evidence files for an audit ID."""
    storage.save_raw_data(audit_id, {"sample_key": "sample_value", "items": [1, 2, 3]})
    target = AuditTarget(
        owner="sample-owner",
        repo="sample-repo",
        url="https://github.com/sample-owner/sample-repo",
        default_branch="main",
    )
    scorecard = Scorecard(
        total_score=18,
        max_possible_score=20,
        criteria_scores=[],
    )
    report = AuditReport(
        audit_id=audit_id,
        target=target,
        decision=AuditDecision.APPROVE,
        scorecard=scorecard,
        hard_gates=[],
        findings=[],
        evidence=[],
        summary="Sample report for tamper verification.",
    )
    storage.save_audit_report(report)
    storage.save_evidence(audit_id, [])


def test_storage_manifest_creation_and_overwrite(temp_storage: StorageService) -> None:
    """Verify manifest creation records correct hashes/sizes and guards against accidental overwrite."""
    audit_id = "audit_manifest_gen_01"
    _create_sample_audit(temp_storage, audit_id)

    manifest = temp_storage.create_audit_manifest(audit_id)
    assert manifest["audit_id"] == audit_id
    assert manifest["manifest_version"] == "1.0"
    assert "raw_data.json" in manifest["files"]
    assert "audit.json" in manifest["files"]
    assert "evidence.json" in manifest["files"]

    # Overwrite without overwrite=True must raise FileExistsError
    with pytest.raises(FileExistsError, match="already exists"):
        temp_storage.create_audit_manifest(audit_id, overwrite=False)

    # Overwrite with overwrite=True succeeds
    manifest2 = temp_storage.create_audit_manifest(audit_id, overwrite=True)
    assert manifest2["audit_id"] == audit_id


def test_storage_manifest_missing_files_error(temp_storage: StorageService) -> None:
    """Verify manifest creation raises FileNotFoundError if any audit file is missing."""
    audit_id = "audit_incomplete_manifest_02"
    # Only save raw_data, not audit.json or evidence.json
    temp_storage.save_raw_data(audit_id, {"incomplete": True})

    with pytest.raises(FileNotFoundError, match="missing required files"):
        temp_storage.create_audit_manifest(audit_id)


def test_storage_verify_missing_manifest_predated_audit(temp_storage: StorageService) -> None:
    """Verify audits predating manifests report UNVERIFIED instead of falsely claiming integrity."""
    audit_id = "audit_legacy_predated_03"
    _create_sample_audit(temp_storage, audit_id)
    # Manifest is NOT generated

    repro = temp_storage.verify_audit_reproducibility(audit_id)
    assert repro["manifest_exists"] is False
    assert repro["integrity_status"] == "UNVERIFIED"
    assert repro["is_tampered"] is None
    assert repro["is_reproducible"] is False
    assert repro["files"]["raw_data"]["status"] == "UNVERIFIED"


def test_storage_tamper_detection_modified_file(temp_storage: StorageService) -> None:
    """Verify modifying raw_data.json or audit.json after saving is immediately detected as TAMPERED."""
    audit_id = "audit_tamper_mod_04"
    _create_sample_audit(temp_storage, audit_id)
    temp_storage.create_audit_manifest(audit_id)

    # Pre-check: verified
    repro = temp_storage.verify_audit_reproducibility(audit_id)
    assert repro["integrity_status"] == "VERIFIED"

    # Modify raw_data.json
    raw_path = temp_storage.base_data_dir / audit_id / "raw_data.json"
    raw_path.write_text('{"tampered": "hacked"}', encoding="utf-8")

    repro_tampered = temp_storage.verify_audit_reproducibility(audit_id)
    assert repro_tampered["manifest_exists"] is True
    assert repro_tampered["integrity_status"] == "TAMPERED"
    assert repro_tampered["is_tampered"] is True
    assert repro_tampered["is_reproducible"] is False
    assert "raw_data.json" in repro_tampered["tampered_files"]
    assert repro_tampered["files"]["raw_data"]["status"] in (
        "TAMPERED_CHECKSUM",
        "TAMPERED_SIZE_AND_CHECKSUM",
    )


def test_storage_tamper_detection_deleted_file(temp_storage: StorageService) -> None:
    """Verify deleting evidence.json after saving is flagged as TAMPERED and file DELETED."""
    audit_id = "audit_tamper_del_05"
    _create_sample_audit(temp_storage, audit_id)
    temp_storage.create_audit_manifest(audit_id)

    # Delete evidence.json
    ev_path = temp_storage.base_data_dir / audit_id / "evidence.json"
    ev_path.unlink()

    repro = temp_storage.verify_audit_reproducibility(audit_id)
    assert repro["integrity_status"] == "TAMPERED"
    assert repro["is_tampered"] is True
    assert repro["is_reproducible"] is False
    assert "evidence.json" in repro["missing_files"]
    assert repro["files"]["evidence"]["status"] == "DELETED"


def test_storage_tamper_detection_truncated_file(temp_storage: StorageService) -> None:
    """Verify truncating audit.json to 0 bytes is flagged as TAMPERED."""
    audit_id = "audit_tamper_trunc_06"
    _create_sample_audit(temp_storage, audit_id)
    temp_storage.create_audit_manifest(audit_id)

    # Truncate audit.json to 0 bytes
    audit_path = temp_storage.base_data_dir / audit_id / "audit.json"
    audit_path.write_text("", encoding="utf-8")

    repro = temp_storage.verify_audit_reproducibility(audit_id)
    assert repro["integrity_status"] == "TAMPERED"
    assert repro["is_tampered"] is True
    assert repro["is_reproducible"] is False
    assert "audit.json" in repro["tampered_files"]


def test_storage_tamper_detection_corrupted_file(temp_storage: StorageService) -> None:
    """Verify corrupting bytes of raw_data.json is flagged as TAMPERED."""
    audit_id = "audit_tamper_corrupt_07"
    _create_sample_audit(temp_storage, audit_id)
    temp_storage.create_audit_manifest(audit_id)

    # Corrupt raw_data.json by appending garbage
    raw_path = temp_storage.base_data_dir / audit_id / "raw_data.json"
    content = raw_path.read_text(encoding="utf-8")
    raw_path.write_text(content + "/* garbage injection */", encoding="utf-8")

    repro = temp_storage.verify_audit_reproducibility(audit_id)
    assert repro["integrity_status"] == "TAMPERED"
    assert repro["is_tampered"] is True
    assert repro["is_reproducible"] is False
    assert "raw_data.json" in repro["tampered_files"]


def test_storage_tamper_detection_malformed_manifest(temp_storage: StorageService) -> None:
    """Verify malformed or empty manifest.json produces CORRUPTED_MANIFEST and is_tampered=True."""
    audit_id = "audit_tamper_malformed_manifest_08"
    _create_sample_audit(temp_storage, audit_id)

    # Write malformed manifest
    manifest_path = temp_storage.base_data_dir / audit_id / "manifest.json"
    manifest_path.write_text("{ corrupt json: [", encoding="utf-8")

    repro = temp_storage.verify_audit_reproducibility(audit_id)
    assert repro["manifest_exists"] is True
    assert repro["integrity_status"] == "CORRUPTED_MANIFEST"
    assert repro["is_tampered"] is True
    assert repro["is_reproducible"] is False
    assert len(repro["manifest_errors"]) > 0

    # Write empty manifest (0 bytes)
    manifest_path.write_text("", encoding="utf-8")
    repro_empty = temp_storage.verify_audit_reproducibility(audit_id)
    assert repro_empty["integrity_status"] == "CORRUPTED_MANIFEST"
    assert repro_empty["is_tampered"] is True


def test_storage_tamper_detection_missing_manifest_entry(
    temp_storage: StorageService,
) -> None:
    """Verify manifest missing a tracked file entry is flagged as CORRUPTED_MANIFEST."""
    import json

    audit_id = "audit_tamper_missing_entry_09"
    _create_sample_audit(temp_storage, audit_id)
    manifest = temp_storage.create_audit_manifest(audit_id)

    # Delete 'evidence.json' entry from manifest
    del manifest["files"]["evidence.json"]
    manifest_path = temp_storage.base_data_dir / audit_id / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    repro = temp_storage.verify_audit_reproducibility(audit_id)
    assert repro["integrity_status"] == "CORRUPTED_MANIFEST"
    assert repro["is_tampered"] is True
    assert repro["is_reproducible"] is False
    assert any("evidence.json" in err for err in repro["manifest_errors"])
