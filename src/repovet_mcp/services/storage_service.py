"""Storage service for persisting audit reports, raw payloads, and evidence."""

import json
from pathlib import Path
from typing import Any

from repovet_mcp.config.settings import Settings, get_settings
from repovet_mcp.models.audit import AuditReport
from repovet_mcp.models.evidence import EvidenceItem


class StorageService:
    """Handles structured JSON persistence for repository audits and evidence."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.base_data_dir = self.settings.data_dir
        self.base_data_dir.mkdir(parents=True, exist_ok=True)

    def _get_audit_dir(self, audit_id: str) -> Path:
        """Return the directory path for a specific audit identifier."""
        # Sanitize audit_id to prevent path traversal
        clean_id = "".join(c for c in audit_id if c.isalnum() or c in ("-", "_"))
        audit_dir = self.base_data_dir / clean_id
        audit_dir.mkdir(parents=True, exist_ok=True)
        return audit_dir

    def save_raw_data(self, audit_id: str, data: dict[str, Any]) -> Path:
        """Persist collected raw GitHub API payloads."""
        audit_dir = self._get_audit_dir(audit_id)
        raw_path = audit_dir / "raw_data.json"
        with raw_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        return raw_path

    def load_raw_data(self, audit_id: str) -> dict[str, Any]:
        """Load previously saved raw GitHub API payloads."""
        audit_dir = self._get_audit_dir(audit_id)
        raw_path = audit_dir / "raw_data.json"
        if not raw_path.exists():
            msg = f"No raw data found for audit ID: {audit_id}"
            raise FileNotFoundError(msg)
        with raw_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                msg = f"Invalid raw data structure in {raw_path}"
                raise ValueError(msg)
            return data

    def save_audit_report(self, report: AuditReport) -> Path:
        """Persist the complete AuditReport model."""
        audit_dir = self._get_audit_dir(report.audit_id)
        report_path = audit_dir / "audit.json"
        with report_path.open("w", encoding="utf-8") as f:
            f.write(report.model_dump_json(indent=2))
        return report_path

    def load_audit_report(self, audit_id: str) -> AuditReport | None:
        """Load an AuditReport by ID, returning None if not found."""
        audit_dir = self._get_audit_dir(audit_id)
        report_path = audit_dir / "audit.json"
        if not report_path.exists():
            return None
        with report_path.open("r", encoding="utf-8") as f:
            return AuditReport.model_validate_json(f.read())

    def save_evidence(self, audit_id: str, evidence: list[EvidenceItem]) -> Path:
        """Persist a list of collected EvidenceItem models."""
        audit_dir = self._get_audit_dir(audit_id)
        evidence_path = audit_dir / "evidence.json"
        items_dict = [item.model_dump(mode="json") for item in evidence]
        with evidence_path.open("w", encoding="utf-8") as f:
            json.dump(items_dict, f, indent=2)
        return evidence_path

    def load_evidence(self, audit_id: str) -> list[EvidenceItem]:
        """Load all evidence items associated with an audit ID."""
        audit_dir = self._get_audit_dir(audit_id)
        evidence_path = audit_dir / "evidence.json"
        if not evidence_path.exists():
            return []
        with evidence_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, list):
                return []
            return [EvidenceItem.model_validate(item) for item in data]

    def audit_exists(self, audit_id: str) -> bool:
        """Check whether audit data exists on disk."""
        audit_dir = self._get_audit_dir(audit_id)
        return (audit_dir / "raw_data.json").exists() or (audit_dir / "audit.json").exists()
