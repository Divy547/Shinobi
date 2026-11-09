"""Storage service for persisting audit reports, raw payloads, and evidence."""

import hashlib
import json
import logging
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from repovet_mcp.config.settings import Settings, get_settings
from repovet_mcp.models.audit import AuditReport
from repovet_mcp.models.evidence import EvidenceItem
from repovet_mcp.services.security import validate_audit_id, validate_safe_subpath

logger = logging.getLogger("repovet_mcp.storage")

MANIFEST_FILENAME = "manifest.json"
MANIFEST_VERSION = "1.0"
TRACKED_AUDIT_FILES: dict[str, str] = {
    "raw_data": "raw_data.json",
    "audit": "audit.json",
    "evidence": "evidence.json",
}
SECURITY_NOTICE_MANIFEST = (
    "Unauthenticated local manifest. Detects subsequent file modifications, truncations, "
    "deletions, or corruption of local audit data. Does not defend against an attacker who "
    "possesses write access to both the manifest and data files."
)


class StorageCorruptionError(ValueError):
    """Raised when an audit file on disk is corrupted, truncated, or unparseable."""


class StorageService:
    """Handles structured JSON persistence with atomic writes, isolation, and path safety."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.base_data_dir = self.settings.data_dir
        self.base_data_dir.mkdir(parents=True, exist_ok=True)

    def _get_audit_dir(self, audit_id: str, create: bool = False) -> Path:
        """Return the directory path for a specific audit identifier with path traversal checks."""
        clean_id = validate_audit_id(audit_id)
        audit_dir = validate_safe_subpath(self.base_data_dir, clean_id)
        if create:
            audit_dir.mkdir(parents=True, exist_ok=True)
        return audit_dir

    def _atomic_write_json(self, target_path: Path, data: Any, indent: int = 2) -> None:
        """Write JSON atomically to disk using a temporary file in the same directory."""
        target_path.parent.mkdir(parents=True, exist_ok=True)
        prefix = f".{target_path.stem}_"
        # Create temp file in target's directory so rename is atomic across filesystem
        with tempfile.NamedTemporaryFile(
            mode="w",
            dir=target_path.parent,
            prefix=prefix,
            suffix=".tmp",
            delete=False,
            encoding="utf-8",
        ) as tmp:
            tmp_path = Path(tmp.name)
            try:
                if isinstance(data, str):
                    tmp.write(data)
                else:
                    json.dump(data, tmp, indent=indent, default=str)
                tmp.flush()
                os.fsync(tmp.fileno())
            except Exception:
                if tmp_path.exists():
                    tmp_path.unlink()
                raise

        # Atomically replace target path
        os.replace(tmp_path, target_path)

    def save_raw_data(self, audit_id: str, data: dict[str, Any]) -> Path:
        """Persist collected raw GitHub API payloads atomically."""
        audit_dir = self._get_audit_dir(audit_id, create=True)
        raw_path = audit_dir / "raw_data.json"
        self._atomic_write_json(raw_path, data)
        return raw_path

    def load_raw_data(self, audit_id: str) -> dict[str, Any]:
        """Load previously saved raw GitHub API payloads safely."""
        audit_dir = self._get_audit_dir(audit_id)
        raw_path = audit_dir / "raw_data.json"
        if not raw_path.exists():
            msg = f"No raw data found for audit ID: {audit_id}"
            raise FileNotFoundError(msg)

        try:
            with raw_path.open("r", encoding="utf-8") as f:
                content = f.read()
            if not content.strip():
                msg = f"Raw data file is empty (corrupted) for audit ID: {audit_id}"
                raise StorageCorruptionError(msg)
            data = json.loads(content)
            if not isinstance(data, dict):
                msg = f"Invalid raw data structure in {raw_path}: expected JSON object"
                raise StorageCorruptionError(msg)
            return data
        except json.JSONDecodeError as exc:
            msg = f"Malformed JSON in raw data file {raw_path}: {exc}"
            raise StorageCorruptionError(msg) from exc

    def save_audit_report(self, report: AuditReport) -> Path:
        """Persist the complete AuditReport model atomically."""
        audit_dir = self._get_audit_dir(report.audit_id, create=True)
        report_path = audit_dir / "audit.json"
        self._atomic_write_json(report_path, report.model_dump_json(indent=2))
        return report_path

    def load_audit_report(self, audit_id: str) -> AuditReport | None:
        """Load an AuditReport by ID, returning None if not found, or raising on corruption."""
        audit_dir = self._get_audit_dir(audit_id)
        report_path = audit_dir / "audit.json"
        if not report_path.exists():
            return None

        try:
            with report_path.open("r", encoding="utf-8") as f:
                content = f.read()
            if not content.strip():
                msg = f"Audit report file is empty (corrupted) for audit ID: {audit_id}"
                raise StorageCorruptionError(msg)
            return AuditReport.model_validate_json(content)
        except (json.JSONDecodeError, ValueError) as exc:
            msg = f"Corrupted or invalid AuditReport at {report_path}: {exc}"
            raise StorageCorruptionError(msg) from exc

    def save_evidence(self, audit_id: str, evidence: list[EvidenceItem]) -> Path:
        """Persist a list of collected EvidenceItem models atomically."""
        audit_dir = self._get_audit_dir(audit_id, create=True)
        evidence_path = audit_dir / "evidence.json"
        items_dict = [item.model_dump(mode="json") for item in evidence]
        self._atomic_write_json(evidence_path, items_dict)
        return evidence_path

    def load_evidence(self, audit_id: str) -> list[EvidenceItem]:
        """Load all evidence items associated with an audit ID safely."""
        audit_dir = self._get_audit_dir(audit_id)
        evidence_path = audit_dir / "evidence.json"
        if not evidence_path.exists():
            return []

        try:
            with evidence_path.open("r", encoding="utf-8") as f:
                content = f.read()
            if not content.strip():
                return []
            data = json.loads(content)
            if not isinstance(data, list):
                msg = f"Invalid evidence file structure at {evidence_path}: expected JSON array"
                raise StorageCorruptionError(msg)
            return [EvidenceItem.model_validate(item) for item in data]
        except (json.JSONDecodeError, ValueError) as exc:
            msg = f"Corrupted or invalid evidence items at {evidence_path}: {exc}"
            raise StorageCorruptionError(msg) from exc

    def audit_exists(self, audit_id: str) -> bool:
        """Check whether audit data exists on disk."""
        try:
            audit_dir = self._get_audit_dir(audit_id)
            if not audit_dir.exists():
                return False
            return (audit_dir / "raw_data.json").exists() or (audit_dir / "audit.json").exists()
        except ValueError:
            return False

    def create_audit_manifest(self, audit_id: str, overwrite: bool = False) -> dict[str, Any]:
        """Atomically persist an integrity manifest (manifest.json) recording SHA-256 and byte sizes.

        Must only be called after raw_data.json, audit.json, and evidence.json are successfully saved.
        """
        audit_dir = self._get_audit_dir(audit_id)
        manifest_path = audit_dir / MANIFEST_FILENAME

        if manifest_path.exists() and not overwrite:
            msg = (
                f"Integrity manifest already exists for audit ID '{audit_id}'. "
                "Pass overwrite=True to regenerate."
            )
            raise FileExistsError(msg)

        # Verify all tracked files exist before generating manifest
        missing_files = [
            fname for fname in TRACKED_AUDIT_FILES.values() if not (audit_dir / fname).exists()
        ]
        if missing_files:
            msg = (
                f"Cannot create audit manifest for '{audit_id}': missing required files: "
                f"{missing_files}"
            )
            raise FileNotFoundError(msg)

        files_manifest: dict[str, dict[str, Any]] = {}
        for fname in TRACKED_AUDIT_FILES.values():
            file_path = audit_dir / fname
            data = file_path.read_bytes()
            files_manifest[fname] = {
                "sha256": hashlib.sha256(data).hexdigest(),
                "size_bytes": len(data),
            }

        manifest_data: dict[str, Any] = {
            "manifest_version": MANIFEST_VERSION,
            "audit_id": audit_id,
            "created_at": datetime.now(UTC).isoformat(),
            "security_notice": SECURITY_NOTICE_MANIFEST,
            "files": files_manifest,
        }

        self._atomic_write_json(manifest_path, manifest_data)
        logger.info("Persisted integrity manifest for audit '%s' at %s", audit_id, manifest_path)
        return manifest_data

    def verify_audit_reproducibility(self, audit_id: str) -> dict[str, Any]:
        """Verify artifact integrity of stored audit contracts (raw_data.json, audit.json, evidence.json) against manifest.json for tamper detection.

        Detects modified files, truncated files, deleted files, corrupted manifests, and audits
        predating manifests. Evaluates artifact integrity rather than external execution reproducibility.
        Note: The compiled PDF report resides in reports/generated/ and is outside the data/ integrity manifest.
        Local manifests are not cryptographically signed and detect local file changes, not host-compromise attacks.
        """
        audit_dir = self._get_audit_dir(audit_id)
        manifest_path = audit_dir / MANIFEST_FILENAME

        files_status: dict[str, Any] = {}
        tampered_files: list[str] = []
        missing_files: list[str] = []
        manifest_errors: list[str] = []

        if not manifest_path.exists():
            # Check if any audit files exist at all
            existing_audit_files = [
                fname for fname in TRACKED_AUDIT_FILES.values() if (audit_dir / fname).exists()
            ]
            if not existing_audit_files:
                for key, _fname in TRACKED_AUDIT_FILES.items():
                    files_status[key] = {
                        "exists": False,
                        "status": "MISSING",
                        "size_bytes": 0,
                        "sha256": "",
                        "expected_sha256": None,
                        "expected_size_bytes": None,
                    }
                return {
                    "audit_id": audit_id,
                    "manifest_exists": False,
                    "integrity_status": "NOT_FOUND",
                    "is_tampered": None,
                    "is_reproducible": False,
                    "audit_dir": str(audit_dir),
                    "files": files_status,
                    "tampered_files": [],
                    "missing_files": list(TRACKED_AUDIT_FILES.values()),
                    "manifest_errors": ["No audit files or manifest found."],
                    "security_notice": SECURITY_NOTICE_MANIFEST,
                }

            # Audit files exist but manifest is absent (e.g. audit predates manifests)
            for key, fname in TRACKED_AUDIT_FILES.items():
                path = audit_dir / fname
                if path.exists():
                    stat = path.stat()
                    sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
                    files_status[key] = {
                        "exists": True,
                        "size_bytes": stat.st_size,
                        "sha256": sha256,
                        "expected_sha256": None,
                        "expected_size_bytes": None,
                        "status": "UNVERIFIED",
                    }
                else:
                    files_status[key] = {
                        "exists": False,
                        "size_bytes": 0,
                        "sha256": "",
                        "expected_sha256": None,
                        "expected_size_bytes": None,
                        "status": "MISSING",
                    }
                    missing_files.append(fname)

            return {
                "audit_id": audit_id,
                "manifest_exists": False,
                "integrity_status": "UNVERIFIED",
                "is_tampered": None,
                "is_reproducible": False,
                "audit_dir": str(audit_dir),
                "files": files_status,
                "tampered_files": [],
                "missing_files": missing_files,
                "manifest_errors": [
                    "Audit lacks an integrity manifest (predates manifest generation or manifest was deleted)."
                ],
                "security_notice": SECURITY_NOTICE_MANIFEST,
            }

        # Manifest exists: load and parse
        manifest_data: dict[str, Any] = {}
        manifest_corrupted = False
        try:
            content = manifest_path.read_text(encoding="utf-8")
            if not content.strip():
                manifest_corrupted = True
                manifest_errors.append("Manifest file is empty (0 bytes).")
            else:
                parsed = json.loads(content)
                if not isinstance(parsed, dict):
                    manifest_corrupted = True
                    manifest_errors.append("Manifest root must be a JSON object.")
                elif "files" not in parsed or not isinstance(parsed["files"], dict):
                    manifest_corrupted = True
                    manifest_errors.append("Manifest is missing 'files' dictionary.")
                else:
                    manifest_data = parsed
        except Exception as exc:
            manifest_corrupted = True
            manifest_errors.append(f"Malformed manifest JSON: {exc}")

        if manifest_corrupted:
            for key, fname in TRACKED_AUDIT_FILES.items():
                path = audit_dir / fname
                if path.exists():
                    files_status[key] = {
                        "exists": True,
                        "size_bytes": path.stat().st_size,
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        "expected_sha256": None,
                        "expected_size_bytes": None,
                        "status": "UNVERIFIABLE_CORRUPTED_MANIFEST",
                    }
                else:
                    files_status[key] = {
                        "exists": False,
                        "size_bytes": 0,
                        "sha256": "",
                        "expected_sha256": None,
                        "expected_size_bytes": None,
                        "status": "MISSING",
                    }
                    missing_files.append(fname)

            return {
                "audit_id": audit_id,
                "manifest_exists": True,
                "integrity_status": "CORRUPTED_MANIFEST",
                "is_tampered": True,
                "is_reproducible": False,
                "audit_dir": str(audit_dir),
                "files": files_status,
                "tampered_files": [],
                "missing_files": missing_files,
                "manifest_errors": manifest_errors,
                "security_notice": SECURITY_NOTICE_MANIFEST,
            }

        # Validate each tracked file against manifest
        manifest_files = manifest_data.get("files", {})
        for key, fname in TRACKED_AUDIT_FILES.items():
            if fname not in manifest_files or not isinstance(manifest_files[fname], dict):
                manifest_errors.append(f"Manifest missing entry for tracked file '{fname}'.")
                tampered_files.append(fname)
                path = audit_dir / fname
                files_status[key] = {
                    "exists": path.exists(),
                    "size_bytes": path.stat().st_size if path.exists() else 0,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest()
                    if path.exists()
                    else "",
                    "expected_sha256": None,
                    "expected_size_bytes": None,
                    "status": "MISSING_FROM_MANIFEST",
                }
                continue

            expected_entry = manifest_files[fname]
            expected_sha256 = expected_entry.get("sha256")
            expected_size = expected_entry.get("size_bytes")

            path = audit_dir / fname
            if not path.exists():
                missing_files.append(fname)
                tampered_files.append(fname)
                files_status[key] = {
                    "exists": False,
                    "size_bytes": 0,
                    "sha256": "",
                    "expected_sha256": expected_sha256,
                    "expected_size_bytes": expected_size,
                    "status": "DELETED",
                }
                continue

            current_bytes = path.read_bytes()
            current_size = len(current_bytes)
            current_sha256 = hashlib.sha256(current_bytes).hexdigest()

            sha_match = current_sha256 == expected_sha256
            size_match = current_size == expected_size

            if sha_match and size_match:
                file_status = "MATCH"
            elif not sha_match and not size_match:
                file_status = "TAMPERED_SIZE_AND_CHECKSUM"
                tampered_files.append(fname)
            elif not sha_match:
                file_status = "TAMPERED_CHECKSUM"
                tampered_files.append(fname)
            else:
                file_status = "TAMPERED_SIZE"
                tampered_files.append(fname)

            files_status[key] = {
                "exists": True,
                "size_bytes": current_size,
                "sha256": current_sha256,
                "expected_sha256": expected_sha256,
                "expected_size_bytes": expected_size,
                "status": file_status,
            }

        if manifest_errors:
            integrity_status = "CORRUPTED_MANIFEST"
            is_tampered = True
            is_reproducible = False
        elif missing_files or tampered_files:
            integrity_status = "TAMPERED"
            is_tampered = True
            is_reproducible = False
        else:
            integrity_status = "VERIFIED"
            is_tampered = False
            is_reproducible = True

        return {
            "audit_id": audit_id,
            "manifest_exists": True,
            "integrity_status": integrity_status,
            "is_tampered": is_tampered,
            "is_reproducible": is_reproducible,
            "audit_dir": str(audit_dir),
            "files": files_status,
            "tampered_files": tampered_files,
            "missing_files": missing_files,
            "manifest_errors": manifest_errors,
            "security_notice": SECURITY_NOTICE_MANIFEST,
        }
