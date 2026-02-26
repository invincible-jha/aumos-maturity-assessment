"""Business logic services for the AumOS Maturity Assessment service.

All services depend on repository and adapter interfaces (not concrete
implementations) and receive dependencies via constructor injection.
No framework code (FastAPI, SQLAlchemy) belongs here.

Key invariants enforced by services:
- Scoring completeness: all five dimensions must have responses before scoring.
- Score immutability: completed assessments cannot be rescored.
- Benchmark alignment: roadmaps always reference the active benchmark period.
- Pilot success framing: every pilot must define ≥3 measurable success criteria.
"""

import uuid
from datetime import datetime, timezone
from typing import Any

from aumos_common.errors import ConflictError, ErrorCode, NotFoundError
from aumos_common.events import EventPublisher, Topics
from aumos_common.observability import get_logger

from aumos_maturity_assessment.core.interfaces import (
    IAssessmentRepository,
    IAssessmentResponseRepository,
    IBenchmarkRepository,
    IPilotRepository,
    IReportGeneratorAdapter,
    IReportRepository,
    IRoadmapGeneratorAdapter,
    IRoadmapRepository,
    IScoringEngine,
)
from aumos_maturity_assessment.core.models import (
    Assessment,
    AssessmentResponse,
    Benchmark,
    Pilot,
    Report,
    Roadmap,
)

logger = get_logger(__name__)

# Valid assessment status values
VALID_ASSESSMENT_STATUSES: frozenset[str] = frozenset(
    {"in_progress", "completed", "abandoned"}
)

# Valid industry verticals
VALID_INDUSTRIES: frozenset[str] = frozenset(
    {
        "financial_services",
        "healthcare",
        "manufacturing",
        "retail",
        "technology",
        "government",
        "other",
    }
)

# Valid organization sizes
VALID_ORG_SIZES: frozenset[str] = frozenset(
    {"startup", "smb", "mid_market", "enterprise", "large_enterprise"}
)

# Valid assessment dimensions
VALID_DIMENSIONS: frozenset[str] = frozenset(
    {"data", "process", "people", "technology", "governance"}
)

# Valid pilot statuses
VALID_PILOT_STATUSES: frozenset[str] = frozenset(
    {"designed", "approved", "running", "completed", "failed", "cancelled"}
)

# Minimum success criteria for a pilot (to address 88% failure rate)
MIN_PILOT_SUCCESS_CRITERIA: int = 3


