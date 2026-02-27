"""Repository for the AI Readiness Assessment lead magnet data layer.

Implements CRUD operations for LMAssessmentResponse, LMAssessmentResult,
and LMAssessmentBenchmark using SQLAlchemy 2.0 async ORM. All database
operations are async and use parameterised queries exclusively.
"""

import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from aumos_common.observability import get_logger

from aumos_maturity_assessment.core.models.assessment import (
    LMAssessmentBenchmark,
    LMAssessmentResponse,
    LMAssessmentResult,
)

logger = get_logger(__name__)


class AssessmentResponseRepository:
    """Repository for LMAssessmentResponse persistence.

    Handles storage and retrieval of individual question answers
    grouped by assessment session.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialise with an async database session.

        Args:
            session: SQLAlchemy async session.
        """
        self._session = session

    async def create_response(
        self,
        session_id: uuid.UUID,
        question_id: str,
        answer_value: int,
        industry_vertical: str,
        answered_at: datetime,
    ) -> LMAssessmentResponse:
        """Persist a single question answer.

        Args:
            session_id: Assessment session UUID.
            question_id: Question identifier from the question bank.
            answer_value: Likert answer 1-5.
            industry_vertical: Respondent's industry vertical.
            answered_at: Timestamp when the answer was submitted.

        Returns:
            The persisted LMAssessmentResponse record.
        """
        record = LMAssessmentResponse(
            session_id=session_id,
            question_id=question_id,
            answer_value=answer_value,
            industry_vertical=industry_vertical,
            answered_at=answered_at,
        )
        self._session.add(record)
        await self._session.flush()
        await self._session.refresh(record)

        logger.debug(
            "Answer persisted",
            session_id=str(session_id),
            question_id=question_id,
            answer_value=answer_value,
        )
        return record

    async def get_responses_by_session(
        self,
        session_id: uuid.UUID,
    ) -> list[LMAssessmentResponse]:
        """Retrieve all answers for an assessment session.

        Args:
            session_id: Assessment session UUID.

        Returns:
            List of LMAssessmentResponse records ordered by answered_at.
        """
        result = await self._session.execute(
            select(LMAssessmentResponse)
            .where(LMAssessmentResponse.session_id == session_id)
            .order_by(LMAssessmentResponse.answered_at)
        )
        return list(result.scalars().all())

    async def count_responses_by_session(
        self,
        session_id: uuid.UUID,
    ) -> int:
        """Count the number of answers submitted for a session.

        Args:
            session_id: Assessment session UUID.

        Returns:
            Number of answer records for this session.
        """
        from sqlalchemy import func

        result = await self._session.execute(
            select(func.count(LMAssessmentResponse.id)).where(
                LMAssessmentResponse.session_id == session_id
            )
        )
        return int(result.scalar_one())


class AssessmentResultRepository:
    """Repository for LMAssessmentResult persistence.

    Handles storage and retrieval of finalised assessment results
    including scores, maturity level, and CRM sync status.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialise with an async database session.

        Args:
            session: SQLAlchemy async session.
        """
        self._session = session

    async def create_result(
        self,
        session_id: uuid.UUID,
        email: str,
        company_name: str,
        overall_score: float,
        dimension_scores: dict[str, float],
        maturity_level: int,
        industry_vertical: str,
        peer_percentile: float,
    ) -> LMAssessmentResult:
        """Persist a completed assessment result.

        Args:
            session_id: Assessment session UUID.
            email: Contact email for lead capture.
            company_name: Organisation name.
            overall_score: Composite score 0-100.
            dimension_scores: Per-dimension scores dict.
            maturity_level: Maturity level 1-5.
            industry_vertical: Respondent's industry vertical.
            peer_percentile: Estimated peer percentile 0-100.

        Returns:
            The persisted LMAssessmentResult record.
        """
        record = LMAssessmentResult(
            session_id=session_id,
            email=email,
            company_name=company_name,
            overall_score=overall_score,
            dimension_scores=dimension_scores,
            maturity_level=maturity_level,
            industry_vertical=industry_vertical,
            peer_percentile=peer_percentile,
            crm_sync_status="pending",
        )
        self._session.add(record)
        await self._session.flush()
        await self._session.refresh(record)

        logger.info(
            "Assessment result persisted",
            session_id=str(session_id),
            email=email,
            overall_score=overall_score,
            maturity_level=maturity_level,
        )
        return record

    async def get_result_by_session(
        self,
        session_id: uuid.UUID,
    ) -> LMAssessmentResult | None:
        """Retrieve the result for a given assessment session.

        Args:
            session_id: Assessment session UUID.

        Returns:
            LMAssessmentResult or None if not yet completed.
        """
        result = await self._session.execute(
            select(LMAssessmentResult).where(
                LMAssessmentResult.session_id == session_id
            )
        )
        return result.scalar_one_or_none()

    async def update_crm_sync_status(
        self,
        result_id: uuid.UUID,
        crm_sync_status: str,
    ) -> LMAssessmentResult:
        """Update the CRM synchronisation status for a result record.

        Args:
            result_id: Result record UUID.
            crm_sync_status: New status value: pending | synced | failed | skipped.

        Returns:
            The updated LMAssessmentResult record.
        """
        await self._session.execute(
            update(LMAssessmentResult)
            .where(LMAssessmentResult.id == result_id)
            .values(crm_sync_status=crm_sync_status)
        )
        result = await self._session.execute(
            select(LMAssessmentResult).where(LMAssessmentResult.id == result_id)
        )
        return result.scalar_one()


