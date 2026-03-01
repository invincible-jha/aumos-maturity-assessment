"""Business logic services for the AumOS Maturity Assessment service.

All services depend on repository and adapter interfaces (not concrete
implementations) and receive dependencies via constructor injection.
No framework code (FastAPI, SQLAlchemy) belongs here.

Key invariants enforced by services:
- Scoring completeness: all five dimensions must have responses before scoring.
- Score immutability: completed assessments cannot be rescored.
- Benchmark alignment: roadmaps always reference the active benchmark period.
- Pilot success framing: every pilot must define ≥3 measurable success criteria.
- Dimension configurability: dimension set is persisted per assessment (GAP-286).
- Benchmark enrichment: minimum 30 consenting tenants before updating (GAP-287).
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
    IBenchmarkComparator,
    IBenchmarkContributionConsentRepository,
    IBenchmarkEnrichmentAdapter,
    IBenchmarkRepository,
    IDimensionConfigRepository,
    IMaturityProgressRepository,
    IPilotRepository,
    IReportGeneratorAdapter,
    IReportRepository,
    IRoadmapGeneratorAdapter,
    IRoadmapPlanner,
    IRoadmapRepository,
    IScoringEngine,
)
from aumos_maturity_assessment.core.models import (
    Assessment,
    AssessmentResponse,
    Benchmark,
    MatBenchmarkContributionConsent,
    MatDimensionConfig,
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


class BenchmarkComparisonService:
    """Provide peer benchmarking, percentile rankings, and gap analysis.

    Wraps IBenchmarkComparator to deliver structured comparison outputs
    suitable for executive reporting and roadmap prioritisation.
    """

    def __init__(
        self,
        benchmark_comparator: IBenchmarkComparator,
        benchmark_repo: IBenchmarkRepository,
        event_publisher: EventPublisher,
    ) -> None:
        """Initialise with injected dependencies.

        Args:
            benchmark_comparator: Peer comparison and percentile ranking adapter.
            benchmark_repo: Benchmark repository for retrieving industry data.
            event_publisher: Kafka event publisher.
        """
        self._comparator = benchmark_comparator
        self._benchmarks = benchmark_repo
        self._publisher = event_publisher

    async def run_peer_comparison(
        self,
        tenant_id: uuid.UUID,
        assessment: Any,
        industry: str,
        organization_size: str,
    ) -> dict[str, Any]:
        """Run a full peer comparison for a completed assessment.

        Retrieves the active industry benchmark, computes percentile rankings,
        gap analysis vs best-in-class, and improvement priority scores.

        Args:
            tenant_id: Requesting tenant UUID.
            assessment: Completed Assessment with dimension scores.
            industry: Organisation industry vertical.
            organization_size: Organisation size band.

        Returns:
            Dict with peer_group, percentile_rankings, gap_analysis,
            improvement_priorities, and visualization_data.

        Raises:
            NotFoundError: If no benchmark is available for the industry/size.
        """
        benchmark = await self._benchmarks.get_active_benchmark(
            tenant_id=tenant_id,
            industry=industry,
            organization_size=organization_size,
        )

        all_benchmarks = await self._benchmarks.list_by_industry(tenant_id, industry)

        peer_group = await self._comparator.select_peer_group(
            industry=industry,
            organization_size=organization_size,
            available_benchmarks=all_benchmarks,
        )

        if benchmark is None:
            if not all_benchmarks:
                raise NotFoundError(
                    message=f"No benchmark data available for industry '{industry}'.",
                    error_code=ErrorCode.NOT_FOUND,
                )
            benchmark = all_benchmarks[0]

        assessment_scores = {
            "data": assessment.data_score or 0.0,
            "process": assessment.process_score or 0.0,
            "people": assessment.people_score or 0.0,
            "technology": assessment.technology_score or 0.0,
            "governance": assessment.governance_score or 0.0,
        }

        percentile_rankings = await self._comparator.compute_percentile_rankings(
            assessment_scores=assessment_scores,
            benchmark=benchmark,
        )

        gap_analysis = await self._comparator.analyze_gap_vs_best_in_class(
            assessment_scores=assessment_scores,
            benchmark=benchmark,
        )

        improvement_priorities = await self._comparator.score_improvement_priorities(
            gap_analysis=gap_analysis,
            dimension_weights=None,
        )

        visualization_data = await self._comparator.generate_comparison_visualization_data(
            assessment_scores=assessment_scores,
            benchmark=benchmark,
            percentile_rankings=percentile_rankings,
        )

        result = {
            "peer_group": peer_group,
            "percentile_rankings": percentile_rankings,
            "gap_analysis": gap_analysis,
            "improvement_priorities": improvement_priorities,
            "visualization_data": visualization_data,
        }

        logger.info(
            "Peer benchmark comparison completed",
            tenant_id=str(tenant_id),
            assessment_id=str(assessment.id),
            industry=industry,
            organization_size=organization_size,
            overall_percentile=percentile_rankings.get("overall_percentile", 0),
        )

        await self._publisher.publish(
            Topics.MATURITY_ASSESSMENT,
            {
                "event_type": "maturity.benchmark_compared",
                "tenant_id": str(tenant_id),
                "assessment_id": str(assessment.id),
                "industry": industry,
                "overall_percentile": percentile_rankings.get("overall_percentile", 0),
            },
        )

        return result


class RoadmapPlanningService:
    """Generate detailed improvement roadmaps with timelines and Gantt exports.

    Orchestrates IRoadmapPlanner to produce comprehensive roadmap documents
    from gap analysis data, with timeline generation and dependency tracking.
    """

    def __init__(
        self,
        roadmap_planner: IRoadmapPlanner,
        event_publisher: EventPublisher,
    ) -> None:
        """Initialise with injected dependencies.

        Args:
            roadmap_planner: Advanced roadmap planning adapter.
            event_publisher: Kafka event publisher.
        """
        self._planner = roadmap_planner
        self._publisher = event_publisher

    async def generate_detailed_roadmap(
        self,
        tenant_id: uuid.UUID,
        assessment_id: uuid.UUID,
        gap_analysis: dict[str, Any],
        horizon_months: int = 12,
        parallel_streams: int = 2,
        team_capacity_hours_per_week: float = 40.0,
        hourly_cost_usd: float = 150.0,
        start_date: datetime | None = None,
    ) -> dict[str, Any]:
        """Generate a full detailed roadmap with timeline and Gantt export.

        Runs the complete planning pipeline: gap-to-action mapping, priority
        sequencing, effort/impact estimation, timeline generation, milestone
        definition, dependency identification, and dual format export.

        Args:
            tenant_id: Requesting tenant UUID.
            assessment_id: Source assessment UUID for event metadata.
            gap_analysis: Output from BenchmarkComparisonService.run_peer_comparison
                (contains gap_analysis key with dimension_gaps list).
            horizon_months: Planning horizon in months.
            parallel_streams: Number of work streams for timeline scheduling.
            team_capacity_hours_per_week: Available team hours per week.
            hourly_cost_usd: Fully-loaded hourly team cost in USD.
            start_date: Roadmap start date (defaults to now UTC).

        Returns:
            Dict with roadmap_json and gantt_data keys, plus summary metadata.
        """
        action_map = await self._planner.map_gaps_to_actions(
            gap_analysis=gap_analysis,
            horizon_months=horizon_months,
        )

        sequenced = await self._planner.sequence_by_priority(
            actions=action_map["actions"],
        )

        enriched = await self._planner.estimate_effort_and_impact(
            actions=sequenced["sequenced_actions"],
            team_capacity_hours_per_week=team_capacity_hours_per_week,
            hourly_cost_usd=hourly_cost_usd,
        )

        timeline = await self._planner.generate_timeline(
            sequenced_actions=enriched["enriched_actions"],
            start_date=start_date,
            parallel_streams=parallel_streams,
        )

        milestones = await self._planner.define_milestones(
            timeline_entries=timeline["timeline_entries"],
            horizon_months=horizon_months,
        )

        dependencies = await self._planner.identify_dependencies(
            actions=enriched["enriched_actions"],
        )

        metadata = {
            "tenant_id": str(tenant_id),
            "assessment_id": str(assessment_id),
            "horizon_months": horizon_months,
            "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        }

        roadmap_json = await self._planner.export_roadmap_json(
            actions=enriched["enriched_actions"],
            timeline=timeline,
            milestones=milestones,
            dependencies=dependencies,
            metadata=metadata,
        )

        gantt_data = await self._planner.export_gantt_data(
            timeline_entries=timeline["timeline_entries"],
            milestones=milestones,
            start_date=timeline.get("start_date", ""),
        )

        result = {
            "roadmap_json": roadmap_json,
            "gantt_data": gantt_data,
            "summary": {
                "total_actions": action_map["total_actions_count"],
                "quick_wins": len(sequenced["quick_wins"]),
                "strategic_initiatives": len(sequenced["strategic_initiatives"]),
                "total_effort_weeks": enriched["total_effort_weeks"],
                "total_cost_usd": enriched["total_cost_usd"],
                "duration_weeks": timeline["duration_weeks"],
                "milestone_count": milestones["total_milestone_count"],
                "dependency_warnings": len(sequenced.get("dependency_warnings", [])),
                "projected_end_date": timeline.get("projected_end_date", ""),
            },
        }

        logger.info(
            "Detailed roadmap generated",
            tenant_id=str(tenant_id),
            assessment_id=str(assessment_id),
            total_actions=action_map["total_actions_count"],
            duration_weeks=timeline["duration_weeks"],
            horizon_months=horizon_months,
        )

        await self._publisher.publish(
            Topics.MATURITY_ROADMAP,
            {
                "event_type": "maturity.detailed_roadmap_generated",
                "tenant_id": str(tenant_id),
                "assessment_id": str(assessment_id),
                "total_actions": action_map["total_actions_count"],
                "horizon_months": horizon_months,
                "duration_weeks": timeline["duration_weeks"],
            },
        )

        return result


# ---------------------------------------------------------------------------
# GAP-286: Configurable dimension management service
# ---------------------------------------------------------------------------


class DimensionConfigService:
    """Manages the configurable dimension registry for maturity assessments.

    Dimensions are stored in mat_dimension_configs rather than hardcoded.
    This service provides CRUD operations and the rebalancing logic used
    when creating assessments with a custom dimension set.

    Args:
        dimension_repo: Repository for MatDimensionConfig persistence.
    """

    def __init__(
        self,
        dimension_repo: IDimensionConfigRepository,
    ) -> None:
        self._dimension_repo = dimension_repo

    async def list_active_dimensions(self) -> list[Any]:
        """Return all active dimensions ordered by default_weight descending.

        Returns:
            List of MatDimensionConfig records.
        """
        return await self._dimension_repo.list_active()

    async def get_dimension(self, dimension_id: str) -> Any:
        """Retrieve a single dimension config by ID.

        Args:
            dimension_id: Dimension slug (e.g. 'agentic_ai').

        Returns:
            MatDimensionConfig record.

        Raises:
            NotFoundError: If dimension does not exist.
        """
        config = await self._dimension_repo.get_by_id(dimension_id)
        if config is None:
            raise NotFoundError(
                resource="MatDimensionConfig",
                resource_id=dimension_id,
                error_code=ErrorCode.RESOURCE_NOT_FOUND,
            )
        return config

    async def resolve_dimension_weights(
        self,
        include_dimensions: list[str] | None,
        custom_weights: dict[str, float] | None,
    ) -> dict[str, float]:
        """Resolve the final set of dimension weights for a new assessment.

        If include_dimensions is None, uses all active dimensions.
        If custom_weights are provided, validates they sum to 1.0.
        Otherwise applies proportional auto-rebalancing.

        Args:
            include_dimensions: Optional list of dimension IDs to include.
            custom_weights: Optional explicit weight mapping.

        Returns:
            Dict mapping dimension ID to weight (sum == 1.0).

        Raises:
            ValueError: If custom_weights do not sum to 1.0 (±0.001).
            NotFoundError: If an include_dimensions entry is not found.
        """
        if custom_weights is not None:
            total = sum(custom_weights.values())
            if abs(total - 1.0) > 0.001:
                raise ValueError(
                    f"Custom dimension weights must sum to 1.0, got {total:.4f}"
                )
            return custom_weights

        active_dims = await self._dimension_repo.list_active()
        if include_dimensions is None:
            dims = active_dims
        else:
            dim_map = {d.id: d for d in active_dims}
            dims = []
            for dim_id in include_dimensions:
                if dim_id not in dim_map:
                    raise NotFoundError(
                        resource="MatDimensionConfig",
                        resource_id=dim_id,
                        error_code=ErrorCode.RESOURCE_NOT_FOUND,
                    )
                dims.append(dim_map[dim_id])

        raw = {d.id: d.default_weight for d in dims}
        total = sum(raw.values())
        if total == 0:
            raise ValueError("Cannot resolve weights: no dimensions selected")
        return {dim_id: round(w / total, 4) for dim_id, w in raw.items()}


# ---------------------------------------------------------------------------
# GAP-287: Benchmark enrichment service
# ---------------------------------------------------------------------------


# Minimum consenting tenants required for a benchmark update
_MIN_BENCHMARK_CONTRIBUTION_TENANTS: int = 30


class BenchmarkEnrichmentService:
    """Manages opt-in benchmark contribution consent and quarterly enrichment.

    Benchmark segments are updated only when at least 30 tenants have
    opted in, protecting individual tenant privacy through k-anonymity.

    Args:
        consent_repo: Repository for consent record persistence.
        enrichment_adapter: Adapter that aggregates opt-in assessment data.
        benchmark_repo: Repository for benchmark record updates.
        publisher: Kafka event publisher.
    """

    def __init__(
        self,
        consent_repo: IBenchmarkContributionConsentRepository,
        enrichment_adapter: IBenchmarkEnrichmentAdapter,
        benchmark_repo: IBenchmarkRepository,
        publisher: EventPublisher,
    ) -> None:
        self._consent_repo = consent_repo
        self._enrichment_adapter = enrichment_adapter
        self._benchmark_repo = benchmark_repo
        self._publisher = publisher

    async def set_contribution_consent(
        self,
        tenant_id: uuid.UUID,
        consented: bool,
        consent_version: str,
    ) -> Any:
        """Grant or revoke benchmark contribution consent for a tenant.

        Args:
            tenant_id: Tenant UUID.
            consented: True to opt in, False to revoke.
            consent_version: Policy version being accepted/revoked.

        Returns:
            Updated MatBenchmarkContributionConsent record.
        """
        record = await self._consent_repo.upsert(
            tenant_id=tenant_id,
            consented=consented,
            consent_version=consent_version,
        )
        logger.info(
            "benchmark_contribution_consent_updated",
            tenant_id=str(tenant_id),
            consented=consented,
            consent_version=consent_version,
        )
        return record

    async def get_contribution_consent(
        self,
        tenant_id: uuid.UUID,
    ) -> Any | None:
        """Retrieve the current consent status for a tenant.

        Args:
            tenant_id: Tenant UUID.

        Returns:
            MatBenchmarkContributionConsent record or None.
        """
        return await self._consent_repo.get_by_tenant(tenant_id)

    async def run_quarterly_enrichment(
        self,
        industry: str,
        organization_size: str,
        benchmark_period: str,
        platform_tenant_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Run quarterly benchmark enrichment for a specific segment.

        Aborts with a status dict if fewer than 30 tenants have consented,
        protecting individual tenant privacy.

        Args:
            industry: Industry vertical to enrich.
            organization_size: Organization size segment to enrich.
            benchmark_period: Target period string (e.g. '2025-Q1').
            platform_tenant_id: Admin tenant UUID for the benchmark record.

        Returns:
            Dict with status, contributing_tenant_count, and updated benchmark.
        """
        consenting_count = await self._consent_repo.count_consenting_tenants()
        if consenting_count < _MIN_BENCHMARK_CONTRIBUTION_TENANTS:
            logger.info(
                "benchmark_enrichment_skipped_insufficient_consent",
                consenting_count=consenting_count,
                minimum_required=_MIN_BENCHMARK_CONTRIBUTION_TENANTS,
                industry=industry,
                organization_size=organization_size,
            )
            return {
                "status": "skipped",
                "reason": (
                    f"Insufficient consenting tenants: {consenting_count} "
                    f"(minimum {_MIN_BENCHMARK_CONTRIBUTION_TENANTS} required)"
                ),
                "contributing_tenant_count": consenting_count,
            }

        enrichment_result = await self._enrichment_adapter.run_quarterly_enrichment(
            industry=industry,
            organization_size=organization_size,
            benchmark_period=benchmark_period,
            tenant_id=platform_tenant_id,
        )

        logger.info(
            "benchmark_enrichment_completed",
            industry=industry,
            organization_size=organization_size,
            benchmark_period=benchmark_period,
            contributing_tenant_count=consenting_count,
        )

        await self._publisher.publish(
            Topics.MATURITY_ASSESSMENT,
            {
                "event_type": "maturity.benchmark.enriched",
                "industry": industry,
                "organization_size": organization_size,
                "benchmark_period": benchmark_period,
                "contributing_tenant_count": consenting_count,
            },
        )

        return {
            "status": "completed",
            "contributing_tenant_count": consenting_count,
            "benchmark_period": benchmark_period,
            "industry": industry,
            "organization_size": organization_size,
            **enrichment_result,
        }


