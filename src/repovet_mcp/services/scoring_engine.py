"""Deterministic scoring engine implementing the 10 scorecard criteria and decision logic."""

import logging
from typing import Any

from repovet_mcp.config.settings import Settings, get_settings
from repovet_mcp.models.audit import (
    AuditDecision,
    CriterionScore,
    HardGateResult,
    HardGateStatus,
    Scorecard,
)
from repovet_mcp.models.evidence import EvidenceItem

logger = logging.getLogger("repovet_mcp.scoring")


class ScoringEngine:
    """Calculates reproducible, evidence-grounded scores across the ten vetting criteria."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def evaluate_scorecard(
        self,
        audit_id: str,
        activity_metrics: dict[str, Any],
        contributor_metrics: dict[str, Any],
        responsiveness_metrics: dict[str, Any],
        newcomer_metrics: dict[str, Any],
        documentation_metrics: dict[str, Any],
        ci_security_metrics: dict[str, Any],
        hard_gates: list[HardGateResult],
        evidence_list: list[EvidenceItem],
        raw_repository: dict[str, Any],
    ) -> tuple[Scorecard, AuditDecision, list[str]]:
        """Compute the 10 criteria scores, sum total, and evaluate final decision verdict."""
        logger.debug("Evaluating scorecard for audit ID: %s", audit_id)
        # Look up dedicated criterion evidence IDs with fallbacks
        c1_ev_id = next(
            (
                e.id
                for e in evidence_list
                if "c1_gsoc" in e.id or e.phase == "phase_9_mentorship_and_gsoc"
            ),
            None,
        )
        c2_ev_id = next(
            (
                e.id
                for e in evidence_list
                if "c2_commits" in e.id
                or (e.phase == "phase_2_vitality_and_pulse" and "gate" not in e.id)
            ),
            None,
        )
        c3_ev_id = next(
            (
                e.id
                for e in evidence_list
                if "c3_contributors" in e.id or e.phase == "phase_3_governance_and_culture"
            ),
            None,
        )
        c4_ev_id = next(
            (
                e.id
                for e in evidence_list
                if "c4_pr_response" in e.id or e.phase == "phase_4_responsiveness_and_velocity"
            ),
            None,
        )
        c5_ev_id = next(
            (
                e.id
                for e in evidence_list
                if "c5_issue_response" in e.id or e.phase == "phase_4_responsiveness_and_velocity"
            ),
            c4_ev_id,
        )
        c6_ev_id = next(
            (
                e.id
                for e in evidence_list
                if "c6_newcomer_prs" in e.id or e.phase == "phase_6_issue_hygiene_and_accessibility"
            ),
            None,
        )
        c7_ev_id = next(
            (
                e.id
                for e in evidence_list
                if "c7_beginner_issues" in e.id
                or e.phase == "phase_6_issue_hygiene_and_accessibility"
            ),
            c6_ev_id,
        )
        c8_ev_id = next(
            (
                e.id
                for e in evidence_list
                if "c8_docs" in e.id or e.phase == "phase_5_documentation_and_onboarding"
            ),
            None,
        )
        c9_ev_id = next(
            (
                e.id
                for e in evidence_list
                if "c9_ci" in e.id
                or (e.phase == "phase_7_ci_cd_and_testing" and "gate" not in e.id)
            ),
            None,
        )
        c10_ev_id = next(
            (
                e.id
                for e in evidence_list
                if "c10_community" in e.id or e.phase == "phase_3_governance_and_culture"
            ),
            c3_ev_id,
        )

        criteria_scores: list[CriterionScore] = []

        # ---------------------------------------------------------------------
        # 1. GSoC History & Mentorship Track Record (phase_9_mentorship_and_gsoc)
        # ---------------------------------------------------------------------
        has_gsoc_doc = documentation_metrics.get("has_gsoc_doc", False)
        gsoc_doc_path = documentation_metrics.get("gsoc_doc_path")

        if has_gsoc_doc:
            path_str = f" ({gsoc_doc_path})" if gsoc_doc_path else ""
            if documentation_metrics.get("has_contributing") and documentation_metrics.get(
                "has_readme"
            ):
                c1_score = 2
                c1_rationale = (
                    f"Dedicated GSoC / project ideas document{path_str} and structured contribution onboarding "
                    "verified in repository contents."
                )
            else:
                c1_score = 1
                c1_rationale = (
                    f"Project ideas or mentorship document{path_str} detected, but formal organization acceptance "
                    "requires manual verification against official GSoC archives."
                )
        else:
            c1_score = 0
            c1_rationale = (
                "Missing historical GSoC archive evidence: no dedicated GSoC or project ideas document "
                "verified in repository contents (checked root, docs/, docs/outreach/, .github/). "
                "Note: repository-level absence does not confirm absence of GSoC "
                "participation, as projects may participate under an umbrella foundation (e.g., CNCF, Apache Foundation); "
                "marked UNKNOWN pending manual verification against official GSoC archives."
            )

        criteria_scores.append(
            CriterionScore(
                criterion_id="gsoc_history",
                name="GSoC History & Mentorship Track Record",
                phase="phase_9_mentorship_and_gsoc",
                score=c1_score,
                max_score=2,
                rationale=c1_rationale,
                evidence_ids=[c1_ev_id] if c1_ev_id else [],
            )
        )

        # ---------------------------------------------------------------------
        # 2. Commit Activity & Maintenance Cadence (phase_2_vitality_and_pulse)
        # ---------------------------------------------------------------------
        commit_history_available = activity_metrics.get("commit_history_available", True)
        days_since_commit = activity_metrics.get("days_since_latest_commit")
        commits_90d = activity_metrics.get("commits_last_90d", 0)

        if not commit_history_available or days_since_commit is None:
            c2_score = 0
            c2_rationale = (
                "Commit history could not be retrieved from GitHub API; maintenance cadence "
                "is UNKNOWN and requires manual verification."
            )
        elif days_since_commit <= 30 and commits_90d >= 10:
            c2_score = 2
            c2_rationale = f"Vibrant activity: last commit {days_since_commit} days ago with {commits_90d} commits in the last 90 days."
        elif days_since_commit <= 180 and commits_90d >= 1:
            c2_score = 1
            c2_rationale = f"Moderate activity: last commit was {days_since_commit} days ago with sporadic maintenance."
        else:
            c2_score = 0
            c2_rationale = f"Dormant/Abandoned: {days_since_commit} days since last commit."

        criteria_scores.append(
            CriterionScore(
                criterion_id="commit_activity",
                name="Commit Activity & Maintenance Cadence",
                phase="phase_2_vitality_and_pulse",
                score=c2_score,
                max_score=2,
                rationale=c2_rationale,
                evidence_ids=[c2_ev_id] if c2_ev_id else [],
            )
        )

        # ---------------------------------------------------------------------
        # 3. Contributor Spread & Decentralization (phase_3_governance_and_culture)
        # ---------------------------------------------------------------------
        top_contrib_share = contributor_metrics.get("top_contributor_share", 100.0)
        total_contributors = contributor_metrics.get("total_contributors", 0)

        if total_contributors >= 5 and top_contrib_share < 50.0:
            c3_score = 2
            c3_rationale = f"Healthy decentralization: {total_contributors} contributors, top contributor accounts for {top_contrib_share}%."
        elif total_contributors >= 2 and top_contrib_share <= 85.0:
            c3_score = 1
            c3_rationale = f"Moderate spread: {total_contributors} contributors, top contributor accounts for {top_contrib_share}%."
        else:
            c3_score = 0
            c3_rationale = f"High bus factor risk: top contributor dominates {top_contrib_share}% of recorded contributions."

        criteria_scores.append(
            CriterionScore(
                criterion_id="contributor_spread",
                name="Contributor Spread & Decentralization",
                phase="phase_3_governance_and_culture",
                score=c3_score,
                max_score=2,
                rationale=c3_rationale,
                evidence_ids=[c3_ev_id] if c3_ev_id else [],
            )
        )

        # ---------------------------------------------------------------------
        # 4. PR First Human Response Time (phase_4_responsiveness_and_velocity)
        # ---------------------------------------------------------------------
        median_pr_hours = responsiveness_metrics.get("median_pr_first_response_hours")
        prs_sampled = responsiveness_metrics.get("prs_with_human_response_count", 0)

        if prs_sampled > 0 and median_pr_hours is not None and median_pr_hours <= 72.0:
            c4_score = 2
            c4_rationale = f"Fast review turnaround: median first human response is {median_pr_hours} hours (<72h)."
        elif (
            prs_sampled > 0 and median_pr_hours is not None and median_pr_hours <= 336.0
        ):  # <= 14 days
            c4_score = 1
            c4_rationale = (
                f"Moderate review speed: median first human response is {median_pr_hours} hours."
            )
        elif prs_sampled > 0 and median_pr_hours is not None:
            c4_score = 0
            c4_rationale = f"Slow or absent review feedback: median first human response is {median_pr_hours} hours (>14 days)."
        else:
            # No PR human response sample available
            total_prs_evaluated = responsiveness_metrics.get("total_prs_evaluated")
            if total_prs_evaluated is None:
                total_prs_evaluated = newcomer_metrics.get("total_prs_evaluated")
            if total_prs_evaluated is None:
                total_prs_evaluated = len(raw_repository.get("pull_requests", []))
            c4_score = 1 if total_prs_evaluated == 0 else 0
            c4_rationale = "Unobserved: No human pull request review samples were observed in evaluated pull requests."

        criteria_scores.append(
            CriterionScore(
                criterion_id="pr_first_response",
                name="PR First Human Response Time",
                phase="phase_4_responsiveness_and_velocity",
                score=c4_score,
                max_score=2,
                rationale=c4_rationale,
                evidence_ids=[c4_ev_id] if c4_ev_id else [],
            )
        )

        # ---------------------------------------------------------------------
        # 5. Issue Human Response Rate (phase_4_responsiveness_and_velocity)
        # ---------------------------------------------------------------------
        unanswered_pct = responsiveness_metrics.get("unanswered_issue_percentage", 0.0)
        open_issues = responsiveness_metrics.get("open_issues_evaluated", 0)

        if open_issues == 0:
            c5_score = 2
            c5_rationale = "No open issue backlog; repository issue tracker is clear."
        elif unanswered_pct < 25.0:
            c5_score = 2
            c5_rationale = f"High issue triage rate: only {unanswered_pct}% of issues remain without human response."
        elif unanswered_pct <= 50.0:
            c5_score = 1
            c5_rationale = f"Moderate triage: {unanswered_pct}% of issues currently have no human maintainer response."
        else:
            c5_score = 0
            c5_rationale = f"High issue backlog neglect: {unanswered_pct}% of issues remain completely unanswered."

        criteria_scores.append(
            CriterionScore(
                criterion_id="issue_response_rate",
                name="Issue Human Response Rate",
                phase="phase_4_responsiveness_and_velocity",
                score=c5_score,
                max_score=2,
                rationale=c5_rationale,
                evidence_ids=[c5_ev_id] if c5_ev_id else [],
            )
        )

        # -------------------------------------------------------------
        # 6. Newcomer PRs Acceptance & Merge Rate (phase_6_issue_hygiene_and_accessibility)
        # -------------------------------------------------------------
        newcomer_merged = newcomer_metrics.get("newcomer_prs_merged", 0)
        newcomer_closed = newcomer_metrics.get("newcomer_prs_closed", 0)
        newcomer_sample = newcomer_metrics.get("newcomer_prs_sample_count", 0)
        newcomer_rate = newcomer_metrics.get("newcomer_merge_rate", 0.0)
        total_prs = responsiveness_metrics.get("total_prs_evaluated")
        if total_prs is None:
            total_prs = newcomer_metrics.get("total_prs_evaluated")
        if total_prs is None:
            total_prs = len(raw_repository.get("pull_requests", []))

        if newcomer_merged >= 5 or (newcomer_rate >= 60.0 and newcomer_merged >= 2):
            c6_score = 2
            c6_rationale = (
                f"Active newcomer acceptance: {newcomer_merged} merged out of {newcomer_closed} closed newcomer PRs "
                f"({newcomer_rate}% merge rate across {newcomer_sample} newcomer PRs evaluated in {total_prs} recent PRs)."
            )
        elif newcomer_merged >= 1:
            c6_score = 1
            c6_rationale = (
                f"Selective newcomer merging: {newcomer_merged} merged out of {newcomer_closed} closed newcomer PRs "
                f"({newcomer_rate}% acceptance rate across {newcomer_sample} newcomer PRs evaluated in {total_prs} recent PRs)."
            )
        else:
            c6_score = 0
            if newcomer_closed > 0:
                c6_rationale = (
                    f"Zero newcomer PRs merged out of {newcomer_closed} closed newcomer PRs "
                    f"({newcomer_sample} evaluated in the {total_prs} most recent PRs)."
                )
            elif newcomer_sample > 0:
                c6_rationale = f"Zero closed newcomer PRs observed ({newcomer_sample} open newcomer PRs evaluated in the {total_prs} most recent PRs)."
            else:
                c6_rationale = f"Zero newcomer PRs identified in the {total_prs} evaluated pull request sample."

        criteria_scores.append(
            CriterionScore(
                criterion_id="newcomer_prs_merged",
                name="Newcomer PRs Acceptance & Merge Rate",
                phase="phase_6_issue_hygiene_and_accessibility",
                score=c6_score,
                max_score=2,
                rationale=c6_rationale,
                evidence_ids=[c6_ev_id] if c6_ev_id else [],
            )
        )

        # ---------------------------------------------------------------------
        # 7. Beginner Issues & Newcomer Hygiene (phase_6_issue_hygiene_and_accessibility)
        # ---------------------------------------------------------------------
        open_beginner_count = newcomer_metrics.get("open_beginner_issues_count", 0)
        if open_beginner_count >= 3:
            c7_score = 2
            c7_rationale = f"Curated beginner backlog: {open_beginner_count} open 'good first issue' / newcomer tasks available."
        elif open_beginner_count >= 1:
            c7_score = 1
            c7_rationale = (
                f"Limited entry points: {open_beginner_count} open beginner issue available."
            )
        else:
            c7_score = 0
            c7_rationale = "Zero issues labeled for beginners or newcomer contributors."

        criteria_scores.append(
            CriterionScore(
                criterion_id="beginner_issues",
                name="Beginner Issues & Newcomer Hygiene",
                phase="phase_6_issue_hygiene_and_accessibility",
                score=c7_score,
                max_score=2,
                rationale=c7_rationale,
                evidence_ids=[c7_ev_id] if c7_ev_id else [],
            )
        )

        # ---------------------------------------------------------------------
        # 8. Documentation & Local Setup Clarity (phase_5_documentation_and_onboarding)
        # ---------------------------------------------------------------------
        has_readme = documentation_metrics.get("has_readme", False)
        has_contributing = documentation_metrics.get("has_contributing", False)
        readme_size = documentation_metrics.get("readme_size_bytes", 0)

        if has_readme and has_contributing and readme_size > 1500:
            c8_score = 2
            c8_rationale = "Exemplary documentation: Detailed README and explicit CONTRIBUTING.md guide present."
        elif has_readme:
            c8_score = 1
            c8_rationale = (
                "Basic README present, but lacks dedicated CONTRIBUTING.md onboarding guide."
            )
        else:
            c8_score = 0
            c8_rationale = "Deficient documentation: Missing or empty README and no setup guide."

        criteria_scores.append(
            CriterionScore(
                criterion_id="docs_and_setup",
                name="Documentation & Local Setup Clarity",
                phase="phase_5_documentation_and_onboarding",
                score=c8_score,
                max_score=2,
                rationale=c8_rationale,
                evidence_ids=[c8_ev_id] if c8_ev_id else [],
            )
        )

        # ---------------------------------------------------------------------
        # 9. CI Workflows & Automated Testing (phase_7_ci_cd_and_testing)
        # ---------------------------------------------------------------------
        has_ci = ci_security_metrics.get("has_ci_workflows", False)
        ci_passing = ci_security_metrics.get("ci_passing_on_default_branch")
        has_tests_dir = ci_security_metrics.get("has_tests_directory", False)

        if has_ci and ci_passing is True and has_tests_dir:
            c9_score = 2
            c9_rationale = "Robust testing: Passing CI workflows on default branch and test directory verified."
        elif has_ci or has_tests_dir:
            c9_score = 1
            c9_rationale = "Partial CI/Testing: Test directory or workflows exist, but automated verification is incomplete or failing."
        else:
            c9_score = 0
            c9_rationale = "Untested: No automated CI workflows and no test directories detected."

        criteria_scores.append(
            CriterionScore(
                criterion_id="ci_and_code_quality",
                name="CI Workflows & Automated Testing",
                phase="phase_7_ci_cd_and_testing",
                score=c9_score,
                max_score=2,
                rationale=c9_rationale,
                evidence_ids=[c9_ev_id] if c9_ev_id else [],
            )
        )

        # ---------------------------------------------------------------------
        # 10. Community Tone & Discussion Channels (phase_3_governance_and_culture)
        # ---------------------------------------------------------------------
        has_coc = documentation_metrics.get("has_code_of_conduct", False)
        has_discussions = documentation_metrics.get("has_discussions_enabled", False)

        if has_coc:
            c10_score = 1
            c10_rationale = (
                "Standard: CODE_OF_CONDUCT.md present. Note: Real-time chat (Discord/Slack/Matrix) "
                "and GitHub Discussions interaction activity are not collected via REST API and remain "
                "unverified (cannot award exemplary score for unverified activity)."
            )
        elif has_discussions:
            c10_score = 1
            c10_rationale = (
                "Discussions feature enabled, but Code of Conduct is absent and discussion "
                "activity is unverified via REST API."
            )
        else:
            c10_score = 0
            c10_rationale = (
                "No Code of Conduct published and no public community discussion channels enabled."
            )

        criteria_scores.append(
            CriterionScore(
                criterion_id="community_tone_and_chat",
                name="Community Tone & Discussion Channels",
                phase="phase_3_governance_and_culture",
                score=c10_score,
                max_score=2,
                rationale=c10_rationale,
                evidence_ids=[c10_ev_id] if c10_ev_id else [],
            )
        )

        # Calculate Total Score
        total_score = sum(c.score for c in criteria_scores)
        scorecard = Scorecard(
            criteria_scores=criteria_scores,
            total_score=total_score,
            max_possible_score=20,
        )

        # ---------------------------------------------------------------------
        # Final Decision Logic & Hard Gates Override
        # ---------------------------------------------------------------------
        disqualifiers_triggered: list[str] = []

        critical_gate_failed = False
        high_gate_failed = False
        unknown_gate_present = False

        for gate in hard_gates:
            if gate.status == HardGateStatus.FAIL:
                disqualifiers_triggered.append(f"{gate.name}: {gate.reason}")
                if gate.severity == "CRITICAL":
                    critical_gate_failed = True
                else:
                    high_gate_failed = True
            elif gate.status == HardGateStatus.UNKNOWN:
                unknown_gate_present = True

        if critical_gate_failed:
            decision = AuditDecision.REJECT
        elif high_gate_failed or unknown_gate_present:
            decision = AuditDecision.NEEDS_MANUAL_REVIEW
        elif total_score >= 16:
            decision = AuditDecision.APPROVE
        elif total_score >= 11:
            decision = AuditDecision.CONDITIONAL
        elif total_score >= 8:
            decision = AuditDecision.NEEDS_MANUAL_REVIEW
        else:
            decision = AuditDecision.REJECT

        return scorecard, decision, disqualifiers_triggered
