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


# ---------------------------------------------------------------------------
# Interfaces for domain-specific analytics adapters
# ---------------------------------------------------------------------------


@runtime_checkable
class IBenchmarkComparator(Protocol):
    """Interface for industry peer comparison and percentile ranking."""

    async def select_peer_group(
        self,
        industry: str,
        organization_size: str,
        available_benchmarks: list[Any],
    ) -> dict[str, Any]:
        """Select the most appropriate peer benchmark group for comparison.

        Args:
            industry: Organisation industry vertical.
            organization_size: Organisation size band (small | mid | enterprise).
            available_benchmarks: List of available benchmark records.

        Returns:
            Dict with selected_benchmark, peer_group_label, and sample_size.
        """
        ...

    async def compute_percentile_rankings(
        self,
        assessment_scores: dict[str, float],
        benchmark: Any,
    ) -> dict[str, Any]:
        """Compute percentile ranking for each dimension against the peer group.

        Args:
            assessment_scores: Dict of dimension name to score (0–100).
            benchmark: Benchmark record with p25/p50/p75/p90 quartile data.

        Returns:
            Dict with percentile_rankings (per dimension) and overall_percentile.
        """
        ...

    async def analyze_gap_vs_best_in_class(
        self,
        assessment_scores: dict[str, float],
        benchmark: Any,
    ) -> dict[str, Any]:
        """Compare assessment scores against best-in-class (p90) thresholds.

        Args:
            assessment_scores: Dict of dimension name to score (0–100).
            benchmark: Benchmark record with p90 quartile data per dimension.

        Returns:
            Dict with overall_gap, dimension_gaps, and gap_severity_labels.
        """
        ...

    async def score_improvement_priorities(
        self,
        gap_analysis: dict[str, Any],
        dimension_weights: dict[str, float] | None,
    ) -> dict[str, Any]:
        """Score improvement priorities based on gap magnitude and difficulty.

        Args:
            gap_analysis: Output of analyze_gap_vs_best_in_class.
            dimension_weights: Optional custom weights per dimension.

        Returns:
            Dict with prioritized_dimensions (ranked list) and quick_win_flags.
        """
        ...

    async def generate_comparison_visualization_data(
        self,
        assessment_scores: dict[str, float],
        benchmark: Any,
        percentile_rankings: dict[str, Any],
    ) -> dict[str, Any]:
        """Generate visualization-ready data for radar chart and bar charts.

        Args:
            assessment_scores: Dict of dimension name to score.
            benchmark: Benchmark record with median and quartile data.
            percentile_rankings: Output of compute_percentile_rankings.

        Returns:
            Dict with radar_chart_data, percentile_bar_data, and gap_waterfall_data.
        """
        ...