# ---------------------------------------------------------------------------
# GAP-291: Assessment comparison over time
# ---------------------------------------------------------------------------


class MaturityProgressService:
    """Computes maturity progress across multiple historical assessments.

    Provides time-series delta analysis and projects time to the next
    maturity level based on the current improvement rate.

    Args:
        progress_repo: Repository for querying historical assessment scores.
    """

    def __init__(
        self,
        progress_repo: IMaturityProgressRepository,
    ) -> None:
        self._progress_repo = progress_repo

    async def compute_progress(
        self,
        tenant_id: uuid.UUID,
        current_assessment_id: uuid.UUID,
        lookback_assessments: int = 5,
    ) -> dict[str, Any]:
        """Compare current assessment to historical assessments.

        Returns per-dimension deltas, overall score trajectory, and
        projected months to reach next maturity level (extrapolated from
        current improvement rate). Requires at least 2 completed assessments.

        Args:
            tenant_id: Tenant UUID for scoping.
            current_assessment_id: UUID of the reference (most recent) assessment.
            lookback_assessments: How many historical assessments to include.

        Returns:
            Dict with dimension_deltas, overall_trajectory, and
            projected_level_up_months.

        Raises:
            NotFoundError: If current_assessment_id not found for tenant.
            ConflictError: If fewer than 2 completed assessments exist.
        """
        historical = await self._progress_repo.list_completed_by_tenant(
            tenant_id=tenant_id,
            limit=lookback_assessments + 1,
        )

        if not historical:
            raise NotFoundError(
                resource="Assessment",
                resource_id=str(current_assessment_id),
                error_code=ErrorCode.RESOURCE_NOT_FOUND,
            )

        current = next(
            (a for a in historical if str(a.id) == str(current_assessment_id)),
            None,
        )
        if current is None:
            raise NotFoundError(
                resource="Assessment",
                resource_id=str(current_assessment_id),
                error_code=ErrorCode.RESOURCE_NOT_FOUND,
            )

        prior = [a for a in historical if str(a.id) != str(current_assessment_id)]

        if not prior:
            raise ConflictError(
                message="Need at least 2 completed assessments for progress comparison",
                error_code=ErrorCode.CONFLICT,
            )

        # Compute per-dimension deltas versus most recent prior assessment
        most_recent_prior = prior[-1]
        dimension_deltas = self._compute_dimension_deltas(current, most_recent_prior)

        # Overall trajectory across all historical assessments
        overall_trajectory = self._compute_trajectory(
            [a for a in historical if a.overall_score is not None]
        )

        # Project months to next maturity level
        projected_level_up_months = self._project_level_up(current, prior)

        logger.info(
            "maturity_progress_computed",
            tenant_id=str(tenant_id),
            current_assessment_id=str(current_assessment_id),
            historical_count=len(prior),
            current_level=current.maturity_level,
            projected_level_up_months=projected_level_up_months,
        )

        return {
            "current_assessment_id": str(current_assessment_id),
            "current_overall_score": current.overall_score,
            "current_maturity_level": current.maturity_level,
            "dimension_deltas": dimension_deltas,
            "overall_trajectory": overall_trajectory,
            "projected_level_up_months": projected_level_up_months,
            "historical_count": len(prior),
        }

    def _compute_dimension_deltas(
        self,
        current: Any,
        prior: Any,
    ) -> dict[str, float]:
        """Compute score change per dimension from prior to current assessment.

        Args:
            current: Current (most recent) Assessment record.
            prior: Prior Assessment record to compare against.

        Returns:
            Dict mapping dimension name to score delta (positive = improved).
        """
        dimensions = ["data", "process", "people", "technology", "governance"]
        deltas: dict[str, float] = {}
        for dim in dimensions:
            current_score = getattr(current, f"{dim}_score", None)
            prior_score = getattr(prior, f"{dim}_score", None)
            if current_score is not None and prior_score is not None:
                deltas[dim] = round(current_score - prior_score, 2)
        return deltas

    def _compute_trajectory(
        self,
        assessments: list[Any],
    ) -> list[dict[str, Any]]:
        """Build a time-series of overall scores across assessments.

        Args:
            assessments: List of Assessment records with overall_score and completed_at.

        Returns:
            List of dicts with assessment_id, completed_at, and overall_score.
        """
        return [
            {
                "assessment_id": str(a.id),
                "completed_at": a.completed_at.isoformat() if a.completed_at else None,
                "overall_score": a.overall_score,
                "maturity_level": a.maturity_level,
            }
            for a in assessments
            if a.overall_score is not None
        ]

    def _project_level_up(
        self,
        current: Any,
        historical: list[Any],
    ) -> float | None:
        """Project months until next maturity level based on improvement rate.

        Uses linear extrapolation from the average monthly score improvement
        rate across all historical assessments.

        Args:
            current: Current Assessment record.
            historical: List of prior completed Assessment records (oldest first).

        Returns:
            Projected months to next level, or None if projection not possible.
        """
        if current.overall_score is None or current.maturity_level is None:
            return None

        if len(historical) < 1:
            return None

        oldest = historical[0]
        if oldest.overall_score is None or oldest.completed_at is None:
            return None
        if current.completed_at is None:
            return None

        # Average monthly improvement rate
        elapsed_months = max(
            (current.completed_at - oldest.completed_at).days / 30.44, 0.1
        )
        total_improvement = current.overall_score - oldest.overall_score
        monthly_rate = total_improvement / elapsed_months

        if monthly_rate <= 0:
            return None

        # Score threshold for next level (each level = 20 points on 0-100 scale)
        next_level_threshold = current.maturity_level * 20.0
        if current.overall_score >= next_level_threshold:
            return 0.0

        points_needed = next_level_threshold - current.overall_score
        return round(points_needed / monthly_rate, 1)
