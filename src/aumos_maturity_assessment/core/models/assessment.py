"""SQLAlchemy ORM models for the AI Readiness Assessment lead magnet.

These tables support the self-service assessment flow (no auth required)
used for lead capture. They are separate from the enterprise assessment
models in core/models.py which require tenant context.

Tables:
    lm_assessment_responses  — individual question answers per session
    lm_assessment_results    — finalised scores and roadmap per session
    lm_assessment_benchmarks — industry benchmark percentiles per dimension
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class LeadMagnetBase(DeclarativeBase):
    """Base class for lead magnet ORM models."""


class LMAssessmentResponse(LeadMagnetBase):
    """A single question answer within a self-service assessment session.

    Each row represents one answered question. Multiple rows share a
    session_id. No tenant isolation — sessions are anonymous until
    the email gate is passed at completion.

    Table: lm_assessment_responses
    """

    __tablename__ = "lm_assessment_responses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Primary key UUID",
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="Groups all answers belonging to one assessment session",
    )
    question_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Question identifier from the diagnostic question bank (e.g. DATA_01)",
    )
    answer_value: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Likert-scale answer 1-5 (1=Not at all, 5=Fully implemented)",
    )
    answered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Timestamp when this answer was submitted",
    )
    industry_vertical: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Industry vertical provided at session start",
    )


class LMAssessmentResult(LeadMagnetBase):
    """Finalised AI readiness assessment result for a completed session.

    Created when the respondent submits their contact email and triggers
    scoring. One result row per session.

    Table: lm_assessment_results
    """

    __tablename__ = "lm_assessment_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Primary key UUID",
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        unique=True,
        index=True,
        comment="Reference to the assessment session in lm_assessment_responses",
    )
    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="Contact email used for lead capture and result delivery",
    )
    company_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Organisation name provided at completion",
    )
    overall_score: Mapped[float] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        comment="Weighted composite AI readiness score 0-100",
    )
    dimension_scores: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
        comment=(
            "Per-dimension scores 0-100: "
            "{data_infrastructure, governance, talent_culture, "
            "technology_stack, security_posture, strategic_alignment}"
        ),
    )
    maturity_level: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Overall maturity level 1-5: 1=Initial, 2=Developing, 3=Defined, 4=Managed, 5=Optimizing",
    )
    industry_vertical: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Industry vertical for benchmark comparison",
    )
    peer_percentile: Mapped[float] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=50.0,
        comment="Estimated peer percentile position within industry vertical (0-100)",
    )
    crm_sync_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
        comment="CRM synchronisation status: pending | synced | failed | skipped",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="When this result record was created",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="When this result record was last updated",
    )


class LMAssessmentBenchmark(LeadMagnetBase):
    """Industry benchmark percentile data for a dimension.

    Provides p25/p50/p75 score benchmarks per industry vertical and
    dimension to support peer percentile calculation and comparison charts.

    Table: lm_assessment_benchmarks
    """

    __tablename__ = "lm_assessment_benchmarks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Primary key UUID",
    )
    industry_vertical: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Industry vertical this benchmark covers",
    )
    dimension: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Assessment dimension: data_infrastructure | governance | talent_culture | ...",
    )
    p25_score: Mapped[float] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        comment="25th percentile score for this industry+dimension combination",
    )
    p50_score: Mapped[float] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        comment="Median (50th percentile) score",
    )
    p75_score: Mapped[float] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        comment="75th percentile score",
    )
    sample_size: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of assessment sessions contributing to this benchmark",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="When these benchmark figures were last recalculated",
    )