class AssessmentService:
    """Orchestrate creation, response collection, and scoring of maturity assessments.

    Coordinates between repositories and the scoring engine to provide a
    single entry point for all assessment lifecycle operations.
    """

    def __init__(
        self,
        assessment_repo: IAssessmentRepository,
        response_repo: IAssessmentResponseRepository,
        scoring_engine: IScoringEngine,
        event_publisher: EventPublisher,
    ) -> None:
        """Initialise with injected dependencies.

        Args:
            assessment_repo: Assessment persistence.
            response_repo: AssessmentResponse persistence.
            scoring_engine: Maturity scoring computation engine.
            event_publisher: Kafka event publisher.
        """
        self._assessments = assessment_repo
        self._responses = response_repo
        self._scoring = scoring_engine
        self._publisher = event_publisher

    async def create_assessment(
        self,
        tenant_id: uuid.UUID,
        organization_name: str,
        industry: str,
        organization_size: str,
        dimension_weights: dict[str, float] | None = None,
        assessment_metadata: dict[str, Any] | None = None,
        initiated_by: uuid.UUID | None = None,
    ) -> Assessment:
        """Create a new maturity assessment.

        Args:
            tenant_id: Owning tenant UUID.
            organization_name: Name of the organization being assessed.
            industry: Industry vertical (must be one of VALID_INDUSTRIES).
            organization_size: Organization size segment.
            dimension_weights: Optional custom scoring weights per dimension.
            assessment_metadata: Additional context (revenue_range, ai_budget, etc.).
            initiated_by: Optional user UUID who initiated this assessment.

        Returns:
            Newly created Assessment in in_progress status.

        Raises:
            ConflictError: If industry or organization_size are invalid.
        """
        if industry not in VALID_INDUSTRIES:
            raise ConflictError(
                message=f"Invalid industry '{industry}'. Must be one of: {VALID_INDUSTRIES}",
                error_code=ErrorCode.INVALID_OPERATION,
            )

        if organization_size not in VALID_ORG_SIZES:
            raise ConflictError(
                message=f"Invalid organization_size '{organization_size}'. Must be one of: {VALID_ORG_SIZES}",
                error_code=ErrorCode.INVALID_OPERATION,
            )

        # Default balanced weights if not provided
        weights = dimension_weights or {
            "data": 0.25,
            "process": 0.20,
            "people": 0.20,
            "technology": 0.20,
            "governance": 0.15,
        }

        # Validate weights sum to 1.0
        weight_sum = sum(weights.values())
        if abs(weight_sum - 1.0) > 0.001:
            raise ConflictError(
                message=f"Dimension weights must sum to 1.0, got {weight_sum:.3f}.",
                error_code=ErrorCode.INVALID_OPERATION,
            )

        assessment = await self._assessments.create(
            tenant_id=tenant_id,
            organization_name=organization_name,
            industry=industry,
            organization_size=organization_size,
            dimension_weights=weights,
            assessment_metadata=assessment_metadata or {},
            initiated_by=initiated_by,
        )

        logger.info(
            "Maturity assessment created",
            tenant_id=str(tenant_id),
            assessment_id=str(assessment.id),
            organization_name=organization_name,
            industry=industry,
            organization_size=organization_size,
        )

        await self._publisher.publish(
            Topics.MATURITY_ASSESSMENT,
            {
                "event_type": "maturity.assessment.created",
                "tenant_id": str(tenant_id),
                "assessment_id": str(assessment.id),
                "organization_name": organization_name,
                "industry": industry,
                "organization_size": organization_size,
            },
        )

        return assessment

    async def get_assessment(
        self, assessment_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> Assessment:
        """Retrieve an assessment by ID.

        Args:
            assessment_id: Assessment UUID.
            tenant_id: Requesting tenant for RLS enforcement.

        Returns:
            Assessment with responses.

        Raises:
            NotFoundError: If assessment not found.
        """
        assessment = await self._assessments.get_by_id(assessment_id, tenant_id)
        if assessment is None:
            raise NotFoundError(
                message=f"Assessment {assessment_id} not found.",
                error_code=ErrorCode.NOT_FOUND,
            )
        return assessment

    async def list_assessments(
        self,
        tenant_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
        industry: str | None = None,
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
        return await self._assessments.list_by_tenant(
            tenant_id=tenant_id,
            page=page,
            page_size=page_size,
            status=status,
            industry=industry,
        )

    async def submit_responses(
        self,
        assessment_id: uuid.UUID,
        tenant_id: uuid.UUID,
        responses: list[dict[str, Any]],
    ) -> list[AssessmentResponse]:
        """Submit diagnostic question responses for an assessment.

        Args:
            assessment_id: Target assessment UUID.
            tenant_id: Owning tenant UUID.
            responses: List of response dicts with question_id, dimension,
                       response_value, numeric_score, weight, and optional metadata.

        Returns:
            List of created AssessmentResponse records.

        Raises:
            NotFoundError: If assessment not found.
            ConflictError: If assessment is not in_progress or a dimension is invalid.
        """
        assessment = await self.get_assessment(assessment_id, tenant_id)
        if assessment.status != "in_progress":
            raise ConflictError(
                message=f"Cannot submit responses — assessment {assessment_id} is {assessment.status}.",
                error_code=ErrorCode.INVALID_OPERATION,
            )

        # Validate all dimensions
        for resp in responses:
            dim = resp.get("dimension", "")
            if dim not in VALID_DIMENSIONS:
                raise ConflictError(
                    message=f"Invalid dimension '{dim}'. Must be one of: {VALID_DIMENSIONS}",
                    error_code=ErrorCode.INVALID_OPERATION,
                )

        created = await self._responses.create_bulk(
            tenant_id=tenant_id,
            assessment_id=assessment_id,
            responses=responses,
        )

        logger.info(
            "Assessment responses submitted",
            assessment_id=str(assessment_id),
            tenant_id=str(tenant_id),
            response_count=len(created),
        )

        return created

    async def score_assessment(
        self,
        assessment_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> Assessment:
        """Compute and persist multi-dimensional maturity scores.

        Requires responses covering all five dimensions. Marks the
        assessment as completed upon successful scoring.

        Args:
            assessment_id: Assessment UUID to score.
            tenant_id: Owning tenant UUID.

        Returns:
            Assessment updated with computed scores and completed status.

        Raises:
            NotFoundError: If assessment not found.
            ConflictError: If assessment is not in_progress or missing dimension coverage.
        """
        assessment = await self.get_assessment(assessment_id, tenant_id)
        if assessment.status != "in_progress":
            raise ConflictError(
                message=f"Cannot score assessment — status is {assessment.status}.",
                error_code=ErrorCode.INVALID_OPERATION,
            )

        all_responses = await self._responses.list_by_assessment(
            assessment_id=assessment_id,
            dimension=None,
        )

        if not all_responses:
            raise ConflictError(
                message="Cannot score assessment with no responses.",
                error_code=ErrorCode.INVALID_OPERATION,
            )

        # Validate all five dimensions have coverage
        covered_dimensions = {r.dimension for r in all_responses}
        missing = VALID_DIMENSIONS - covered_dimensions
        if missing:
            raise ConflictError(
                message=(
                    f"Cannot score assessment — missing responses for dimensions: {missing}. "
                    "All five dimensions (data, process, people, technology, governance) are required."
                ),
                error_code=ErrorCode.INVALID_OPERATION,
            )

        response_dicts = [
            {
                "dimension": r.dimension,
                "numeric_score": r.numeric_score,
                "weight": r.weight,
            }
            for r in all_responses
        ]

        scores = await self._scoring.compute_scores(
            responses=response_dicts,
            dimension_weights=assessment.dimension_weights,
        )

        now = datetime.now(tz=timezone.utc)
        updated = await self._assessments.update_scores(
            assessment_id=assessment_id,
            overall_score=scores["overall_score"],
            maturity_level=scores["maturity_level"],
            data_score=scores["data_score"],
            process_score=scores["process_score"],
            people_score=scores["people_score"],
            technology_score=scores["technology_score"],
            governance_score=scores["governance_score"],
            completed_at=now,
        )

        logger.info(
            "Assessment scored and completed",
            assessment_id=str(assessment_id),
            tenant_id=str(tenant_id),
            overall_score=scores["overall_score"],
            maturity_level=scores["maturity_level"],
        )

        await self._publisher.publish(
            Topics.MATURITY_ASSESSMENT,
            {
                "event_type": "maturity.assessment.completed",
                "tenant_id": str(tenant_id),
                "assessment_id": str(assessment_id),
                "overall_score": scores["overall_score"],
                "maturity_level": scores["maturity_level"],
                "data_score": scores["data_score"],
                "process_score": scores["process_score"],
                "people_score": scores["people_score"],
                "technology_score": scores["technology_score"],
                "governance_score": scores["governance_score"],
            },
        )

        return updated

    async def get_detailed_scores(
        self,
        assessment_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Get detailed scoring breakdown for a completed assessment.

        Args:
            assessment_id: Assessment UUID.
            tenant_id: Requesting tenant.

        Returns:
            Dict with dimension scores, maturity level, and per-response details.

        Raises:
            NotFoundError: If assessment not found.
            ConflictError: If assessment not yet completed.
        """
        assessment = await self.get_assessment(assessment_id, tenant_id)
        if assessment.status != "completed":
            raise ConflictError(
                message=f"Assessment {assessment_id} is not yet completed (status: {assessment.status}).",
                error_code=ErrorCode.INVALID_OPERATION,
            )

        responses = await self._responses.list_by_assessment(
            assessment_id=assessment_id,
            dimension=None,
        )

        # Group responses by dimension
        by_dimension: dict[str, list[dict[str, Any]]] = {
            dim: [] for dim in VALID_DIMENSIONS
        }
        for resp in responses:
            by_dimension[resp.dimension].append(
                {
                    "question_id": resp.question_id,
                    "response_value": resp.response_value,
                    "numeric_score": resp.numeric_score,
                    "weight": resp.weight,
                }
            )

        return {
            "assessment_id": str(assessment_id),
            "organization_name": assessment.organization_name,
            "overall_score": assessment.overall_score,
            "maturity_level": assessment.maturity_level,
            "maturity_label": _maturity_level_label(assessment.maturity_level),
            "dimension_scores": {
                "data": {
                    "score": assessment.data_score,
                    "weight": assessment.dimension_weights.get("data"),
                    "responses": by_dimension["data"],
                },
                "process": {
                    "score": assessment.process_score,
                    "weight": assessment.dimension_weights.get("process"),
                    "responses": by_dimension["process"],
                },
                "people": {
                    "score": assessment.people_score,
                    "weight": assessment.dimension_weights.get("people"),
                    "responses": by_dimension["people"],
                },
                "technology": {
                    "score": assessment.technology_score,
                    "weight": assessment.dimension_weights.get("technology"),
                    "responses": by_dimension["technology"],
                },
                "governance": {
                    "score": assessment.governance_score,
                    "weight": assessment.dimension_weights.get("governance"),
                    "responses": by_dimension["governance"],
                },
            },
            "dimension_weights": assessment.dimension_weights,
            "completed_at": assessment.completed_at.isoformat() if assessment.completed_at else None,
        }


class BenchmarkService:
    """Manage industry benchmark data and enable peer comparison.

    Provides storage, retrieval, and comparison logic for industry
    maturity benchmarks segmented by vertical and organization size.
    """

    def __init__(
        self,
        benchmark_repo: IBenchmarkRepository,
        event_publisher: EventPublisher,
    ) -> None:
        """Initialise with injected dependencies.

        Args:
            benchmark_repo: Benchmark persistence.
            event_publisher: Kafka event publisher.
        """
        self._benchmarks = benchmark_repo
        self._publisher = event_publisher

    async def get_industry_benchmark(
        self,
        tenant_id: uuid.UUID,
        industry: str,
        organization_size: str = "enterprise",
    ) -> Benchmark:
        """Retrieve the active benchmark for an industry+size segment.

        Args:
            tenant_id: Requesting tenant.
            industry: Industry vertical.
            organization_size: Organization size segment.

        Returns:
            Active Benchmark record.

        Raises:
            NotFoundError: If no active benchmark exists for the segment.
        """
        benchmark = await self._benchmarks.get_active_benchmark(
            tenant_id=tenant_id,
            industry=industry,
            organization_size=organization_size,
        )
        if benchmark is None:
            raise NotFoundError(
                message=(
                    f"No active benchmark found for industry='{industry}', "
                    f"organization_size='{organization_size}'."
                ),
                error_code=ErrorCode.NOT_FOUND,
            )
        return benchmark

    async def compare_assessment(
        self,
        tenant_id: uuid.UUID,
        assessment: Assessment,
    ) -> dict[str, Any]:
        """Compare an assessment's scores against industry benchmarks.

        Args:
            tenant_id: Requesting tenant.
            assessment: Completed Assessment with dimension scores.

        Returns:
            Comparison dict with percentile rankings, gaps, and strengths.

        Raises:
            ConflictError: If assessment is not completed.
            NotFoundError: If no benchmark found for the industry+size.
        """
        if assessment.status != "completed":
            raise ConflictError(
                message=f"Assessment {assessment.id} is not completed.",
                error_code=ErrorCode.INVALID_OPERATION,
            )

        benchmark = await self.get_industry_benchmark(
            tenant_id=tenant_id,
            industry=assessment.industry,
            organization_size=assessment.organization_size,
        )

        overall_percentile = _compute_percentile(
            value=assessment.overall_score or 0.0,
            p25=benchmark.overall_p25,
            p50=benchmark.overall_p50,
            p75=benchmark.overall_p75,
            p90=benchmark.overall_p90,
        )

        dimension_comparisons: dict[str, Any] = {}
        for dim in ["data", "process", "people", "technology", "governance"]:
            assessment_score = getattr(assessment, f"{dim}_score") or 0.0
            benchmark_median = getattr(benchmark, f"{dim}_p50")
            dimension_comparisons[dim] = {
                "assessment_score": assessment_score,
                "benchmark_median": benchmark_median,
                "gap": round(assessment_score - benchmark_median, 2),
                "above_median": assessment_score >= benchmark_median,
            }

        # Identify top gaps (dimensions most below median)
        gaps = sorted(
            [
                {"dimension": dim, "gap": info["gap"]}
                for dim, info in dimension_comparisons.items()
                if not info["above_median"]
            ],
            key=lambda x: x["gap"],
        )

        # Identify strengths (dimensions above median)
        strengths = [
            {"dimension": dim, "gap": info["gap"]}
            for dim, info in dimension_comparisons.items()
            if info["above_median"]
        ]

        logger.info(
            "Assessment benchmark comparison computed",
            assessment_id=str(assessment.id),
            industry=assessment.industry,
            overall_percentile=overall_percentile,
            gap_count=len(gaps),
        )

        return {
            "assessment_id": str(assessment.id),
            "benchmark_period": benchmark.benchmark_period,
            "industry": assessment.industry,
            "organization_size": assessment.organization_size,
            "sample_size": benchmark.sample_size,
            "overall_score": assessment.overall_score,
            "overall_percentile": overall_percentile,
            "benchmark_median": benchmark.overall_p50,
            "dimension_comparisons": dimension_comparisons,
            "top_gaps": gaps[:3],
            "strengths": strengths,
            "industry_top_strengths": benchmark.top_strengths,
            "industry_top_gaps": benchmark.top_gaps,
        }

    async def list_industry_benchmarks(
        self,
        tenant_id: uuid.UUID,
        industry: str,
    ) -> list[Benchmark]:
        """List all benchmarks for an industry (all size segments).

        Args:
            tenant_id: Requesting tenant.
            industry: Industry vertical.

        Returns:
            List of Benchmark records for the industry.
        """
        return await self._benchmarks.list_by_industry(tenant_id=tenant_id, industry=industry)

    async def upsert_benchmark(
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
        """Create or update benchmark data for an industry+size+period segment.

        Args:
            tenant_id: Owning tenant UUID.
            industry: Industry vertical.
            organization_size: Organization size segment.
            benchmark_period: Period identifier (e.g., 2024-Q4).
            sample_size: Number of contributing organizations.
            overall_p25: 25th percentile overall score.
            overall_p50: Median overall score.
            overall_p75: 75th percentile overall score.
            overall_p90: 90th percentile overall score.
            data_p50: Median data dimension score.
            process_p50: Median process dimension score.
            people_p50: Median people dimension score.
            technology_p50: Median technology dimension score.
            governance_p50: Median governance dimension score.
            dimension_breakdowns: Full percentile distribution per dimension.
            top_strengths: Top industry strengths.
            top_gaps: Top industry gaps.

        Returns:
            Created Benchmark record.
        """
        benchmark = await self._benchmarks.create(
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
        )

        logger.info(
            "Industry benchmark upserted",
            tenant_id=str(tenant_id),
            industry=industry,
            organization_size=organization_size,
            benchmark_period=benchmark_period,
            sample_size=sample_size,
        )

        return benchmark


class RoadmapService:
    """Auto-generate prioritized AI adoption roadmaps from assessment results.

    Uses a roadmap generator adapter to produce initiative recommendations
    organized by time horizon and expected impact.
    """

    def __init__(
        self,
        roadmap_repo: IRoadmapRepository,
        assessment_repo: IAssessmentRepository,
        benchmark_repo: IBenchmarkRepository,
        roadmap_generator: IRoadmapGeneratorAdapter,
        event_publisher: EventPublisher,
        default_horizon_months: int = 18,
    ) -> None:
        """Initialise with injected dependencies.

        Args:
            roadmap_repo: Roadmap persistence.
            assessment_repo: Assessment persistence for score retrieval.
            benchmark_repo: Benchmark persistence for industry context.
            roadmap_generator: LLM-backed roadmap generation adapter.
            event_publisher: Kafka event publisher.
            default_horizon_months: Default planning horizon in months.
        """
        self._roadmaps = roadmap_repo
        self._assessments = assessment_repo
        self._benchmarks = benchmark_repo
        self._generator = roadmap_generator
        self._publisher = event_publisher
        self._default_horizon_months = default_horizon_months

    async def generate_roadmap(
        self,
        assessment_id: uuid.UUID,
        tenant_id: uuid.UUID,
        horizon_months: int | None = None,
        target_maturity_level: int | None = None,
    ) -> Roadmap:
        """Auto-generate a roadmap from a completed assessment.

        Args:
            assessment_id: Source assessment UUID.
            tenant_id: Owning tenant UUID.
            horizon_months: Planning horizon (defaults to service setting).
            target_maturity_level: Target level 1-5 (defaults to current+1).

        Returns:
            Newly created Roadmap with generated initiatives.

        Raises:
            NotFoundError: If assessment not found.
            ConflictError: If assessment is not completed.
        """
        assessment = await self._assessments.get_by_id(assessment_id, tenant_id)
        if assessment is None:
            raise NotFoundError(
                message=f"Assessment {assessment_id} not found.",
                error_code=ErrorCode.NOT_FOUND,
            )
        if assessment.status != "completed":
            raise ConflictError(
                message=f"Cannot generate roadmap — assessment {assessment_id} is not completed.",
                error_code=ErrorCode.INVALID_OPERATION,
            )

        effective_horizon = horizon_months or self._default_horizon_months
        effective_target = target_maturity_level or min((assessment.maturity_level or 1) + 1, 5)

        # Load benchmark for context (optional — roadmap can still generate without it)
        benchmark = await self._benchmarks.get_active_benchmark(
            tenant_id=tenant_id,
            industry=assessment.industry,
            organization_size=assessment.organization_size,
        )

        generated = await self._generator.generate(
            assessment=assessment,
            benchmark=benchmark,
            horizon_months=effective_horizon,
            target_maturity_level=effective_target,
        )

        roadmap = await self._roadmaps.create(
            tenant_id=tenant_id,
            assessment_id=assessment_id,
            title=f"AI Maturity Advancement Plan — {assessment.organization_name}",
            horizon_months=effective_horizon,
            target_maturity_level=effective_target,
            initiatives=generated.get("initiatives", []),
            quick_wins=generated.get("quick_wins", []),
            estimated_roi_multiplier=generated.get("estimated_roi_multiplier"),
            roadmap_metadata={
                "generator_version": "1.0",
                "assessment_id": str(assessment_id),
                "benchmark_period": benchmark.benchmark_period if benchmark else None,
                "generated_at": datetime.now(tz=timezone.utc).isoformat(),
            },
        )

        logger.info(
            "Roadmap generated",
            tenant_id=str(tenant_id),
            roadmap_id=str(roadmap.id),
            assessment_id=str(assessment_id),
            initiative_count=len(generated.get("initiatives", [])),
            quick_win_count=len(generated.get("quick_wins", [])),
        )

        await self._publisher.publish(
            Topics.MATURITY_ROADMAP,
            {
                "event_type": "maturity.roadmap.generated",
                "tenant_id": str(tenant_id),
                "roadmap_id": str(roadmap.id),
                "assessment_id": str(assessment_id),
                "target_maturity_level": effective_target,
                "initiative_count": len(generated.get("initiatives", [])),
            },
        )

        return roadmap

    async def get_roadmap(
        self, roadmap_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> Roadmap:
        """Retrieve a roadmap by ID.

        Args:
            roadmap_id: Roadmap UUID.
            tenant_id: Requesting tenant.

        Returns:
            Roadmap record.

        Raises:
            NotFoundError: If roadmap not found.
        """
        roadmap = await self._roadmaps.get_by_id(roadmap_id, tenant_id)
        if roadmap is None:
            raise NotFoundError(
                message=f"Roadmap {roadmap_id} not found.",
                error_code=ErrorCode.NOT_FOUND,
            )
        return roadmap

    async def publish_roadmap(
        self,
        roadmap_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> Roadmap:
        """Publish a draft roadmap to the client.

        Args:
            roadmap_id: Roadmap UUID.
            tenant_id: Owning tenant.

        Returns:
            Updated Roadmap in published status.

        Raises:
            NotFoundError: If roadmap not found.
            ConflictError: If roadmap is not in draft status.
        """
        roadmap = await self.get_roadmap(roadmap_id, tenant_id)
        if roadmap.status != "draft":
            raise ConflictError(
                message=f"Cannot publish roadmap {roadmap_id} — status is {roadmap.status}.",
                error_code=ErrorCode.INVALID_OPERATION,
            )

        now = datetime.now(tz=timezone.utc)
        updated = await self._roadmaps.update_status(
            roadmap_id=roadmap_id,
            status="published",
            published_at=now,
        )

        logger.info(
            "Roadmap published",
            roadmap_id=str(roadmap_id),
            tenant_id=str(tenant_id),
        )

        return updated


class PilotService:
    """Design and track AI pilot initiatives to address the 88% failure rate.

    Enforces structured pilot design with measurable success criteria,
    pre-identified failure modes, and stakeholder mapping.
    """

    def __init__(
        self,
        pilot_repo: IPilotRepository,
        roadmap_repo: IRoadmapRepository,
        event_publisher: EventPublisher,
    ) -> None:
        """Initialise with injected dependencies.

        Args:
            pilot_repo: Pilot persistence.
            roadmap_repo: Roadmap persistence for parent validation.
            event_publisher: Kafka event publisher.
        """
        self._pilots = pilot_repo
        self._roadmaps = roadmap_repo
        self._publisher = event_publisher

    async def design_pilot(
        self,
        roadmap_id: uuid.UUID,
        tenant_id: uuid.UUID,
        title: str,
        dimension: str,
        success_criteria: list[dict[str, Any]],
        failure_modes: list[dict[str, Any]],
        stakeholder_map: dict[str, Any],
        resource_requirements: dict[str, Any],
        duration_weeks: int = 8,
    ) -> Pilot:
        """Design a structured AI pilot initiative.

        Enforces minimum 3 success criteria to address the 88% failure rate
        pattern of pilots without measurable objectives.

        Args:
            roadmap_id: Parent roadmap UUID.
            tenant_id: Owning tenant UUID.
            title: Pilot title.
            dimension: Primary dimension addressed.
            success_criteria: Measurable criteria list (minimum 3 required).
            failure_modes: Pre-identified failure modes with mitigations.
            stakeholder_map: Roles mapped to named stakeholders.
            resource_requirements: Compute, data, people, and budget resources.
            duration_weeks: Planned pilot duration in weeks.

        Returns:
            Newly designed Pilot.

        Raises:
            NotFoundError: If roadmap not found.
            ConflictError: If dimension invalid or insufficient success criteria.
        """
        roadmap = await self._roadmaps.get_by_id(roadmap_id, tenant_id)
        if roadmap is None:
            raise NotFoundError(
                message=f"Roadmap {roadmap_id} not found.",
                error_code=ErrorCode.NOT_FOUND,
            )

        if dimension not in VALID_DIMENSIONS:
            raise ConflictError(
                message=f"Invalid dimension '{dimension}'. Must be one of: {VALID_DIMENSIONS}",
                error_code=ErrorCode.INVALID_OPERATION,
            )

        if len(success_criteria) < MIN_PILOT_SUCCESS_CRITERIA:
            raise ConflictError(
                message=(
                    f"At least {MIN_PILOT_SUCCESS_CRITERIA} success criteria required "
                    f"to address the 88% pilot failure rate. Got {len(success_criteria)}."
                ),
                error_code=ErrorCode.INVALID_OPERATION,
            )

        pilot = await self._pilots.create(
            tenant_id=tenant_id,
            roadmap_id=roadmap_id,
            title=title,
            dimension=dimension,
            duration_weeks=duration_weeks,
            success_criteria=success_criteria,
            failure_modes=failure_modes,
            stakeholder_map=stakeholder_map,
            resource_requirements=resource_requirements,
        )

        logger.info(
            "Pilot designed",
            tenant_id=str(tenant_id),
            pilot_id=str(pilot.id),
            roadmap_id=str(roadmap_id),
            dimension=dimension,
            success_criteria_count=len(success_criteria),
        )

        await self._publisher.publish(
            Topics.MATURITY_PILOT,
            {
                "event_type": "maturity.pilot.designed",
                "tenant_id": str(tenant_id),
                "pilot_id": str(pilot.id),
                "roadmap_id": str(roadmap_id),
                "dimension": dimension,
            },
        )

        return pilot

    async def get_pilot(
        self, pilot_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> Pilot:
        """Retrieve a pilot by ID.

        Args:
            pilot_id: Pilot UUID.
            tenant_id: Requesting tenant.

        Returns:
            Pilot record.

        Raises:
            NotFoundError: If pilot not found.
        """
        pilot = await self._pilots.get_by_id(pilot_id, tenant_id)
        if pilot is None:
            raise NotFoundError(
                message=f"Pilot {pilot_id} not found.",
                error_code=ErrorCode.NOT_FOUND,
            )
        return pilot

    async def update_pilot_status(
        self,
        pilot_id: uuid.UUID,
        tenant_id: uuid.UUID,
        new_status: str,
    ) -> Pilot:
        """Transition a pilot to a new lifecycle status.

        Args:
            pilot_id: Pilot UUID.
            tenant_id: Owning tenant.
            new_status: Target status (must be valid).

        Returns:
            Updated Pilot.

        Raises:
            NotFoundError: If pilot not found.
            ConflictError: If status transition is invalid.
        """
        if new_status not in VALID_PILOT_STATUSES:
            raise ConflictError(
                message=f"Invalid status '{new_status}'. Must be one of: {VALID_PILOT_STATUSES}",
                error_code=ErrorCode.INVALID_OPERATION,
            )

        pilot = await self.get_pilot(pilot_id, tenant_id)

        now = datetime.now(tz=timezone.utc)
        started_at: datetime | None = None
        completed_at: datetime | None = None

        if new_status == "running" and pilot.status == "approved":
            started_at = now
        elif new_status in {"completed", "failed", "cancelled"}:
            completed_at = now

        updated = await self._pilots.update_status(
            pilot_id=pilot_id,
            status=new_status,
            started_at=started_at,
            completed_at=completed_at,
        )

        await self._publisher.publish(
            Topics.MATURITY_PILOT,
            {
                "event_type": "maturity.pilot.status_changed",
                "tenant_id": str(tenant_id),
                "pilot_id": str(pilot_id),
                "old_status": pilot.status,
                "new_status": new_status,
            },
        )

        logger.info(
            "Pilot status updated",
            pilot_id=str(pilot_id),
            tenant_id=str(tenant_id),
            old_status=pilot.status,
            new_status=new_status,
        )

        return updated

    async def log_execution_update(
        self,
        pilot_id: uuid.UUID,
        tenant_id: uuid.UUID,
        week: int,
        status: str,
        metrics: dict[str, Any],
        blockers: list[str],
        notes: str,
    ) -> Pilot:
        """Append a weekly execution update to a running pilot.

        Args:
            pilot_id: Pilot UUID.
            tenant_id: Owning tenant.
            week: Week number (1-based).
            status: on_track | at_risk | blocked.
            metrics: Current measurements against success criteria.
            blockers: List of active blocker descriptions.
            notes: Narrative update.

        Returns:
            Updated Pilot with new log entry appended.

        Raises:
            NotFoundError: If pilot not found.
            ConflictError: If pilot is not running.
        """
        pilot = await self.get_pilot(pilot_id, tenant_id)
        if pilot.status != "running":
            raise ConflictError(
                message=f"Cannot log execution update — pilot {pilot_id} is not running.",
                error_code=ErrorCode.INVALID_OPERATION,
            )

        log_entry = {
            "week": week,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "status": status,
            "metrics": metrics,
            "blockers": blockers,
            "notes": notes,
        }

        return await self._pilots.append_execution_log(
            pilot_id=pilot_id,
            log_entry=log_entry,
        )


class ReportService:
    """Generate executive reports from completed assessment data.

    Compiles assessment scores, benchmark comparisons, and roadmap
    recommendations into polished executive deliverables.
    """

    def __init__(
        self,
        report_repo: IReportRepository,
        assessment_repo: IAssessmentRepository,
        benchmark_repo: IBenchmarkRepository,
        roadmap_repo: IRoadmapRepository,
        report_generator: IReportGeneratorAdapter,
        event_publisher: EventPublisher,
        include_benchmarks: bool = True,
    ) -> None:
        """Initialise with injected dependencies.

        Args:
            report_repo: Report persistence.
            assessment_repo: Assessment persistence.
            benchmark_repo: Benchmark persistence.
            roadmap_repo: Roadmap persistence.
            report_generator: Report content generation adapter.
            event_publisher: Kafka event publisher.
            include_benchmarks: Default benchmark inclusion flag.
        """
        self._reports = report_repo
        self._assessments = assessment_repo
        self._benchmarks = benchmark_repo
        self._roadmaps = roadmap_repo
        self._generator = report_generator
        self._publisher = event_publisher
        self._include_benchmarks = include_benchmarks

    async def generate_report(
        self,
        assessment_id: uuid.UUID,
        tenant_id: uuid.UUID,
        report_type: str = "executive_summary",
        format: str = "pdf",
        roadmap_id: uuid.UUID | None = None,
        include_benchmarks: bool | None = None,
    ) -> Report:
        """Generate an executive report from a completed assessment.

        Args:
            assessment_id: Source assessment UUID.
            tenant_id: Owning tenant UUID.
            report_type: Type of report to generate.
            format: Output format (pdf, pptx, docx, json).
            roadmap_id: Optional roadmap to include.
            include_benchmarks: Override default benchmark inclusion.

        Returns:
            Newly created Report (initially in generating status, updated to ready).

        Raises:
            NotFoundError: If assessment not found.
            ConflictError: If assessment is not completed.
        """
        assessment = await self._assessments.get_by_id(assessment_id, tenant_id)
        if assessment is None:
            raise NotFoundError(
                message=f"Assessment {assessment_id} not found.",
                error_code=ErrorCode.NOT_FOUND,
            )
        if assessment.status != "completed":
            raise ConflictError(
                message=f"Cannot generate report — assessment {assessment_id} is not completed.",
                error_code=ErrorCode.INVALID_OPERATION,
            )

        # Create report record in generating status
        report = await self._reports.create(
            tenant_id=tenant_id,
            assessment_id=assessment_id,
            title=f"AI Maturity Assessment Report — {assessment.organization_name}",
            report_type=report_type,
            format=format,
            report_metadata={
                "roadmap_id": str(roadmap_id) if roadmap_id else None,
                "include_benchmarks": include_benchmarks if include_benchmarks is not None else self._include_benchmarks,
                "template_version": "1.0",
            },
        )

        # Load optional context
        benchmark = await self._benchmarks.get_active_benchmark(
            tenant_id=tenant_id,
            industry=assessment.industry,
            organization_size=assessment.organization_size,
        )

        roadmap = None
        if roadmap_id:
            roadmap = await self._roadmaps.get_by_id(roadmap_id, tenant_id)

        try:
            effective_include_benchmarks = (
                include_benchmarks if include_benchmarks is not None else self._include_benchmarks
            )
            generated = await self._generator.generate(
                assessment=assessment,
                benchmark=benchmark,
                roadmap=roadmap,
                report_type=report_type,
                format=format,
                include_benchmarks=effective_include_benchmarks,
            )

            now = datetime.now(tz=timezone.utc)
            updated = await self._reports.mark_ready(
                report_id=report.id,
                content=generated.get("content", {}),
                artifact_url=generated.get("artifact_url"),
                generated_at=now,
            )

            logger.info(
                "Report generated",
                tenant_id=str(tenant_id),
                report_id=str(report.id),
                assessment_id=str(assessment_id),
                report_type=report_type,
                format=format,
            )

            await self._publisher.publish(
                Topics.MATURITY_REPORT,
                {
                    "event_type": "maturity.report.generated",
                    "tenant_id": str(tenant_id),
                    "report_id": str(report.id),
                    "assessment_id": str(assessment_id),
                    "report_type": report_type,
                    "format": format,
                },
            )

            return updated

        except Exception as exc:
            await self._reports.mark_failed(
                report_id=report.id,
                error_message=str(exc),
            )
            logger.error(
                "Report generation failed",
                report_id=str(report.id),
                assessment_id=str(assessment_id),
                error=str(exc),
            )
            raise

    async def get_report(
        self, report_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> Report:
        """Retrieve a report by ID.

        Args:
            report_id: Report UUID.
            tenant_id: Requesting tenant.

        Returns:
            Report record.

        Raises:
            NotFoundError: If report not found.
        """
        report = await self._reports.get_by_id(report_id, tenant_id)
        if report is None:
            raise NotFoundError(
                message=f"Report {report_id} not found.",
                error_code=ErrorCode.NOT_FOUND,
            )
        return report


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _maturity_level_label(level: int | None) -> str:
    """Map a maturity level integer to its descriptive label.

    Args:
        level: Maturity level 1-5 or None.

    Returns:
        Descriptive label string.
    """
    labels = {
        1: "Initial",
        2: "Developing",
        3: "Defined",
        4: "Managed",
        5: "Optimizing",
    }
    return labels.get(level or 0, "Unknown")


def _compute_percentile(
    value: float,
    p25: float,
    p50: float,
    p75: float,
    p90: float,
) -> int:
    """Estimate approximate percentile from known benchmark breakpoints.

    Args:
        value: The score to rank.
        p25: 25th percentile breakpoint.
        p50: 50th percentile breakpoint.
        p75: 75th percentile breakpoint.
        p90: 90th percentile breakpoint.

    Returns:
        Estimated integer percentile (0-99).
    """
    if value >= p90:
        return 90
    if value >= p75:
        return 75
    if value >= p50:
        return 50
    if value >= p25:
        return 25
    return 10
