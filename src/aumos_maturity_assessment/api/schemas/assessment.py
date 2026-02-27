"""Pydantic request/response schemas for the AI Readiness Assessment lead magnet API.

All API inputs and outputs are strictly typed Pydantic v2 models.
No raw dicts are returned from any endpoint.
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field, field_validator


# ---------------------------------------------------------------------------
# Shared value objects
# ---------------------------------------------------------------------------


class RoadmapItemSchema(BaseModel):
    """A single roadmap recommendation item.

    Attributes:
        module: AumOS platform module identifier.
        dimension: Assessment dimension this recommendation addresses.
        score_band: Score band that triggered this recommendation.
        title: Human-readable initiative title.
        description: How this module addresses the identified gap.
        priority: Suggested priority level.
        estimated_effort_weeks: Rough implementation effort estimate.
    """

    module: str
    dimension: str
    score_band: str
    title: str
    description: str
    priority: str
    estimated_effort_weeks: int


class BenchmarkComparisonSchema(BaseModel):
    """Peer benchmark comparison for a single dimension.

    Attributes:
        dimension: The dimension being compared.
        respondent_score: The respondent's score for this dimension.
        p25_score: 25th percentile benchmark score.
        p50_score: Median benchmark score.
        p75_score: 75th percentile benchmark score.
        percentile_position: Respondent's estimated percentile position.
    """

    dimension: str
    respondent_score: float
    p25_score: float
    p50_score: float
    p75_score: float
    percentile_position: float


# ---------------------------------------------------------------------------
# Start assessment
# ---------------------------------------------------------------------------


class StartAssessmentRequest(BaseModel):
    """Request body to begin a self-service AI readiness assessment session.

    Attributes:
        industry_vertical: The respondent's industry sector.
        company_size: Broad organisation size category.
    """

    industry_vertical: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description=(
            "Industry vertical: financial_services | healthcare | manufacturing | "
            "retail | technology | government | other"
        ),
    )
    company_size: str = Field(
        ...,
        description="startup | smb | mid_market | enterprise | large_enterprise",
    )


class QuestionSchema(BaseModel):
    """A single assessment question returned to the client.

    Attributes:
        question_id: Unique question identifier.
        dimension: Assessment dimension this question belongs to.
        text: Full question text.
        weight: Scoring weight within the dimension.
    """

    question_id: str
    dimension: str
    text: str
    weight: float


class StartAssessmentResponse(BaseModel):
    """Response after successfully starting an assessment session.

    Attributes:
        session_id: UUID for this assessment session, used in subsequent calls.
        questions: The complete question set to present to the respondent.
        total_questions: Total number of questions in this assessment.
        dimensions: List of dimension names covered by this assessment.
    """

    session_id: uuid.UUID
    questions: list[QuestionSchema]
    total_questions: int
    dimensions: list[str]


# ---------------------------------------------------------------------------
# Answer submission
# ---------------------------------------------------------------------------


class AnswerRequest(BaseModel):
    """Request body to submit a single question answer.

    Attributes:
        question_id: Identifier of the question being answered.
        answer_value: Answer on the 1-5 Likert scale.
        industry_vertical: Industry vertical (must match session value).
    """

    question_id: str = Field(..., min_length=1, max_length=50)
    answer_value: int = Field(
        ...,
        ge=1,
        le=5,
        description="Answer on a 1-5 scale: 1=Not at all, 5=Fully implemented",
    )
    industry_vertical: str = Field(..., min_length=1, max_length=100)

    @field_validator("answer_value")
    @classmethod
    def validate_answer_range(cls, value: int) -> int:
        """Ensure answer_value is within the valid 1-5 range.

        Args:
            value: The provided answer value.

        Returns:
            The validated answer value.

        Raises:
            ValueError: If value is outside 1-5 range.
        """
        if not (1 <= value <= 5):
            raise ValueError(f"answer_value must be between 1 and 5, got {value}")
        return value


class AnswerResponse(BaseModel):
    """Response after successfully recording a question answer.

    Attributes:
        session_id: The assessment session UUID.
        question_id: The question that was answered.
        answer_value: The recorded answer value.
        answered_at: Timestamp when the answer was persisted.
        progress: Fraction of total questions answered (0.0-1.0).
        answered_count: Number of questions answered so far.
        total_questions: Total questions in this assessment.
    """

    session_id: uuid.UUID
    question_id: str
    answer_value: int
    answered_at: datetime
    progress: float
    answered_count: int
    total_questions: int


# ---------------------------------------------------------------------------
# Complete assessment
# ---------------------------------------------------------------------------


class CompleteAssessmentRequest(BaseModel):
    """Request body to finalise an assessment session and receive results.

    Attributes:
        email: Contact email for delivering the full report.
        company_name: Name of the organisation being assessed.
        industry_vertical: Must match the session's industry vertical.
    """

    email: EmailStr = Field(
        ...,
        description="Contact email address for delivering assessment results",
    )
    company_name: str = Field(..., min_length=1, max_length=255)
    industry_vertical: str = Field(..., min_length=1, max_length=100)


class CompleteAssessmentResponse(BaseModel):
    """Full assessment results returned after completion.

    Attributes:
        session_id: The assessment session UUID.
        email: Contact email used for lead capture.
        company_name: Organisation name.
        overall_score: Weighted composite score (0-100).
        maturity_level: Overall maturity level (1-5).
        maturity_label: Human-readable maturity label.
        dimension_scores: Per-dimension scores (0-100 each).
        peer_percentile: Estimated percentile vs industry peers.
        roadmap_items: Prioritised list of AumOS module recommendations.
        benchmark_comparison: Per-dimension benchmark comparison data.
        industry_vertical: The respondent's industry sector.
        completed_at: Timestamp when assessment was finalised.
    """

    session_id: uuid.UUID
    email: str
    company_name: str
    overall_score: float
    maturity_level: int
    maturity_label: str
    dimension_scores: dict[str, float]
    peer_percentile: float
    roadmap_items: list[RoadmapItemSchema]
    benchmark_comparison: list[BenchmarkComparisonSchema]
    industry_vertical: str
    completed_at: datetime


# ---------------------------------------------------------------------------
# Benchmarks
# ---------------------------------------------------------------------------


class BenchmarkResponse(BaseModel):
    """Industry benchmark data for a specific dimension and vertical.

    Attributes:
        id: Benchmark record UUID.
        industry_vertical: Industry this benchmark covers.
        dimension: Assessment dimension.
        p25_score: 25th percentile score.
        p50_score: Median score.
        p75_score: 75th percentile score.
        sample_size: Number of organisations in the sample.
        updated_at: When this benchmark was last refreshed.
    """

    id: uuid.UUID
    industry_vertical: str
    dimension: str
    p25_score: float
    p50_score: float
    p75_score: float
    sample_size: int
    updated_at: datetime


class BenchmarkListResponse(BaseModel):
    """List of benchmark records for an industry vertical.

    Attributes:
        industry_vertical: The queried industry vertical.
        benchmarks: List of benchmark records, one per dimension.
        total: Total number of benchmark records returned.
    """

    industry_vertical: str
    benchmarks: list[BenchmarkResponse]
    total: int


# ---------------------------------------------------------------------------
# Assessment result summary (for CRM/internal use)
# ---------------------------------------------------------------------------


class AssessmentResultSummary(BaseModel):
    """Lightweight summary of a stored assessment result record.

    Attributes:
        id: Result record UUID.
        session_id: Assessment session UUID.
        email: Contact email.
        company_name: Organisation name.
        overall_score: Weighted composite score.
        maturity_level: Overall maturity level.
        industry_vertical: Respondent's industry vertical.
        peer_percentile: Estimated peer percentile.
        crm_sync_status: Status of CRM synchronisation.
        created_at: When the result was created.
    """

    id: uuid.UUID
    session_id: uuid.UUID
    email: str
    company_name: str
    overall_score: float
    maturity_level: int
    industry_vertical: str
    peer_percentile: float
    crm_sync_status: str
    created_at: datetime
    dimension_scores: dict[str, Any]
