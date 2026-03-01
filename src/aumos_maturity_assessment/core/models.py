"""SQLAlchemy ORM models for the AumOS Maturity Assessment service.

All tables use the `mat_` prefix. Tenant-scoped tables extend AumOSModel
which supplies id (UUID), tenant_id, created_at, and updated_at columns.

Domain model:
  Assessment                      — maturity assessment instance with multi-dimensional scores
  AssessmentResponse              — individual question responses within an assessment
  Benchmark                       — industry benchmark data for comparison
  Roadmap                         — auto-generated AI adoption roadmap from assessment results
  Pilot                           — pilot design and execution tracking
  Report                          — generated executive report artifacts
  MatDimensionConfig              — configurable assessment dimensions (GAP-286)
  MatBenchmarkContributionConsent — opt-in consent for anonymous benchmark contribution (GAP-287)
"""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from aumos_common.database import AumOSModel, Base


class Assessment(AumOSModel):
    """A maturity assessment instance for an enterprise client.

    Captures multi-dimensional AI maturity scores across data, process,
    people, technology, and governance dimensions. Tracks the full
    assessment lifecycle from in_progress to completed.

    Status transitions:
        in_progress → completed
        in_progress → abandoned

    Table: mat_assessments
    """

    __tablename__ = "mat_assessments"

    organization_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="Name of the organization being assessed",
    )
    industry: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment=(
            "Industry vertical: financial_services | healthcare | manufacturing | "
            "retail | technology | government | other"
        ),
    )
    organization_size: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="startup | smb | mid_market | enterprise | large_enterprise",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="in_progress",
        index=True,
        comment="in_progress | completed | abandoned",
    )
    overall_score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Weighted composite maturity score 0-100 (null until assessment completes)",
    )
    maturity_level: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment=(
            "Overall maturity level 1-5: "
            "1=Initial, 2=Developing, 3=Defined, 4=Managed, 5=Optimizing"
        ),
    )
    # Multi-dimensional scores (0-100 each)
    data_score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Data dimension score: quality, governance, infrastructure, accessibility",
    )
    process_score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Process dimension score: MLOps, deployment pipelines, automation maturity",
    )
    people_score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="People dimension score: AI literacy, talent density, upskilling programs",
    )
    technology_score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Technology dimension score: AI tooling, compute, infrastructure readiness",
    )
    governance_score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Governance dimension score: AI ethics, compliance, risk management",
    )
    dimension_weights: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=lambda: {
            "data": 0.25,
            "process": 0.20,
            "people": 0.20,
            "technology": 0.20,
            "governance": 0.15,
        },
        comment="Weighting factors per dimension (must sum to 1.0)",
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when assessment was finalized",
    )
    assessment_metadata: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Additional context: revenue_range, ai_budget, current_initiatives",
    )
    initiated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="User ID who initiated this assessment",
    )
    dimensions_used: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=lambda: ["data", "process", "people", "technology", "governance"],
        comment=(
            "Ordered list of dimension IDs included in this assessment. "
            "Defaults to the original 5 dimensions for backward compatibility."
        ),
    )

    responses: Mapped[list["AssessmentResponse"]] = relationship(
        "AssessmentResponse",
        back_populates="assessment",
        cascade="all, delete-orphan",
        order_by="AssessmentResponse.created_at",
    )
    roadmaps: Mapped[list["Roadmap"]] = relationship(
        "Roadmap",
        back_populates="assessment",
        cascade="all, delete-orphan",
    )
    reports: Mapped[list["Report"]] = relationship(
        "Report",
        back_populates="assessment",
        cascade="all, delete-orphan",
    )


class AssessmentResponse(AumOSModel):
    """A single question response within a maturity assessment.

    Each response captures the answer to one diagnostic question and
    its contribution to the dimension score.

    Table: mat_assessment_responses
    """

    __tablename__ = "mat_assessment_responses"

    assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("mat_assessments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Parent assessment UUID",
    )
    question_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Question identifier from the diagnostic questionnaire",
    )
    dimension: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="data | process | people | technology | governance",
    )
    response_value: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="The answer value (typically a scale option or free text)",
    )
    numeric_score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Normalized 0-100 score derived from this response",
    )
    response_metadata: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Additional response context: evidence, examples, notes",
    )
    weight: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=1.0,
        comment="Question weight within its dimension (for weighted scoring)",
    )

    assessment: Mapped["Assessment"] = relationship(
        "Assessment",
        back_populates="responses",
    )


