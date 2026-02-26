"""SQLAlchemy repository implementations for the Maturity Assessment service.

All repositories extend BaseRepository from aumos-common and implement
the interfaces defined in core/interfaces.py. RLS tenant isolation is
enforced automatically via the DB session (SET app.current_tenant).
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from aumos_common.database import BaseRepository
from aumos_common.observability import get_logger

from aumos_maturity_assessment.core.models import (
    Assessment,
    AssessmentResponse,
    Benchmark,
    Pilot,
    Report,
    Roadmap,
)

logger = get_logger(__name__)


class AssessmentRepository(BaseRepository):
    """Repository for Assessment persistence."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialise with async database session.

        Args:
            session: SQLAlchemy async session (RLS context pre-set by aumos-common).
        """
        super().__init__(session, Assessment)

    async def create(
        self,
        tenant_id: uuid.UUID,
        organization_name: str,
        industry: str,
        organization_size: str,
        dimension_weights: dict[str, float],
        assessment_metadata: dict[str, Any],
        initiated_by: uuid.UUID | None,
    ) -> Assessment:
        """Create a new assessment record.

        Args:
            tenant_id: Owning tenant UUID.
            organization_name: Name of the organization.
            industry: Industry vertical.
            organization_size: Organization size segment.
            dimension_weights: Per-dimension scoring weights.
            assessment_metadata: Additional context.
            initiated_by: Optional initiating user UUID.

        Returns:
            Newly created Assessment.
        """
        assessment = Assessment(
            tenant_id=tenant_id,
            organization_name=organization_name,
            industry=industry,
            organization_size=organization_size,
            dimension_weights=dimension_weights,
            assessment_metadata=assessment_metadata,
            initiated_by=initiated_by,
            status="in_progress",
        )
        self.session.add(assessment)
        await self.session.flush()
        await self.session.refresh(assessment)
        return assessment

    async def get_by_id(
        self, assessment_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> Assessment | None:
        """Retrieve an assessment by ID within a tenant.

        Args:
            assessment_id: Assessment UUID.
            tenant_id: Requesting tenant for RLS enforcement.

        Returns:
            Assessment or None if not found.
        """
        result = await self.session.execute(
            select(Assessment).where(
                Assessment.id == assessment_id,
                Assessment.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_tenant(
        self,
        tenant_id: uuid.UUID,
        page: int,
        page_size: int,
        status: str | None,
        industry: str | None,
    ) -> tuple[list[Assessment], int]:
        """List assessments for a tenant with pagination.

        Args:
            tenant_id: Requesting tenant.
            page: 1-based page number.
            page_size: Results per page.
            status: Optional status filter.
            industry: Optional industry filter.

        Returns:
            Tuple of (assessments, total_count).
        """
        query = select(Assessment).where(Assessment.tenant_id == tenant_id)
        count_query = select(func.count(Assessment.id)).where(
            Assessment.tenant_id == tenant_id
        )

        if status:
            query = query.where(Assessment.status == status)
            count_query = count_query.where(Assessment.status == status)

        if industry:
            query = query.where(Assessment.industry == industry)
            count_query = count_query.where(Assessment.industry == industry)

        total_result = await self.session.execute(count_query)
        total = total_result.scalar_one()

        offset = (page - 1) * page_size
        result = await self.session.execute(
            query.order_by(Assessment.created_at.desc()).offset(offset).limit(page_size)
        )
        return list(result.scalars().all()), total

    async def update_scores(
        self,
        assessment_id: uuid.UUID,
        overall_score: float,
        maturity_level: int,
        data_score: float,
        process_score: float,
        people_score: float,
        technology_score: float,
        governance_score: float,
        completed_at: datetime,
    ) -> Assessment:
        """Update computed dimension scores and mark as completed.

        Args:
            assessment_id: Assessment UUID.
            overall_score: Weighted composite score.
            maturity_level: Computed maturity level 1-5.
            data_score: Data dimension score.
            process_score: Process dimension score.
            people_score: People dimension score.
            technology_score: Technology dimension score.
            governance_score: Governance dimension score.
            completed_at: Completion timestamp.

        Returns:
            Updated Assessment.
        """
        await self.session.execute(
            update(Assessment)
            .where(Assessment.id == assessment_id)
            .values(
                overall_score=overall_score,
                maturity_level=maturity_level,
                data_score=data_score,
                process_score=process_score,
                people_score=people_score,
                technology_score=technology_score,
                governance_score=governance_score,
                completed_at=completed_at,
                status="completed",
            )
        )
        result = await self.session.execute(
            select(Assessment).where(Assessment.id == assessment_id)
        )
        return result.scalar_one()

    async def update_status(
        self,
        assessment_id: uuid.UUID,
        status: str,
    ) -> Assessment:
        """Update assessment status.

        Args:
            assessment_id: Assessment UUID.
            status: New status value.

        Returns:
            Updated Assessment.
        """
        await self.session.execute(
            update(Assessment)
            .where(Assessment.id == assessment_id)
            .values(status=status)
        )
        result = await self.session.execute(
            select(Assessment).where(Assessment.id == assessment_id)
        )
        return result.scalar_one()


class AssessmentResponseRepository(BaseRepository):
    """Repository for AssessmentResponse persistence."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialise with async database session.

        Args:
            session: SQLAlchemy async session.
        """
        super().__init__(session, AssessmentResponse)

    async def create_bulk(
        self,
        tenant_id: uuid.UUID,
        assessment_id: uuid.UUID,
        responses: list[dict[str, Any]],
    ) -> list[AssessmentResponse]:
        """Bulk-create response records.

        Args:
            tenant_id: Owning tenant UUID.
            assessment_id: Parent assessment UUID.
            responses: List of response attribute dicts.

        Returns:
            List of created AssessmentResponse records.
        """
        records = [
            AssessmentResponse(
                tenant_id=tenant_id,
                assessment_id=assessment_id,
                question_id=r["question_id"],
                dimension=r["dimension"],
                response_value=r["response_value"],
                numeric_score=r.get("numeric_score"),
                weight=r.get("weight", 1.0),
                response_metadata=r.get("response_metadata", {}),
            )
            for r in responses
        ]
        self.session.add_all(records)
        await self.session.flush()
        for rec in records:
            await self.session.refresh(rec)
        return records

    async def list_by_assessment(
        self,
        assessment_id: uuid.UUID,
        dimension: str | None,
    ) -> list[AssessmentResponse]:
        """List responses for an assessment, optionally filtered by dimension.

        Args:
            assessment_id: Parent assessment UUID.
            dimension: Optional dimension filter.

        Returns:
            List of AssessmentResponse records.
        """
        query = select(AssessmentResponse).where(
            AssessmentResponse.assessment_id == assessment_id
        )
        if dimension:
            query = query.where(AssessmentResponse.dimension == dimension)
        result = await self.session.execute(query.order_by(AssessmentResponse.created_at))
        return list(result.scalars().all())


class BenchmarkRepository(BaseRepository):
    """Repository for Benchmark persistence."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialise with async database session.

        Args:
            session: SQLAlchemy async session.
        """
        super().__init__(session, Benchmark)

    async def create(
        self,
        tenant_id: uuid.UUID,
        industry: str,
        organization_size: str,
        benchmark_period: str,
        sample_size: int,
        overall_p25: float,
        overall_p50: float,
        overall_p75: float,
        overall_p90: float,
        data_p50: float,
        process_p50: float,
        people_p50: float,
        technology_p50: float,
        governance_p50: float,
        dimension_breakdowns: dict[str, Any],
        top_strengths: list[str],
        top_gaps: list[str],
    ) -> Benchmark:
        """Create a benchmark record.

        Args:
            tenant_id: Owning tenant UUID.
            industry: Industry vertical.
            organization_size: Organization size segment.
            benchmark_period: Period identifier.
            sample_size: Contributing organization count.
            overall_p25: 25th percentile overall score.
            overall_p50: Median overall score.
            overall_p75: 75th percentile overall score.
            overall_p90: 90th percentile overall score.
            data_p50: Median data score.
            process_p50: Median process score.
            people_p50: Median people score.
            technology_p50: Median technology score.
            governance_p50: Median governance score.
            dimension_breakdowns: Full distribution per dimension.
            top_strengths: Top industry strengths.
            top_gaps: Top industry gaps.

        Returns:
            Created Benchmark.
        """
        benchmark = Benchmark(
            tenant_id=tenant_id,
            industry=industry,
            organization_size=organization_size,
            benchmark_period=benchmark_period,
            sample_size=sample_size,
            overall_p25=overall_p25,
            overall_p50=overall_p50,
            overall_p75=overall_p75,
            overall_p90=overall_p90,
            data_p50=data_p50,
            process_p50=process_p50,
            people_p50=people_p50,
            technology_p50=technology_p50,
            governance_p50=governance_p50,
            dimension_breakdowns=dimension_breakdowns,
            top_strengths=top_strengths,
            top_gaps=top_gaps,
            is_active=True,
        )
        self.session.add(benchmark)
        await self.session.flush()
        await self.session.refresh(benchmark)
        return benchmark

    async def get_active_benchmark(
        self,
        tenant_id: uuid.UUID,
        industry: str,
        organization_size: str,
    ) -> Benchmark | None:
        """Get the most recent active benchmark for an industry+size segment.

        Args:
            tenant_id: Requesting tenant.
            industry: Industry vertical.
            organization_size: Organization size segment.

        Returns:
            Most recent active Benchmark or None.
        """
        result = await self.session.execute(
            select(Benchmark)
            .where(
                Benchmark.tenant_id == tenant_id,
                Benchmark.industry == industry,
                Benchmark.organization_size == organization_size,
                Benchmark.is_active == True,  # noqa: E712
            )
            .order_by(Benchmark.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_by_industry(
        self,
        tenant_id: uuid.UUID,
        industry: str,
    ) -> list[Benchmark]:
        """List all benchmarks for an industry (all size segments).

        Args:
            tenant_id: Requesting tenant.
            industry: Industry vertical.

        Returns:
            List of Benchmark records.
        """
        result = await self.session.execute(
            select(Benchmark)
            .where(
                Benchmark.tenant_id == tenant_id,
                Benchmark.industry == industry,
            )
            .order_by(Benchmark.created_at.desc())
        )
        return list(result.scalars().all())


class RoadmapRepository(BaseRepository):
    """Repository for Roadmap persistence."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialise with async database session.

        Args:
            session: SQLAlchemy async session.
        """
        super().__init__(session, Roadmap)

    async def create(
        self,
        tenant_id: uuid.UUID,
        assessment_id: uuid.UUID,
        title: str,
        horizon_months: int,
        target_maturity_level: int,
        initiatives: list[dict[str, Any]],
        quick_wins: list[dict[str, Any]],
        estimated_roi_multiplier: float | None,
        roadmap_metadata: dict[str, Any],
    ) -> Roadmap:
        """Create a roadmap record.

        Args:
            tenant_id: Owning tenant UUID.
            assessment_id: Parent assessment UUID.
            title: Roadmap title.
            horizon_months: Planning horizon in months.
            target_maturity_level: Target maturity level 1-5.
            initiatives: Generated initiative list.
            quick_wins: Quick win initiatives subset.
            estimated_roi_multiplier: Optional ROI estimate.
            roadmap_metadata: Generation context.

        Returns:
            Created Roadmap.
        """
        roadmap = Roadmap(
            tenant_id=tenant_id,
            assessment_id=assessment_id,
            title=title,
            horizon_months=horizon_months,
            target_maturity_level=target_maturity_level,
            initiatives=initiatives,
            quick_wins=quick_wins,
            estimated_roi_multiplier=estimated_roi_multiplier,
            roadmap_metadata=roadmap_metadata,
            status="draft",
        )
        self.session.add(roadmap)
        await self.session.flush()
        await self.session.refresh(roadmap)
        return roadmap

    async def get_by_id(
        self, roadmap_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> Roadmap | None:
        """Retrieve a roadmap by ID.

        Args:
            roadmap_id: Roadmap UUID.
            tenant_id: Requesting tenant.

        Returns:
            Roadmap or None.
        """
        result = await self.session.execute(
            select(Roadmap).where(
                Roadmap.id == roadmap_id,
                Roadmap.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def update_status(
        self,
        roadmap_id: uuid.UUID,
        status: str,
        published_at: datetime | None,
    ) -> Roadmap:
        """Update roadmap publish status.

        Args:
            roadmap_id: Roadmap UUID.
            status: New status value.
            published_at: Optional publish timestamp.

        Returns:
            Updated Roadmap.
        """
        values: dict[str, Any] = {"status": status}
        if published_at is not None:
            values["published_at"] = published_at

        await self.session.execute(
            update(Roadmap).where(Roadmap.id == roadmap_id).values(**values)
        )
        result = await self.session.execute(
            select(Roadmap).where(Roadmap.id == roadmap_id)
        )
        return result.scalar_one()


class PilotRepository(BaseRepository):
    """Repository for Pilot persistence."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialise with async database session.

        Args:
            session: SQLAlchemy async session.
        """
        super().__init__(session, Pilot)

    async def create(
        self,
        tenant_id: uuid.UUID,
        roadmap_id: uuid.UUID,
        title: str,
        dimension: str,
        duration_weeks: int,
        success_criteria: list[dict[str, Any]],
        failure_modes: list[dict[str, Any]],
        stakeholder_map: dict[str, Any],
        resource_requirements: dict[str, Any],
    ) -> Pilot:
        """Create a pilot design record.

        Args:
            tenant_id: Owning tenant UUID.
            roadmap_id: Parent roadmap UUID.
            title: Pilot title.
            dimension: Primary dimension addressed.
            duration_weeks: Planned duration in weeks.
            success_criteria: Measurable success criteria.
            failure_modes: Pre-identified failure modes.
            stakeholder_map: Role to stakeholder mapping.
            resource_requirements: Required resources.

        Returns:
            Created Pilot.
        """
        pilot = Pilot(
            tenant_id=tenant_id,
            roadmap_id=roadmap_id,
            title=title,
            dimension=dimension,
            duration_weeks=duration_weeks,
            success_criteria=success_criteria,
            failure_modes=failure_modes,
            stakeholder_map=stakeholder_map,
            resource_requirements=resource_requirements,
            status="designed",
        )
        self.session.add(pilot)
        await self.session.flush()
        await self.session.refresh(pilot)
        return pilot

    async def get_by_id(
        self, pilot_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> Pilot | None:
        """Retrieve a pilot by ID.

        Args:
            pilot_id: Pilot UUID.
            tenant_id: Requesting tenant.

        Returns:
            Pilot or None.
        """
        result = await self.session.execute(
            select(Pilot).where(
                Pilot.id == pilot_id,
                Pilot.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def update_status(
        self,
        pilot_id: uuid.UUID,
        status: str,
        started_at: datetime | None,
        completed_at: datetime | None,
    ) -> Pilot:
        """Update pilot execution status and timestamps.

        Args:
            pilot_id: Pilot UUID.
            status: New status value.
            started_at: Optional start timestamp.
            completed_at: Optional completion timestamp.

        Returns:
            Updated Pilot.
        """
        values: dict[str, Any] = {"status": status}
        if started_at is not None:
            values["started_at"] = started_at
        if completed_at is not None:
            values["completed_at"] = completed_at

        await self.session.execute(
            update(Pilot).where(Pilot.id == pilot_id).values(**values)
        )
        result = await self.session.execute(select(Pilot).where(Pilot.id == pilot_id))
        return result.scalar_one()

    async def append_execution_log(
        self,
        pilot_id: uuid.UUID,
        log_entry: dict[str, Any],
    ) -> Pilot:
        """Append a weekly update to the execution log via JSONB concatenation.

        Args:
            pilot_id: Pilot UUID.
            log_entry: Weekly update dict.

        Returns:
            Updated Pilot with appended log entry.
        """
        from sqlalchemy import text

        await self.session.execute(
            text(
                "UPDATE mat_pilots SET execution_log = execution_log || :entry::jsonb "
                "WHERE id = :pilot_id"
            ),
            {
                "entry": f"[{__import__('json').dumps(log_entry)}]",
                "pilot_id": str(pilot_id),
            },
        )
        result = await self.session.execute(select(Pilot).where(Pilot.id == pilot_id))
        return result.scalar_one()

    async def update_outcomes(
        self,
        pilot_id: uuid.UUID,
        outcome_metrics: dict[str, Any],
        success_score: float,
    ) -> Pilot:
        """Record final pilot outcome metrics and success score.

        Args:
            pilot_id: Pilot UUID.
            outcome_metrics: Actual measured outcomes.
            success_score: 0-100 success score.

        Returns:
            Updated Pilot.
        """
        await self.session.execute(
            update(Pilot)
            .where(Pilot.id == pilot_id)
            .values(outcome_metrics=outcome_metrics, success_score=success_score)
        )
        result = await self.session.execute(select(Pilot).where(Pilot.id == pilot_id))
        return result.scalar_one()


class ReportRepository(BaseRepository):
    """Repository for Report persistence."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialise with async database session.

        Args:
            session: SQLAlchemy async session.
        """
        super().__init__(session, Report)

    async def create(
        self,
        tenant_id: uuid.UUID,
        assessment_id: uuid.UUID,
        title: str,
        report_type: str,
        format: str,
        report_metadata: dict[str, Any],
    ) -> Report:
        """Create a report record in generating status.

        Args:
            tenant_id: Owning tenant UUID.
            assessment_id: Parent assessment UUID.
            title: Report title.
            report_type: Type of report.
            format: Output format.
            report_metadata: Generation parameters.

        Returns:
            Created Report in generating status.
        """
        report = Report(
            tenant_id=tenant_id,
            assessment_id=assessment_id,
            title=title,
            report_type=report_type,
            format=format,
            report_metadata=report_metadata,
            status="generating",
        )
        self.session.add(report)
        await self.session.flush()
        await self.session.refresh(report)
        return report

    async def get_by_id(
        self, report_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> Report | None:
        """Retrieve a report by ID.

        Args:
            report_id: Report UUID.
            tenant_id: Requesting tenant.

        Returns:
            Report or None.
        """
        result = await self.session.execute(
            select(Report).where(
                Report.id == report_id,
                Report.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def mark_ready(
        self,
        report_id: uuid.UUID,
        content: dict[str, Any],
        artifact_url: str | None,
        generated_at: datetime,
    ) -> Report:
        """Mark report as ready with its generated content.

        Args:
            report_id: Report UUID.
            content: Structured report content.
            artifact_url: Optional storage URL.
            generated_at: Generation completion timestamp.

        Returns:
            Updated Report in ready status.
        """
        await self.session.execute(
            update(Report)
            .where(Report.id == report_id)
            .values(
                status="ready",
                content=content,
                artifact_url=artifact_url,
                generated_at=generated_at,
            )
        )
        result = await self.session.execute(select(Report).where(Report.id == report_id))
        return result.scalar_one()

    async def mark_failed(
        self,
        report_id: uuid.UUID,
        error_message: str,
    ) -> Report:
        """Mark report generation as failed.

        Args:
            report_id: Report UUID.
            error_message: Failure detail.

        Returns:
            Updated Report in failed status.
        """
        await self.session.execute(
            update(Report)
            .where(Report.id == report_id)
            .values(status="failed", error_message=error_message)
        )
        result = await self.session.execute(select(Report).where(Report.id == report_id))
        return result.scalar_one()
