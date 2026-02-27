"""Abstract interfaces (Protocol classes) for the Maturity Assessment service.

All services depend on these interfaces, not concrete implementations.
This enables dependency injection and makes services independently testable.

The ``ILM*`` interfaces describe the repositories consumed by AssessmentService
(the lead-magnet anonymous assessment flow). Concrete implementations live in
``adapters/repositories/assessment_repository.py``.
"""

import uuid
from datetime import datetime
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class IAssessmentRepository(Protocol):
    """Repository interface for Assessment persistence."""

    async def create(
        self,
        tenant_id: uuid.UUID,
        organization_name: str,
        industry: str,
        organization_size: str,
        dimension_weights: dict[str, float],
        assessment_metadata: dict[str, Any],
        initiated_by: uuid.UUID | None,
    ) -> Any:
        """Create a new assessment record."""
        ...

    async def get_by_id(
        self, assessment_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> Any | None:
        """Retrieve an assessment by ID within a tenant."""
        ...

    async def list_by_tenant(
        self,
        tenant_id: uuid.UUID,
        page: int,
        page_size: int,
        status: str | None,
        industry: str | None,
    ) -> tuple[list[Any], int]:
        """List assessments for a tenant with pagination."""
        ...

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
    ) -> Any:
        """Update computed dimension and overall scores."""
        ...

    async def update_status(
        self,
        assessment_id: uuid.UUID,
        status: str,
    ) -> Any:
        """Update assessment status."""
        ...


@runtime_checkable
class IAssessmentResponseRepository(Protocol):
    """Repository interface for AssessmentResponse persistence."""

    async def create_bulk(
        self,
        tenant_id: uuid.UUID,
        assessment_id: uuid.UUID,
        responses: list[dict[str, Any]],
    ) -> list[Any]:
        """Bulk-create response records."""
        ...

    async def list_by_assessment(
        self,
        assessment_id: uuid.UUID,
        dimension: str | None,
    ) -> list[Any]:
        """List all responses for an assessment, optionally filtered by dimension."""
        ...


@runtime_checkable
class IBenchmarkRepository(Protocol):
    """Repository interface for Benchmark persistence."""

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
    ) -> Any:
        """Create a benchmark record."""
        ...

    async def get_active_benchmark(
        self,
        tenant_id: uuid.UUID,
        industry: str,
        organization_size: str,
    ) -> Any | None:
        """Get the most recent active benchmark for an industry+size segment."""
        ...

    async def list_by_industry(
        self,
        tenant_id: uuid.UUID,
        industry: str,
    ) -> list[Any]:
        """List all benchmarks for an industry (all size segments)."""
        ...


