"""Hard gates service for evaluating mandatory repository eligibility conditions."""

from datetime import UTC, datetime
from typing import Any

from repovet_mcp.models.audit import HardGateResult, HardGateStatus
from repovet_mcp.models.evidence import EvidenceConfidence, EvidenceItem, EvidenceSourceType
from repovet_mcp.models.findings import Finding, FindingCategory, FindingSeverity


class HardGatesService:
    """Evaluates mandatory gating criteria (license, activity, safety, builds)."""

    def evaluate_gates(
        self,
        audit_id: str,
        activity_metrics: dict[str, Any],
        ci_security_metrics: dict[str, Any],
        raw_repository: dict[str, Any],
    ) -> tuple[list[HardGateResult], list[EvidenceItem], list[Finding]]:
        """Evaluate hard eligibility conditions and return results, evidence, and findings."""
        now = datetime.now(UTC)
        results: list[HardGateResult] = []
        evidence: list[EvidenceItem] = []
        findings: list[Finding] = []

        repo_url = raw_repository.get("html_url", "")

        # -------------------------------------------------------------
        # 1. License Gate: Must have verified OSI-approved open source license
        # -------------------------------------------------------------
        spdx_id = ci_security_metrics.get("license_spdx")
        is_osi = ci_security_metrics.get("is_osi_approved", False)

        ev_license = EvidenceItem(
            id=f"{audit_id}_ev_gate_license",
            phase="phase_1_identity_and_licensing",
            source_type=EvidenceSourceType.GITHUB_API_REST,
            source_endpoint=f"{repo_url}/blob/main/LICENSE",
            collected_at=now,
            confidence=EvidenceConfidence.CONFIRMED,
            summary=f"Repository license is {spdx_id or 'missing/unrecognized'} (OSI-approved: {is_osi}).",
            verified=True,
        )
        evidence.append(ev_license)

        if is_osi:
            results.append(
                HardGateResult(
                    gate_id="unlicensed_repository",
                    name="Open Source License Validity",
                    status=HardGateStatus.PASS,
                    severity="CRITICAL",
                    reason=f"Repository has a recognized OSI-approved license ({spdx_id}).",
                    evidence_ids=[ev_license.id],
                )
            )
        elif spdx_id:
            results.append(
                HardGateResult(
                    gate_id="unlicensed_repository",
                    name="Open Source License Validity",
                    status=HardGateStatus.UNKNOWN,
                    severity="HIGH",
                    reason=f"License '{spdx_id}' is present but not recognized in standard OSI list; requires manual legal review.",
                    evidence_ids=[ev_license.id],
                )
            )
        else:
            results.append(
                HardGateResult(
                    gate_id="unlicensed_repository",
                    name="Open Source License Validity",
                    status=HardGateStatus.FAIL,
                    severity="CRITICAL",
                    reason="No open-source license detected. Code defaults to All Rights Reserved, legally prohibiting external contributions.",
                    evidence_ids=[ev_license.id],
                )
            )
            findings.append(
                Finding(
                    id=f"{audit_id}_find_unlicensed",
                    phase="phase_1_identity_and_licensing",
                    criterion_id="security_and_licensing",
                    severity=FindingSeverity.CRITICAL,
                    category=FindingCategory.LICENSING,
                    title="Missing Open Source License",
                    description="The repository does not contain an OSI-approved license file, creating complete legal liability for contributors.",
                    evidence_ids=[ev_license.id],
                    remediation_recommendation="Add a standard open-source license (such as MIT or Apache-2.0).",
                )
            )

        # -------------------------------------------------------------
        # 2. Dormancy Gate: Must have had commits or activity in the last 18 months
        # -------------------------------------------------------------
        days_since_commit = activity_metrics.get("days_since_latest_commit", 9999)
        is_archived = activity_metrics.get("is_archived", False)
        is_abandoned = activity_metrics.get("is_abandoned", False)

        ev_activity = EvidenceItem(
            id=f"{audit_id}_ev_gate_dormancy",
            phase="phase_2_vitality_and_pulse",
            source_type=EvidenceSourceType.GITHUB_API_REST,
            source_endpoint=f"{repo_url}/commits",
            collected_at=now,
            confidence=EvidenceConfidence.CONFIRMED,
            summary=f"Latest commit was {days_since_commit} days ago. Repository archived status: {is_archived}.",
            verified=True,
        )
        evidence.append(ev_activity)

        if is_archived:
            results.append(
                HardGateResult(
                    gate_id="abandoned_repository",
                    name="Repository Vitality & Maintenance Status",
                    status=HardGateStatus.FAIL,
                    severity="CRITICAL",
                    reason="Repository has been officially archived on GitHub (read-only).",
                    evidence_ids=[ev_activity.id],
                )
            )
            findings.append(
                Finding(
                    id=f"{audit_id}_find_archived",
                    phase="phase_2_vitality_and_pulse",
                    criterion_id="commit_activity",
                    severity=FindingSeverity.CRITICAL,
                    category=FindingCategory.ACTIVITY,
                    title="Repository is Archived",
                    description="Repository has been permanently archived by the maintainers.",
                    evidence_ids=[ev_activity.id],
                )
            )
        elif is_abandoned:
            results.append(
                HardGateResult(
                    gate_id="abandoned_repository",
                    name="Repository Vitality & Maintenance Status",
                    status=HardGateStatus.FAIL,
                    severity="CRITICAL",
                    reason=f"Repository has been dormant for {days_since_commit} days (>18 months) with zero maintainer commits.",
                    evidence_ids=[ev_activity.id],
                )
            )
            findings.append(
                Finding(
                    id=f"{audit_id}_find_dormant",
                    phase="phase_2_vitality_and_pulse",
                    criterion_id="commit_activity",
                    severity=FindingSeverity.CRITICAL,
                    category=FindingCategory.ACTIVITY,
                    title="Abandoned / Dormant Codebase",
                    description=f"Zero commits for {days_since_commit} days indicates the project is no longer actively maintained.",
                    evidence_ids=[ev_activity.id],
                )
            )
        else:
            results.append(
                HardGateResult(
                    gate_id="abandoned_repository",
                    name="Repository Vitality & Maintenance Status",
                    status=HardGateStatus.PASS,
                    severity="CRITICAL",
                    reason=f"Repository is active. Latest commit was {days_since_commit} days ago.",
                    evidence_ids=[ev_activity.id],
                )
            )

        # -------------------------------------------------------------
        # 3. Default Branch CI Gate: CI must not be persistently broken
        # -------------------------------------------------------------
        ci_passing = ci_security_metrics.get("ci_passing_on_default_branch")
        has_ci = ci_security_metrics.get("has_ci_workflows", False)

        ev_ci = EvidenceItem(
            id=f"{audit_id}_ev_gate_ci",
            phase="phase_7_ci_cd_and_testing",
            source_type=EvidenceSourceType.GITHUB_API_REST,
            source_endpoint=f"{repo_url}/actions",
            collected_at=now,
            confidence=EvidenceConfidence.CONFIRMED,
            summary=f"Automated CI workflows configured: {has_ci}. Passing on default branch: {ci_passing}.",
            verified=True,
        )
        evidence.append(ev_ci)

        if not has_ci:
            results.append(
                HardGateResult(
                    gate_id="failing_default_branch",
                    name="Default Branch CI Status",
                    status=HardGateStatus.UNKNOWN,
                    severity="HIGH",
                    reason="No automated GitHub Actions CI workflows detected; automated test health is unknown.",
                    evidence_ids=[ev_ci.id],
                )
            )
        elif ci_passing is True:
            results.append(
                HardGateResult(
                    gate_id="failing_default_branch",
                    name="Default Branch CI Status",
                    status=HardGateStatus.PASS,
                    severity="HIGH",
                    reason="Default branch continuous integration workflow runs are passing.",
                    evidence_ids=[ev_ci.id],
                )
            )
        elif ci_passing is False:
            results.append(
                HardGateResult(
                    gate_id="failing_default_branch",
                    name="Default Branch CI Status",
                    status=HardGateStatus.FAIL,
                    severity="HIGH",
                    reason="Latest continuous integration workflow run on the default branch failed.",
                    evidence_ids=[ev_ci.id],
                )
            )
            findings.append(
                Finding(
                    id=f"{audit_id}_find_broken_ci",
                    phase="phase_7_ci_cd_and_testing",
                    criterion_id="ci_and_code_quality",
                    severity=FindingSeverity.HIGH,
                    category=FindingCategory.CI_CD,
                    title="Failing Default Branch Build",
                    description="Latest automated CI workflow run on the default branch has failed.",
                    evidence_ids=[ev_ci.id],
                    remediation_recommendation="Investigate failed workflow runs and verify test suite passes locally.",
                )
            )
        else:
            results.append(
                HardGateResult(
                    gate_id="failing_default_branch",
                    name="Default Branch CI Status",
                    status=HardGateStatus.UNKNOWN,
                    severity="HIGH",
                    reason="CI workflows exist, but no recent workflow run logs were retrieved.",
                    evidence_ids=[ev_ci.id],
                )
            )

        # -------------------------------------------------------------
        # 4. Safe Read-Only Installation & Code Pattern Gate
        # -------------------------------------------------------------
        suspicious = ci_security_metrics.get("suspicious_install_scripts", False)
        reasons = ci_security_metrics.get("suspicious_reasons", [])

        ev_safety = EvidenceItem(
            id=f"{audit_id}_ev_gate_safety",
            phase="phase_8_dependencies_and_security",
            source_type=EvidenceSourceType.STATIC_ANALYSIS,
            source_endpoint=repo_url,
            collected_at=now,
            confidence=EvidenceConfidence.CONFIRMED,
            summary=f"Read-only installation safety scan result: suspicious={suspicious}.",
            verified=True,
        )
        evidence.append(ev_safety)

        if suspicious:
            results.append(
                HardGateResult(
                    gate_id="untrusted_malicious_code",
                    name="Installation & Binary Safety",
                    status=HardGateStatus.FAIL,
                    severity="CRITICAL",
                    reason=f"Suspicious files detected in repository root: {', '.join(reasons)}",
                    evidence_ids=[ev_safety.id],
                )
            )
            findings.append(
                Finding(
                    id=f"{audit_id}_find_suspicious_binaries",
                    phase="phase_8_dependencies_and_security",
                    severity=FindingSeverity.CRITICAL,
                    category=FindingCategory.SECURITY,
                    title="Suspicious Binaries in Root",
                    description="Precompiled binaries found in repository root. Untrusted code execution policy forbids automated running.",
                    evidence_ids=[ev_safety.id],
                )
            )
        else:
            results.append(
                HardGateResult(
                    gate_id="untrusted_malicious_code",
                    name="Installation & Binary Safety",
                    status=HardGateStatus.PASS,
                    severity="CRITICAL",
                    reason="No suspicious precompiled binaries or high-risk root installation anomalies detected.",
                    evidence_ids=[ev_safety.id],
                )
            )

        return results, evidence, findings