class Benchmark(AumOSModel):
    """Industry benchmark data for AI maturity comparison.

    Stores aggregated maturity statistics per industry vertical and
    organization size segment to enable peer comparison.

    Table: mat_benchmarks
    """

    __tablename__ = "mat_benchmarks"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "industry",
            "organization_size",
            "benchmark_period",
            name="uq_mat_benchmarks_tenant_industry_size_period",
        ),
    )

    industry: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Industry vertical this benchmark covers",
    )
    organization_size: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Organization size segment this benchmark covers",
    )
    benchmark_period: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="Period identifier: 2024-Q1, 2024-Q2, etc.",
    )
    sample_size: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of organizations contributing to this benchmark",
    )
    # Benchmark scores (0-100 each, percentile distributions)
    overall_p25: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, comment="25th percentile overall score"
    )
    overall_p50: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, comment="Median overall score"
    )
    overall_p75: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, comment="75th percentile overall score"
    )
    overall_p90: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, comment="90th percentile overall score"
    )
    data_p50: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, comment="Median data dimension score"
    )
    process_p50: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, comment="Median process dimension score"
    )
    people_p50: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, comment="Median people dimension score"
    )
    technology_p50: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, comment="Median technology dimension score"
    )
    governance_p50: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, comment="Median governance dimension score"
    )
    dimension_breakdowns: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Full percentile distribution per dimension",
    )
    top_strengths: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment="Top 3 capability strengths for this industry segment",
    )
    top_gaps: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment="Top 3 capability gaps for this industry segment",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="False when superseded by a newer benchmark period",
    )
    # GAP-287: Benchmark data enrichment fields
    data_source: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="seed_estimate",
        comment="Source attribution, e.g. 'Gartner 2025 AI Adoption Survey (n=843)'",
    )
    confidence_tier: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="seed_estimate",
        comment=(
            "Data quality tier: seed_estimate (n<30) | preliminary (30-100) | "
            "reliable (100-500) | robust (>500)"
        ),
    )
    data_collected_at: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="Date when the underlying survey/research data was collected",
    )
    contributing_tenant_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of opt-in tenants contributing to this benchmark period",
    )


class Roadmap(AumOSModel):
    """Auto-generated AI adoption roadmap from assessment results.

    Represents a prioritized set of initiatives to advance AI maturity,
    organized by time horizon and addressing identified gaps.

    Table: mat_roadmaps
    """

    __tablename__ = "mat_roadmaps"

    assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("mat_assessments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Parent assessment UUID",
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Roadmap title (e.g., 'AI Maturity Advancement Plan 2025-2026')",
    )
    horizon_months: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=18,
        comment="Time horizon in months for the roadmap",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="draft",
        index=True,
        comment="draft | published | superseded",
    )
    target_maturity_level: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3,
        comment="Target overall maturity level 1-5 to achieve within horizon",
    )
    initiatives: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment=(
            "Ordered list of initiatives: "
            "[{id, title, dimension, priority, effort_weeks, impact_score, "
            "phase: 'quick_wins'|'foundation'|'scale'|'optimize', description}]"
        ),
    )
    quick_wins: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment="High-impact, low-effort initiatives achievable within 90 days",
    )
    estimated_roi_multiplier: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Estimated ROI multiplier from completing roadmap initiatives",
    )
    roadmap_metadata: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Generation context: model_version, benchmark_period, generation_params",
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when roadmap was published to client",
    )

    assessment: Mapped["Assessment"] = relationship(
        "Assessment",
        back_populates="roadmaps",
    )
    pilots: Mapped[list["Pilot"]] = relationship(
        "Pilot",
        back_populates="roadmap",
        cascade="all, delete-orphan",
    )


