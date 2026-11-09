"""Evidence data contracts for grounded repository auditing."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class EvidenceConfidence(StrEnum):
    """Confidence level of an evidence item."""

    CONFIRMED = "CONFIRMED"
    INFERRED = "INFERRED"
    UNKNOWN = "UNKNOWN"


class EvidenceSourceType(StrEnum):
    """Source provenance of an evidence item."""

    GITHUB_API_REST = "github_api_rest"
    GITHUB_API_GRAPHQL = "github_api_graphql"
    REPOSITORY_FILE = "repository_file"
    STATIC_ANALYSIS = "static_analysis"
    MANUAL_INSPECTION = "manual_inspection"


class EvidenceItem(BaseModel):
    """Individual grounded piece of evidence collected during vetting."""

    id: str = Field(description="Unique identifier for the evidence artifact")
    phase: str = Field(description="Vetting phase where evidence was collected")
    source_type: EvidenceSourceType = Field(description="Mechanism used to obtain evidence")
    source_endpoint: str | None = Field(
        default=None,
        description="API endpoint or file location of evidence",
    )
    collected_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Timestamp when evidence was observed",
    )
    confidence: EvidenceConfidence = Field(
        default=EvidenceConfidence.CONFIRMED,
        description="Confidence classification of the evidence",
    )
    summary: str = Field(description="Concise description of the observed evidence")
    raw_reference: str | None = Field(
        default=None,
        description="Pointer to raw cached payload or commit SHA",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional structured metadata or raw metrics",
    )
    verified: bool = Field(
        default=True,
        description="Whether evidence passed ground-truth validation",
    )
