"""lm: lead magnet assessment tables — responses, results, benchmarks.

Creates the three tables supporting the self-service AI Readiness Assessment
lead magnet flow. These tables do not use tenant isolation (anonymous flow)
but are scoped by session_id.

Revision ID: lm_001_assessment_tables
Revises: mat_001_initial
Create Date: 2024-02-01 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "lm_001_assessment_tables"
down_revision: str | None = "mat_001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create lm_assessment_responses, lm_assessment_results, and lm_assessment_benchmarks."""
    # lm_assessment_responses — individual question answers
    op.create_table(
        "lm_assessment_responses",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            index=True,
            comment="Groups all answers belonging to one assessment session",
        ),
        sa.Column(
            "question_id",
            sa.String(50),
            nullable=False,
            comment="Question identifier from the question bank (e.g. DATA_01)",
        ),
        sa.Column(
            "answer_value",
            sa.Integer,
            nullable=False,
            comment="Likert-scale answer 1-5",
        ),
        sa.Column(
            "answered_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
            comment="Timestamp when this answer was submitted",
        ),
        sa.Column(
            "industry_vertical",
            sa.String(100),
            nullable=False,
            comment="Industry vertical provided at session start",
        ),
    )
    op.create_index(
        "ix_lm_assessment_responses_session_id",
        "lm_assessment_responses",
        ["session_id"],
    )
    op.create_index(
        "ix_lm_assessment_responses_question_id",
        "lm_assessment_responses",
        ["question_id"],
    )

    # lm_assessment_results — finalised scores per session
    op.create_table(
        "lm_assessment_results",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            unique=True,
            comment="Reference to the assessment session",
        ),
        sa.Column(
            "email",
            sa.String(255),
            nullable=False,
            comment="Contact email for lead capture",
        ),
        sa.Column(
            "company_name",
            sa.String(255),
            nullable=False,
            comment="Organisation name provided at completion",
        ),
        sa.Column(
            "overall_score",
            sa.Numeric(5, 2),
            nullable=False,
            comment="Weighted composite AI readiness score 0-100",
        ),
        sa.Column(
            "dimension_scores",
            postgresql.JSONB,
            nullable=False,
            server_default="{}",
            comment="Per-dimension scores 0-100",
        ),
        sa.Column(
            "maturity_level",
            sa.Integer,
            nullable=False,
            comment="Overall maturity level 1-5",
        ),
        sa.Column(
            "industry_vertical",
            sa.String(100),
            nullable=False,
            comment="Industry vertical for benchmark comparison",
        ),
        sa.Column(
            "peer_percentile",
            sa.Numeric(5, 2),
            nullable=False,
            server_default="50.0",
            comment="Estimated peer percentile position 0-100",
        ),
        sa.Column(
            "crm_sync_status",
            sa.String(50),
            nullable=False,
            server_default="pending",
            comment="CRM sync status: pending | synced | failed | skipped",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_lm_assessment_results_session_id",
        "lm_assessment_results",
        ["session_id"],
        unique=True,
    )
    op.create_index(
        "ix_lm_assessment_results_email",
        "lm_assessment_results",
        ["email"],
    )
    op.create_index(
        "ix_lm_assessment_results_industry_vertical",
        "lm_assessment_results",
        ["industry_vertical"],
    )

    # lm_assessment_benchmarks — industry peer percentile data
    op.create_table(
        "lm_assessment_benchmarks",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "industry_vertical",
            sa.String(100),
            nullable=False,
            comment="Industry vertical this benchmark covers",
        ),
        sa.Column(
            "dimension",
            sa.String(50),
            nullable=False,
            comment="Assessment dimension",
        ),
        sa.Column(
            "p25_score",
            sa.Numeric(5, 2),
            nullable=False,
            comment="25th percentile score",
        ),
        sa.Column(
            "p50_score",
            sa.Numeric(5, 2),
            nullable=False,
            comment="Median score",
        ),
        sa.Column(
            "p75_score",
            sa.Numeric(5, 2),
            nullable=False,
            comment="75th percentile score",
        ),
        sa.Column(
            "sample_size",
            sa.Integer,
            nullable=False,
            server_default="0",
            comment="Number of contributing assessment sessions",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
            comment="When these benchmark figures were last recalculated",
        ),
        sa.UniqueConstraint(
            "industry_vertical",
            "dimension",
            name="uq_lm_assessment_benchmarks_industry_dimension",
        ),
    )
    op.create_index(
        "ix_lm_assessment_benchmarks_industry_vertical",
        "lm_assessment_benchmarks",
        ["industry_vertical"],
    )
    op.create_index(
        "ix_lm_assessment_benchmarks_dimension",
        "lm_assessment_benchmarks",
        ["dimension"],
    )


def downgrade() -> None:
    """Drop lm_ assessment tables."""
    for table in [
        "lm_assessment_benchmarks",
        "lm_assessment_results",
        "lm_assessment_responses",
    ]:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
