"""Evidence validation service verifying grounding, citations, and confidence taxonomy."""

from typing import Any

from repovet_mcp.models.audit import AuditReport
from repovet_mcp.models.evidence import EvidenceConfidence, EvidenceItem


class EvidenceValidator:
    """Validates evidence structure, citation grounding, and anti-hallucination compliance."""

    def validate_audit_evidence(
        self,
        audit_report: AuditReport,
    ) -> dict[str, Any]:
        """Verify that all scorecard criteria and findings are backed by primary evidence."""
        evidence_by_id: dict[str, EvidenceItem] = {e.id: e for e in audit_report.evidence}
        validation_messages: list[str] = []
        unsupported_findings: list[str] = []
        unsupported_criteria: list[str] = []

        confidence_counts = {
            EvidenceConfidence.CONFIRMED.value: 0,
            EvidenceConfidence.INFERRED.value: 0,
            EvidenceConfidence.UNKNOWN.value: 0,
        }

        # 1. Validate Evidence Items Structure
        for ev in audit_report.evidence:
            conf_val = ev.confidence.value
            confidence_counts[conf_val] = confidence_counts.get(conf_val, 0) + 1

            if not ev.summary or len(ev.summary.strip()) < 5:
                validation_messages.append(f"Evidence {ev.id} has insufficient summary.")
            if not ev.source_endpoint:
                validation_messages.append(f"Evidence {ev.id} lacks a source endpoint citation.")

        # 2. Validate Findings Grounding
        for finding in audit_report.findings:
            if not finding.evidence_ids:
                unsupported_findings.append(finding.id)
                validation_messages.append(
                    f"Finding '{finding.title}' ({finding.id}) has no associated evidence IDs."
                )
            else:
                for eid in finding.evidence_ids:
                    if eid not in evidence_by_id:
                        unsupported_findings.append(finding.id)
                        validation_messages.append(
                            f"Finding '{finding.title}' references missing evidence ID: {eid}"
                        )

        # 3. Validate Scorecard Grounding
        for crit in audit_report.scorecard.criteria_scores:
            if not crit.evidence_ids:
                unsupported_criteria.append(crit.criterion_id)
                validation_messages.append(
                    f"Scorecard criterion '{crit.name}' ({crit.criterion_id}) has no supporting evidence items."
                )
            else:
                for eid in crit.evidence_ids:
                    if eid not in evidence_by_id:
                        unsupported_criteria.append(crit.criterion_id)
                        validation_messages.append(
                            f"Scorecard criterion '{crit.name}' references non-existent evidence ID: {eid}"
                        )

        is_valid = len(unsupported_findings) == 0 and len(unsupported_criteria) == 0

        return {
            "audit_id": audit_report.audit_id,
            "is_valid": is_valid,
            "total_evidence_count": len(audit_report.evidence),
            "total_findings_count": len(audit_report.findings),
            "confidence_counts": confidence_counts,
            "unsupported_findings": list(set(unsupported_findings)),
            "unsupported_criteria": list(set(unsupported_criteria)),
            "validation_messages": validation_messages,
        }