@runtime_checkable
class IRoadmapPlanner(Protocol):
    """Interface for advanced roadmap planning with timeline and Gantt export."""

    async def map_gaps_to_actions(
        self,
        gap_analysis: dict[str, Any],
        horizon_months: int,
    ) -> dict[str, Any]:
        """Map dimension gaps to specific actionable initiatives.

        Args:
            gap_analysis: Gap analysis output with dimension_gaps list.
            horizon_months: Planning horizon to constrain initiative selection.

        Returns:
            Dict with actions, total_actions_count, and dimensions_addressed.
        """
        ...

    async def sequence_by_priority(
        self,
        actions: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Sequence actions from quick wins through strategic initiatives.

        Args:
            actions: List of action dicts from map_gaps_to_actions.

        Returns:
            Dict with sequenced_actions, quick_wins, strategic_initiatives,
            and dependency_warnings.
        """
        ...

    async def estimate_effort_and_impact(
        self,
        actions: list[dict[str, Any]],
        team_capacity_hours_per_week: float,
        hourly_cost_usd: float,
    ) -> dict[str, Any]:
        """Compute effort and impact estimates for each action.

        Args:
            actions: List of sequenced action dicts.
            team_capacity_hours_per_week: Available team hours per week.
            hourly_cost_usd: Fully-loaded hourly cost in USD.

        Returns:
            Dict with enriched_actions, total_effort_weeks, total_cost_usd.
        """
        ...

    async def generate_timeline(
        self,
        sequenced_actions: list[dict[str, Any]],
        start_date: datetime | None,
        parallel_streams: int,
    ) -> dict[str, Any]:
        """Assign start/end dates to each action.

        Args:
            sequenced_actions: Priority-ordered actions.
            start_date: Roadmap kickoff date.
            parallel_streams: Number of work streams.

        Returns:
            Dict with timeline_entries, start_date, and projected_end_date.
        """
        ...

    async def define_milestones(
        self,
        timeline_entries: list[dict[str, Any]],
        horizon_months: int,
    ) -> dict[str, Any]:
        """Define milestone checkpoints at regular intervals.

        Args:
            timeline_entries: Timeline data from generate_timeline.
            horizon_months: Total roadmap horizon.

        Returns:
            Dict with milestones, phase_completions, and total_milestone_count.
        """
        ...

    async def identify_dependencies(
        self,
        actions: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Identify and document dependencies between actions.

        Args:
            actions: List of action dicts with id, dimension, and phase.

        Returns:
            Dict with dependencies, dependency_graph, and orphaned_actions.
        """
        ...

    async def export_roadmap_json(
        self,
        actions: list[dict[str, Any]],
        timeline: dict[str, Any],
        milestones: dict[str, Any],
        dependencies: dict[str, Any],
        metadata: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Export the complete roadmap as a structured JSON document.

        Args:
            actions: Sequenced and enriched action list.
            timeline: Timeline data from generate_timeline.
            milestones: Milestone data from define_milestones.
            dependencies: Dependency data from identify_dependencies.
            metadata: Optional metadata dict.

        Returns:
            Complete roadmap JSON document dict.
        """
        ...

    async def export_gantt_data(
        self,
        timeline_entries: list[dict[str, Any]],
        milestones: dict[str, Any],
        start_date: str,
    ) -> dict[str, Any]:
        """Export roadmap data in Gantt chart format.

        Args:
            timeline_entries: Timeline data from generate_timeline.
            milestones: Milestone data from define_milestones.
            start_date: Roadmap start date string (YYYY-MM-DD).

        Returns:
            Dict with tasks, milestones_gantt, and chart_config.
        """
        ...


# ---------------------------------------------------------------------------
# GAP-286: Configurable dimension system interfaces
# ---------------------------------------------------------------------------


@runtime_checkable
class IDimensionConfigRepository(Protocol):
    """Repository interface for MatDimensionConfig persistence."""

    async def get_by_id(
        self,
        dimension_id: str,
    ) -> Any | None:
        """Retrieve a dimension config by ID."""
        ...

    async def list_active(self) -> list[Any]:
        """List all active dimension configs ordered by default_weight descending."""
        ...

    async def create(
        self,
        id: str,
        display_name: str,
        description: str,
        default_weight: float,
        question_bank: list[dict[str, Any]],
        introduced_in_version: str,
        framework_alignment: str | None,
    ) -> Any:
        """Create a new dimension config."""
        ...

    async def update_active(
        self,
        dimension_id: str,
        is_active: bool,
    ) -> Any:
        """Activate or deactivate a dimension."""
        ...


# ---------------------------------------------------------------------------
# GAP-287: Benchmark data enrichment interfaces
# ---------------------------------------------------------------------------


@runtime_checkable
class IBenchmarkContributionConsentRepository(Protocol):
    """Repository interface for MatBenchmarkContributionConsent persistence."""

    async def get_by_tenant(
        self,
        tenant_id: uuid.UUID,
    ) -> Any | None:
        """Retrieve consent record for a tenant."""
        ...

    async def upsert(
        self,
        tenant_id: uuid.UUID,
        consented: bool,
        consent_version: str,
    ) -> Any:
        """Create or update consent for a tenant."""
        ...

    async def count_consenting_tenants(self) -> int:
        """Count the number of tenants who have opted in to benchmark contribution."""
        ...


@runtime_checkable
class IBenchmarkEnrichmentAdapter(Protocol):
    """Interface for the quarterly benchmark enrichment adapter."""

    async def run_quarterly_enrichment(
        self,
        industry: str,
        organization_size: str,
        benchmark_period: str,
        tenant_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Aggregate opt-in tenant scores into updated benchmark data.

        Args:
            industry: Industry vertical to enrich.
            organization_size: Organization size segment.
            benchmark_period: Target period string (e.g. '2025-Q1').
            tenant_id: Platform admin tenant UUID for record creation.

        Returns:
            Dict with updated benchmark stats and contributing_tenant_count.
        """
        ...


# ---------------------------------------------------------------------------
# GAP-291: Assessment progress over time interfaces
# ---------------------------------------------------------------------------


@runtime_checkable
class IMaturityProgressRepository(Protocol):
    """Repository interface for querying historical assessment scores."""

    async def list_completed_by_tenant(
        self,
        tenant_id: uuid.UUID,
        limit: int,
    ) -> list[Any]:
        """List completed assessments ordered by completed_at ascending.

        Args:
            tenant_id: Tenant UUID.
            limit: Maximum number of assessments to return.

        Returns:
            List of completed Assessment records.
        """
        ...
