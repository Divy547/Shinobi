"""Audit and scorecard data contracts for repository vetting."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from repovet_mcp.models.evidence import EvidenceItem
from repovet_mcp.models.findings import Finding


class AuditDecision(StrEnum):
    """Final vetting decision verdict."""

    APPROVE = "APPROVE"
    CONDITIONAL = "CONDITIONAL"
    NEEDS_MANUAL_REVIEW = "NEEDS_MANUAL_REVIEW"
    REJECT = "REJECT"


class CriterionScore(BaseModel):
    """Evaluated score for a single criterion on the 0-2 scale."""

    criterion_id: str = Field(description="Unique criterion identifier matching scoring config")
    name: str = Field(description="Human-readable criterion title")
    phase: str = Field(description="Corresponding vetting phase")
    score: int = Field(ge=0, le=2, description="Score on 0-2 scale")
    max_score: int = Field(default=2, description="Maximum possible score for this criterion")
    rationale: str = Field(description="Evidence-backed justification for the assigned score")
    evidence_ids: list[str] = Field(
        default_factory=list,
        description="IDs of evidence items supporting this score",
    )


class AuditTarget(BaseModel):
    """Target repository being vetted."""

    owner: str = Field(description="GitHub repository owner or organization")
    repo: str = Field(description="GitHub repository name")
    url: str = Field(description="Full URL to repository")
    default_branch: str = Field(default="main", description="Target default branch name")
    commit_sha: str | None = Field(
        default=None,
        description="Specific commit SHA analyzed, if applicable",
    )


class Scorecard(BaseModel):
    """Aggregated scorecard containing all 10 evaluated criteria."""

    criteria_scores: list[CriterionScore] = Field(
        default_factory=list,
        description="List of individual criterion evaluation scores",
    )
    total_score: int = Field(
        default=0,
        ge=0,
        le=20,
        description="Sum of all evaluated criteria scores (0-20)",
    )
    max_possible_score: int = Field(
        default=20,
        description="Maximum attainable scorecard score (20)",
    )

    @property
    def percentage(self) -> float:
        """Calculate percentage score."""
        if self.max_possible_score == 0:
            return 0.0
        return round((self.total_score / self.max_possible_score) * 100, 2)


class AuditReport(BaseModel):
    """Comprehensive repository audit result."""

    audit_id: str = Field(description="Unique audit execution identifier")
    target: AuditTarget = Field(description="Target repository details")
    decision: AuditDecision = Field(description="Final evaluation decision verdict")
    scorecard: Scorecard = Field(description="Complete 10-criterion evaluation scorecard")
    findings: list[Finding] = Field(
        default_factory=list,
        description="List of individual audit observations and risks",
    )
    evidence: list[EvidenceItem] = Field(
        default_factory=list,
        description="Collected grounded evidence items",
    )
    summary: str = Field(description="Executive summary of the audit verdict")
    disqualifiers_triggered: list[str] = Field(
        default_factory=list,
        description="List of critical disqualifiers or hard blockers triggered",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Audit execution timestamp",
    )
    schema_version: str = Field(default="1.0.0", description="Contract schema version")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional execution metadata",
    )
