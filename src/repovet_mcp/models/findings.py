"""Findings data contracts for audit observations and risk flags."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class FindingSeverity(StrEnum):
    """Severity classification for audit findings."""

    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class FindingCategory(StrEnum):
    """Categorical domain of a repository finding."""

    LICENSING = "licensing"
    ACTIVITY = "activity"
    GOVERNANCE = "governance"
    COMMUNITY = "community"
    RESPONSIVENESS = "responsiveness"
    DOCUMENTATION = "documentation"
    ISSUE_HYGIENE = "issue_hygiene"
    CI_CD = "ci_cd"
    TESTING = "testing"
    DEPENDENCIES = "dependencies"
    SECURITY = "security"
    MENTORSHIP = "mentorship"


class Finding(BaseModel):
    """Structured audit observation tied to primary evidence."""

    id: str = Field(description="Unique finding identifier")
    phase: str = Field(description="Associated vetting phase")
    criterion_id: str | None = Field(
        default=None,
        description="Associated scorecard criterion identifier, if applicable",
    )
    severity: FindingSeverity = Field(
        default=FindingSeverity.INFO,
        description="Assessed severity level",
    )
    category: FindingCategory = Field(description="Domain category of the finding")
    title: str = Field(description="Short human-readable summary of the finding")
    description: str = Field(description="Detailed explanation of the observation")
    evidence_ids: list[str] = Field(
        default_factory=list,
        description="IDs of evidence items that support this finding",
    )
    remediation_recommendation: str | None = Field(
        default=None,
        description="Suggested action for contributor or maintainer",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Timestamp when finding was recorded",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context or raw findings data",
    )
