"""mat: initial schema — assessments, responses, benchmarks, roadmaps, pilots, reports.

Revision ID: mat_001_initial
Revises:
Create Date: 2024-01-01 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "mat_001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create all mat_ tables with RLS policies."""
    # mat_assessments
    op.create_table(
        "mat_assessments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("organization_name", sa.String(255), nullable=False),
        sa.Column("industry", sa.String(100), nullable=False),
        sa.Column("organization_size", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="in_progress"),
        sa.Column("overall_score", sa.Float, nullable=True),
        sa.Column("maturity_level", sa.Integer, nullable=True),
        sa.Column("data_score", sa.Float, nullable=True),
        sa.Column("process_score", sa.Float, nullable=True),
        sa.Column("people_score", sa.Float, nullable=True),
        sa.Column("technology_score", sa.Float, nullable=True),
        sa.Column("governance_score", sa.Float, nullable=True),
        sa.Column(
            "dimension_weights",
            postgresql.JSONB,
            nullable=False,
            server_default='{"data":0.25,"process":0.20,"people":0.20,"technology":0.20,"governance":0.15}',
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("assessment_metadata", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("initiated_by", postgresql.UUID(as_uuid=True), nullable=True),
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
    op.create_index("ix_mat_assessments_tenant_id", "mat_assessments", ["tenant_id"])
    op.create_index("ix_mat_assessments_industry", "mat_assessments", ["industry"])
    op.create_index("ix_mat_assessments_status", "mat_assessments", ["status"])
    op.create_index(
        "ix_mat_assessments_org_name", "mat_assessments", ["organization_name"]
    )

    # mat_assessment_responses
    op.create_table(
        "mat_assessment_responses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column(
            "assessment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("mat_assessments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("question_id", sa.String(100), nullable=False),
        sa.Column("dimension", sa.String(50), nullable=False),
        sa.Column("response_value", sa.String(500), nullable=False),
        sa.Column("numeric_score", sa.Float, nullable=True),
        sa.Column("weight", sa.Float, nullable=False, server_default="1.0"),
        sa.Column("response_metadata", postgresql.JSONB, nullable=False, server_default="{}"),
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
        "ix_mat_assessment_responses_assessment_id",
        "mat_assessment_responses",
        ["assessment_id"],
    )
    op.create_index(
        "ix_mat_assessment_responses_dimension",
        "mat_assessment_responses",
        ["dimension"],
    )

    # mat_benchmarks
    op.create_table(
        "mat_benchmarks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("industry", sa.String(100), nullable=False),
        sa.Column("organization_size", sa.String(50), nullable=False),
        sa.Column("benchmark_period", sa.String(20), nullable=False),
        sa.Column("sample_size", sa.Integer, nullable=False, server_default="0"),
        sa.Column("overall_p25", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("overall_p50", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("overall_p75", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("overall_p90", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("data_p50", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("process_p50", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("people_p50", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("technology_p50", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("governance_p50", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("dimension_breakdowns", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("top_strengths", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("top_gaps", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
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
        sa.UniqueConstraint(
            "tenant_id",
            "industry",
            "organization_size",
            "benchmark_period",
            name="uq_mat_benchmarks_tenant_industry_size_period",
        ),
    )
    op.create_index("ix_mat_benchmarks_industry", "mat_benchmarks", ["industry"])
    op.create_index(
        "ix_mat_benchmarks_organization_size", "mat_benchmarks", ["organization_size"]
    )

    # mat_roadmaps
    op.create_table(
        "mat_roadmaps",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column(
            "assessment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("mat_assessments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("horizon_months", sa.Integer, nullable=False, server_default="18"),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("target_maturity_level", sa.Integer, nullable=False, server_default="3"),
        sa.Column("initiatives", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("quick_wins", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("estimated_roi_multiplier", sa.Float, nullable=True),
        sa.Column("roadmap_metadata", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
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
    op.create_index("ix_mat_roadmaps_assessment_id", "mat_roadmaps", ["assessment_id"])
    op.create_index("ix_mat_roadmaps_status", "mat_roadmaps", ["status"])

    # mat_pilots
    op.create_table(
        "mat_pilots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column(
            "roadmap_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("mat_roadmaps.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="designed"),
        sa.Column("dimension", sa.String(50), nullable=False),
        sa.Column("duration_weeks", sa.Integer, nullable=False, server_default="8"),
        sa.Column("success_criteria", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("failure_modes", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("stakeholder_map", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("resource_requirements", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("execution_log", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("outcome_metrics", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("success_score", sa.Float, nullable=True),
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
    op.create_index("ix_mat_pilots_roadmap_id", "mat_pilots", ["roadmap_id"])
    op.create_index("ix_mat_pilots_status", "mat_pilots", ["status"])
    op.create_index("ix_mat_pilots_dimension", "mat_pilots", ["dimension"])

    # mat_reports
    op.create_table(
        "mat_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column(
            "assessment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("mat_assessments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column(
            "report_type", sa.String(50), nullable=False, server_default="executive_summary"
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="generating"),
        sa.Column("format", sa.String(20), nullable=False, server_default="pdf"),
        sa.Column("content", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("artifact_url", sa.String(1000), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("report_metadata", postgresql.JSONB, nullable=False, server_default="{}"),
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
    op.create_index("ix_mat_reports_assessment_id", "mat_reports", ["assessment_id"])
    op.create_index("ix_mat_reports_status", "mat_reports", ["status"])

    # Enable RLS on all tenant-scoped tables
    for table in [
        "mat_assessments",
        "mat_assessment_responses",
        "mat_benchmarks",
        "mat_roadmaps",
        "mat_pilots",
        "mat_reports",
    ]:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY {table}_tenant_isolation ON {table}
            USING (tenant_id = current_setting('app.current_tenant')::uuid)
            """
        )


def downgrade() -> None:
    """Drop all mat_ tables."""
    for table in [
        "mat_reports",
        "mat_pilots",
        "mat_roadmaps",
        "mat_benchmarks",
        "mat_assessment_responses",
        "mat_assessments",
    ]:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