class Pilot(AumOSModel):
    """Pilot design and execution tracking for AI adoption initiatives.

    Addresses the 88% AI pilot failure rate by providing structured
    design, success criteria, and execution tracking.

    Table: mat_pilots
    """

    __tablename__ = "mat_pilots"

    roadmap_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("mat_roadmaps.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Parent roadmap UUID",
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Pilot initiative title",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="designed",
        index=True,
        comment="designed | approved | running | completed | failed | cancelled",
    )
    dimension: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Primary dimension addressed: data | process | people | technology | governance",
    )
    duration_weeks: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=8,
        comment="Planned pilot duration in weeks",
    )
    # Success criteria (addressing 88% failure rate root causes)
    success_criteria: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment=(
            "Measurable success criteria: "
            "[{metric, target_value, measurement_method, baseline_value}]"
        ),
    )
    failure_modes: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment=(
            "Pre-identified failure modes and mitigations: "
            "[{mode, likelihood, mitigation_action, owner}]"
        ),
    )
    stakeholder_map: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Stakeholders by role: {sponsor, champion, data_owner, it_owner, users}",
    )
    resource_requirements: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Required resources: {compute, data, people, budget_estimate}",
    )
    execution_log: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment="Weekly execution updates: [{week, status, metrics, blockers, notes}]",
    )
    outcome_metrics: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Actual measured outcomes at pilot completion",
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when pilot execution started",
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when pilot completed or was cancelled/failed",
    )
    success_score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="0-100 score measuring how well the pilot met its success criteria",
    )

    roadmap: Mapped["Roadmap"] = relationship(
        "Roadmap",
        back_populates="pilots",
    )


class Report(AumOSModel):
    """Generated executive report for an assessment.

    Consolidates assessment findings, benchmark comparisons, and roadmap
    recommendations into a structured executive presentation.

    Table: mat_reports
    """

    __tablename__ = "mat_reports"

    assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("mat_assessments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Parent assessment UUID",
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Report title",
    )
    report_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="executive_summary",
        comment=(
            "executive_summary | detailed_assessment | benchmark_comparison | "
            "roadmap_presentation | pilot_brief"
        ),
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="generating",
        index=True,
        comment="generating | ready | failed",
    )
    format: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pdf",
        comment="pdf | pptx | docx | json",
    )
    content: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Structured report content: sections, charts, findings, recommendations",
    )
    artifact_url: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
        comment="Storage URL for the generated report file",
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Error detail if status=failed",
    )
    generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when report generation completed",
    )
    report_metadata: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Generation parameters: include_benchmarks, roadmap_id, template_version",
    )

    assessment: Mapped["Assessment"] = relationship(
        "Assessment",
        back_populates="reports",
    )


# ---------------------------------------------------------------------------
# GAP-286: Configurable dimension system
# ---------------------------------------------------------------------------


class MatDimensionConfig(Base):
    """Configurable assessment dimensions stored in the database.

    Platform-wide configuration record (not tenant-scoped). Dimensions
    are stored here rather than hardcoded so new dimensions can be added
    via migration without code changes.

    This class does NOT extend AumOSModel because dimension configs are
    platform-wide, not tenant-scoped.

    Table: mat_dimension_configs
    """

    __tablename__ = "mat_dimension_configs"

    id: Mapped[str] = mapped_column(
        String(100),
        primary_key=True,
        comment="Dimension slug, e.g. 'data', 'process', 'agentic_ai'",
    )
    display_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Human-readable dimension name",
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="What this dimension measures",
    )
    default_weight: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Default weighting factor when this dimension is included",
    )
    question_bank: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment=(
            "Diagnostic questions: "
            "[{id, text, scoring_guidance}]"
        ),
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="False = dimension is archived and not offered in new assessments",
    )
    introduced_in_version: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Platform version when this dimension was first available",
    )
    framework_alignment: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Industry framework this dimension aligns to, if any",
    )


# ---------------------------------------------------------------------------
# GAP-287: Opt-in benchmark contribution consent
# ---------------------------------------------------------------------------


class MatBenchmarkContributionConsent(AumOSModel):
    """Opt-in consent for anonymous benchmark data contribution.

    When a tenant consents, their anonymized assessment scores are
    included in quarterly benchmark enrichment aggregations.

    Minimum 30 consenting tenants are required before any benchmark
    segment is updated to protect tenant privacy.

    Table: mat_benchmark_contribution_consents
    """

    __tablename__ = "mat_benchmark_contribution_consents"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            name="uq_mat_benchmark_consent_tenant",
        ),
    )

    consented: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="True when the tenant has opted in to anonymous data contribution",
    )
    consented_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when consent was most recently granted",
    )
    consent_version: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="Consent policy version at time of agreement (for audit trail)",
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when consent was revoked, if applicable",
    )