class AssessmentBenchmarkRepository:
    """Repository for LMAssessmentBenchmark persistence.

    Handles storage and retrieval of industry benchmark percentile data
    used for peer comparison in assessment results.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialise with an async database session.

        Args:
            session: SQLAlchemy async session.
        """
        self._session = session

    async def get_benchmarks_by_industry(
        self,
        industry_vertical: str,
    ) -> list[LMAssessmentBenchmark]:
        """Retrieve all benchmark records for an industry vertical.

        Args:
            industry_vertical: Industry vertical to query.

        Returns:
            List of LMAssessmentBenchmark records, one per dimension.
        """
        result = await self._session.execute(
            select(LMAssessmentBenchmark)
            .where(LMAssessmentBenchmark.industry_vertical == industry_vertical)
            .order_by(LMAssessmentBenchmark.dimension)
        )
        return list(result.scalars().all())

    async def upsert_benchmark(
        self,
        industry_vertical: str,
        dimension: str,
        p25_score: float,
        p50_score: float,
        p75_score: float,
        sample_size: int,
    ) -> LMAssessmentBenchmark:
        """Create or update a benchmark record for an industry+dimension pair.

        Attempts to update an existing record; creates a new one if none exists.

        Args:
            industry_vertical: Industry vertical.
            dimension: Assessment dimension.
            p25_score: 25th percentile score.
            p50_score: Median score.
            p75_score: 75th percentile score.
            sample_size: Number of contributing sessions.

        Returns:
            The created or updated LMAssessmentBenchmark record.
        """
        existing_result = await self._session.execute(
            select(LMAssessmentBenchmark).where(
                LMAssessmentBenchmark.industry_vertical == industry_vertical,
                LMAssessmentBenchmark.dimension == dimension,
            )
        )
        existing = existing_result.scalar_one_or_none()

        if existing is not None:
            await self._session.execute(
                update(LMAssessmentBenchmark)
                .where(LMAssessmentBenchmark.id == existing.id)
                .values(
                    p25_score=p25_score,
                    p50_score=p50_score,
                    p75_score=p75_score,
                    sample_size=sample_size,
                )
            )
            await self._session.refresh(existing)
            return existing

        record = LMAssessmentBenchmark(
            industry_vertical=industry_vertical,
            dimension=dimension,
            p25_score=p25_score,
            p50_score=p50_score,
            p75_score=p75_score,
            sample_size=sample_size,
        )
        self._session.add(record)
        await self._session.flush()
        await self._session.refresh(record)
        return record

    async def update_benchmarks(
        self,
        industry_vertical: str,
        benchmarks: list[dict[str, object]],
    ) -> list[LMAssessmentBenchmark]:
        """Bulk upsert benchmark records for an industry vertical.

        Args:
            industry_vertical: Industry vertical to update.
            benchmarks: List of dicts with keys: dimension, p25_score,
                p50_score, p75_score, sample_size.

        Returns:
            List of created or updated LMAssessmentBenchmark records.
        """
        results: list[LMAssessmentBenchmark] = []
        for benchmark_data in benchmarks:
            record = await self.upsert_benchmark(
                industry_vertical=industry_vertical,
                dimension=str(benchmark_data["dimension"]),
                p25_score=float(benchmark_data.get("p25_score", 0.0)),
                p50_score=float(benchmark_data.get("p50_score", 50.0)),
                p75_score=float(benchmark_data.get("p75_score", 75.0)),
                sample_size=int(benchmark_data.get("sample_size", 0)),
            )
            results.append(record)
        return results
