"""Pydantic request/response models for the AumOS Maturity Assessment API.

All API inputs and outputs are typed Pydantic models — never raw dicts.
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Assessment schemas
# ---------------------------------------------------------------------------


class DimensionWeightsRequest(BaseModel):
    """Custom dimension scoring weights. Must sum to 1.0."""

    data: float = Field(0.25, ge=0.0, le=1.0, description="Data dimension weight")
    process: float = Field(0.20, ge=0.0, le=1.0, description="Process dimension weight")
    people: float = Field(0.20, ge=0.0, le=1.0, description="People dimension weight")
    technology: float = Field(0.20, ge=0.0, le=1.0, description="Technology dimension weight")
    governance: float = Field(0.15, ge=0.0, le=1.0, description="Governance dimension weight")

    @field_validator("governance", mode="after")
    @classmethod
    def weights_must_sum_to_one(cls, governance: float, info: Any) -> float:
        """Validate that all weights sum to 1.0."""
        data = info.data.get("data", 0.25)
        process = info.data.get("process", 0.20)
        people = info.data.get("people", 0.20)
        technology = info.data.get("technology", 0.20)
        total = data + process + people + technology + governance
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"Dimension weights must sum to 1.0, got {total:.3f}")
        return governance


class CreateAssessmentRequest(BaseModel):
    """Request body for creating a new maturity assessment."""

    organization_name: str = Field(..., min_length=1, max_length=255)
    industry: str = Field(
        ...,
        description=(
            "Industry vertical: financial_services | healthcare | manufacturing | "
            "retail | technology | government | other"
        ),
    )
    organization_size: str = Field(
        ...,
        description="startup | smb | mid_market | enterprise | large_enterprise",
    )
    dimension_weights: DimensionWeightsRequest | None = Field(
        None,
        description="Custom dimension weights (defaults to standard weighting)",
    )
    assessment_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context: revenue_range, ai_budget, current_initiatives",
    )


class AssessmentResponse(BaseModel):
    """Response model for a maturity assessment."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    organization_name: str
    industry: str
    organization_size: str
    status: str
    overall_score: float | None
    maturity_level: int | None
    data_score: float | None
    process_score: float | None
    people_score: float | None
    technology_score: float | None
    governance_score: float | None
    dimension_weights: dict[str, float]
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AssessmentListResponse(BaseModel):
    """Paginated list of assessments."""

    items: list[AssessmentResponse]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Response submission schemas
# ---------------------------------------------------------------------------


class QuestionResponseItem(BaseModel):
    """A single diagnostic question response."""

    question_id: str = Field(..., min_length=1, max_length=100)
    dimension: str = Field(
        ...,
        description="data | process | people | technology | governance",
    )
    response_value: str = Field(..., min_length=1, max_length=500)
    numeric_score: float | None = Field(None, ge=0.0, le=100.0)
    weight: float = Field(1.0, ge=0.0, le=10.0)
    response_metadata: dict[str, Any] = Field(default_factory=dict)


class SubmitResponsesRequest(BaseModel):
    """Request body for submitting diagnostic question responses."""

    responses: list[QuestionResponseItem] = Field(
        ...,
        min_length=1,
        description="List of question responses to submit",
    )


class QuestionResponseRecord(BaseModel):
    """Persisted question response record."""

    id: uuid.UUID
    assessment_id: uuid.UUID
    question_id: str
    dimension: str
    response_value: str
    numeric_score: float | None
    weight: float
    created_at: datetime


class SubmitResponsesResponse(BaseModel):
    """Response after submitting question responses."""

    assessment_id: uuid.UUID
    submitted_count: int
    responses: list[QuestionResponseRecord]


# ---------------------------------------------------------------------------
# Detailed scoring schemas
# ---------------------------------------------------------------------------


class DimensionScoreDetail(BaseModel):
    """Detailed score breakdown for one dimension."""

    score: float | None
    weight: float | None
    responses: list[dict[str, Any]]


class DetailedScoreResponse(BaseModel):
    """Detailed multi-dimensional scoring breakdown."""

    assessment_id: uuid.UUID
    organization_name: str
    overall_score: float | None
    maturity_level: int | None
    maturity_label: str
    dimension_scores: dict[str, DimensionScoreDetail]
    dimension_weights: dict[str, float]
    completed_at: str | None


# ---------------------------------------------------------------------------
# Benchmark schemas
# ---------------------------------------------------------------------------


class BenchmarkCompareRequest(BaseModel):
    """Request body for comparing an assessment against industry benchmarks."""

    assessment_id: uuid.UUID


class DimensionComparisonDetail(BaseModel):
    """Comparison result for one dimension."""

    assessment_score: float
    benchmark_median: float
    gap: float
    above_median: bool


class BenchmarkCompareResponse(BaseModel):
    """Result of comparing an assessment against industry benchmarks."""

    assessment_id: uuid.UUID
    benchmark_period: str
    industry: str
    organization_size: str
    sample_size: int
    overall_score: float | None
    overall_percentile: int
    benchmark_median: float
    dimension_comparisons: dict[str, DimensionComparisonDetail]
    top_gaps: list[dict[str, Any]]
    strengths: list[dict[str, Any]]
    industry_top_strengths: list[str]
    industry_top_gaps: list[str]