@runtime_checkable
class IRoadmapRepository(Protocol):
    """Repository interface for Roadmap persistence."""

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
    ) -> Any:
        """Create a roadmap record."""
        ...

    async def get_by_id(
        self, roadmap_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> Any | None:
        """Retrieve a roadmap by ID."""
        ...

    async def update_status(
        self,
        roadmap_id: uuid.UUID,
        status: str,
        published_at: datetime | None,
    ) -> Any:
        """Update roadmap publish status."""
        ...


@runtime_checkable
class IPilotRepository(Protocol):
    """Repository interface for Pilot persistence."""

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
    ) -> Any:
        """Create a pilot design record."""
        ...

    async def get_by_id(
        self, pilot_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> Any | None:
        """Retrieve a pilot by ID."""
        ...

    async def update_status(
        self,
        pilot_id: uuid.UUID,
        status: str,
        started_at: datetime | None,
        completed_at: datetime | None,
    ) -> Any:
        """Update pilot execution status."""
        ...

    async def append_execution_log(
        self,
        pilot_id: uuid.UUID,
        log_entry: dict[str, Any],
    ) -> Any:
        """Append a weekly update to the execution log."""
        ...

    async def update_outcomes(
        self,
        pilot_id: uuid.UUID,
        outcome_metrics: dict[str, Any],
        success_score: float,
    ) -> Any:
        """Record final pilot outcome metrics and success score."""
        ...


@runtime_checkable
class IReportRepository(Protocol):
    """Repository interface for Report persistence."""

    async def create(
        self,
        tenant_id: uuid.UUID,
        assessment_id: uuid.UUID,
        title: str,
        report_type: str,
        format: str,
        report_metadata: dict[str, Any],
    ) -> Any:
        """Create a report record in generating status."""
        ...

    async def get_by_id(
        self, report_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> Any | None:
        """Retrieve a report by ID."""
        ...

    async def mark_ready(
        self,
        report_id: uuid.UUID,
        content: dict[str, Any],
        artifact_url: str | None,
        generated_at: datetime,
    ) -> Any:
        """Mark report as ready with its generated content."""
        ...

    async def mark_failed(
        self,
        report_id: uuid.UUID,
        error_message: str,
    ) -> Any:
        """Mark report generation as failed."""
        ...


@runtime_checkable
class IScoringEngine(Protocol):
    """Interface for the maturity scoring computation engine."""

    async def compute_scores(
        self,
        responses: list[dict[str, Any]],
        dimension_weights: dict[str, float],
    ) -> dict[str, Any]:
        """Compute all dimension scores and overall maturity level.

        Args:
            responses: List of response dicts with numeric_score and dimension.
            dimension_weights: Per-dimension weighting factors.

        Returns:
            Dict with overall_score, maturity_level, and per-dimension scores.
        """
        ...


@runtime_checkable
class IRoadmapGeneratorAdapter(Protocol):
    """Interface for the roadmap generation adapter."""

    async def generate(
        self,
        assessment: Any,
        benchmark: Any | None,
        horizon_months: int,
        target_maturity_level: int,
    ) -> dict[str, Any]:
        """Generate roadmap initiatives from assessment scores.

        Args:
            assessment: Completed Assessment with dimension scores.
            benchmark: Optional industry benchmark for peer comparison.
            horizon_months: Planning horizon in months.
            target_maturity_level: Target maturity level to achieve.

        Returns:
            Dict with initiatives, quick_wins, and estimated_roi_multiplier.
        """
        ...


@runtime_checkable
class IReportGeneratorAdapter(Protocol):
    """Interface for the report generation adapter."""

    async def generate(
        self,
        assessment: Any,
        benchmark: Any | None,
        roadmap: Any | None,
        report_type: str,
        format: str,
        include_benchmarks: bool,
    ) -> dict[str, Any]:
        """Generate a structured report from assessment data.

        Args:
            assessment: Completed Assessment with dimension scores.
            benchmark: Optional industry benchmark for comparison.
            roadmap: Optional associated roadmap.
            report_type: Type of report to generate.
            format: Output format (pdf, pptx, docx, json).
            include_benchmarks: Whether to include benchmark data.

        Returns:
            Dict with content and optional artifact_url.
        """
        ...


# ---------------------------------------------------------------------------
# Lead-magnet (anonymous self-service) repository interfaces
# ---------------------------------------------------------------------------


@runtime_checkable
class ILMResponseRepository(Protocol):
    """Repository interface for LMAssessmentResponse persistence.

    Consumed by AssessmentService to store and retrieve individual
    question answers grouped by anonymous assessment session.
    """

    async def create_response(
        self,
        session_id: uuid.UUID,
        question_id: str,
        answer_value: int,
        industry_vertical: str,
        answered_at: datetime,
    ) -> Any:
        """Persist a single question answer.

        Args:
            session_id: Assessment session UUID.
            question_id: Question identifier from the question bank.
            answer_value: Likert answer 1-5.
            industry_vertical: Respondent's industry vertical.
            answered_at: Timestamp when the answer was submitted.

        Returns:
            The persisted response record.
        """
        ...

    async def get_responses_by_session(
        self,
        session_id: uuid.UUID,
    ) -> list[Any]:
        """Retrieve all answers for an assessment session.

        Args:
            session_id: Assessment session UUID.

        Returns:
            List of response records ordered by answered_at.
        """
        ...

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
        ...


@runtime_checkable
class ILMResultRepository(Protocol):
    """Repository interface for LMAssessmentResult persistence.

    Consumed by AssessmentService to store and retrieve finalised
    assessment results including scores and CRM sync status.
    """

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
    ) -> Any:
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
            The persisted result record.
        """
        ...

    async def get_result_by_session(
        self,
        session_id: uuid.UUID,
    ) -> Any | None:
        """Retrieve the result for a given assessment session.

        Args:
            session_id: Assessment session UUID.

        Returns:
            Result record or None if not yet completed.
        """
        ...


@runtime_checkable
class ILMBenchmarkRepository(Protocol):
    """Repository interface for LMAssessmentBenchmark persistence.

    Consumed by AssessmentService to retrieve industry benchmark
    percentile data used for peer comparison in assessment results.
    """

    async def get_benchmarks_by_industry(
        self,
        industry_vertical: str,
    ) -> list[Any]:
        """Retrieve all benchmark records for an industry vertical.

        Args:
            industry_vertical: Industry vertical to query.

        Returns:
            List of benchmark records, one per dimension.
        """
        ...