class BenchmarkResponse(BaseModel):
    """Industry benchmark record."""

    id: uuid.UUID
    industry: str
    organization_size: str
    benchmark_period: str
    sample_size: int
    overall_p25: float
    overall_p50: float
    overall_p75: float
    overall_p90: float
    data_p50: float
    process_p50: float
    people_p50: float
    technology_p50: float
    governance_p50: float
    top_strengths: list[str]
    top_gaps: list[str]
    is_active: bool
    created_at: datetime


class BenchmarkListResponse(BaseModel):
    """List of industry benchmarks."""

    items: list[BenchmarkResponse]
    total: int


# ---------------------------------------------------------------------------
# Roadmap schemas
# ---------------------------------------------------------------------------


class GenerateRoadmapRequest(BaseModel):
    """Request body for auto-generating a roadmap."""

    assessment_id: uuid.UUID
    horizon_months: int | None = Field(
        None, ge=3, le=60, description="Planning horizon in months (default: 18)"
    )
    target_maturity_level: int | None = Field(
        None, ge=1, le=5, description="Target maturity level 1-5 (default: current+1)"
    )


class InitiativeItem(BaseModel):
    """A single roadmap initiative."""

    id: str
    title: str
    dimension: str
    priority: str
    effort_weeks: int
    impact_score: float
    phase: str
    description: str


class RoadmapResponse(BaseModel):
    """Roadmap record."""

    id: uuid.UUID
    assessment_id: uuid.UUID
    title: str
    horizon_months: int
    status: str
    target_maturity_level: int
    initiatives: list[dict[str, Any]]
    quick_wins: list[dict[str, Any]]
    estimated_roi_multiplier: float | None
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Pilot schemas
# ---------------------------------------------------------------------------


class SuccessCriterionItem(BaseModel):
    """A measurable pilot success criterion."""

    metric: str
    target_value: str
    measurement_method: str
    baseline_value: str | None = None


class FailureModeItem(BaseModel):
    """A pre-identified pilot failure mode."""

    mode: str
    likelihood: str
    mitigation_action: str
    owner: str


class DesignPilotRequest(BaseModel):
    """Request body for designing a pilot initiative."""

    roadmap_id: uuid.UUID
    title: str = Field(..., min_length=1, max_length=255)
    dimension: str = Field(
        ...,
        description="data | process | people | technology | governance",
    )
    success_criteria: list[SuccessCriterionItem] = Field(
        ...,
        min_length=3,
        description="Minimum 3 success criteria required",
    )
    failure_modes: list[FailureModeItem] = Field(
        default_factory=list,
        description="Pre-identified failure modes with mitigation actions",
    )
    stakeholder_map: dict[str, str] = Field(
        ...,
        description="Roles mapped to stakeholder names/IDs",
    )
    resource_requirements: dict[str, Any] = Field(
        ...,
        description="Required resources: compute, data, people, budget_estimate",
    )
    duration_weeks: int = Field(8, ge=1, le=52)


class PilotResponse(BaseModel):
    """Pilot record."""

    id: uuid.UUID
    roadmap_id: uuid.UUID
    title: str
    status: str
    dimension: str
    duration_weeks: int
    success_criteria: list[dict[str, Any]]
    failure_modes: list[dict[str, Any]]
    stakeholder_map: dict[str, Any]
    resource_requirements: dict[str, Any]
    execution_log: list[dict[str, Any]]
    outcome_metrics: dict[str, Any]
    success_score: float | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class UpdatePilotStatusRequest(BaseModel):
    """Request body for updating pilot lifecycle status."""

    status: str = Field(
        ...,
        description="designed | approved | running | completed | failed | cancelled",
    )


class LogExecutionUpdateRequest(BaseModel):
    """Request body for logging a weekly pilot execution update."""

    week: int = Field(..., ge=1, le=52)
    status: str = Field(..., description="on_track | at_risk | blocked")
    metrics: dict[str, Any] = Field(default_factory=dict)
    blockers: list[str] = Field(default_factory=list)
    notes: str = Field("", max_length=2000)


# ---------------------------------------------------------------------------
# Report schemas
# ---------------------------------------------------------------------------


class GenerateReportRequest(BaseModel):
    """Request body for generating an executive report."""

    assessment_id: uuid.UUID
    report_type: str = Field(
        "executive_summary",
        description=(
            "executive_summary | detailed_assessment | benchmark_comparison | "
            "roadmap_presentation | pilot_brief"
        ),
    )
    format: str = Field("pdf", description="pdf | pptx | docx | json")
    roadmap_id: uuid.UUID | None = Field(
        None,
        description="Optional roadmap to include in the report",
    )
    include_benchmarks: bool = Field(
        True,
        description="Whether to include industry benchmark comparisons",
    )


class ReportResponse(BaseModel):
    """Report record."""

    id: uuid.UUID
    assessment_id: uuid.UUID
    title: str
    report_type: str
    status: str
    format: str
    content: dict[str, Any]
    artifact_url: str | None
    error_message: str | None
    generated_at: datetime | None
    created_at: datetime
    updated_at: datetime
