"""FastAPI router for the AumOS Maturity Assessment API.

All routes are thin — they validate inputs, extract tenant context,
delegate to services, and serialize responses. No business logic here.

API prefix: /api/v1/maturity
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from aumos_common.auth import get_current_tenant, get_current_user
from aumos_common.database import get_db_session
from aumos_common.events import EventPublisher, get_event_publisher
from aumos_common.schemas import TenantContext, UserContext

from aumos_maturity_assessment.adapters.kafka import MaturityEventPublisher
from aumos_maturity_assessment.adapters.repositories import (
    AssessmentRepository,
    AssessmentResponseRepository,
    BenchmarkRepository,
    PilotRepository,
    ReportRepository,
    RoadmapRepository,
)
from aumos_maturity_assessment.adapters.report_generator import ReportGeneratorAdapter
from aumos_maturity_assessment.adapters.roadmap_generator import RoadmapGeneratorAdapter
from aumos_maturity_assessment.adapters.scoring_engine import ScoringEngine
from aumos_maturity_assessment.api.schemas import (
    AssessmentListResponse,
    AssessmentResponse,
    BenchmarkCompareRequest,
    BenchmarkCompareResponse,
    BenchmarkListResponse,
    BenchmarkResponse,
    CreateAssessmentRequest,
    DesignPilotRequest,
    DetailedScoreResponse,
    GenerateReportRequest,
    GenerateRoadmapRequest,
    LogExecutionUpdateRequest,
    PilotResponse,
    ReportResponse,
    RoadmapResponse,
    SubmitResponsesRequest,
    SubmitResponsesResponse,
    UpdatePilotStatusRequest,
)
from aumos_maturity_assessment.core.services import (
    AssessmentService,
    BenchmarkService,
    PilotService,
    ReportService,
    RoadmapService,
)
from aumos_maturity_assessment.settings import Settings

router = APIRouter(prefix="/maturity", tags=["Maturity Assessment"])

settings = Settings()


# ---------------------------------------------------------------------------
# Dependency factories
# ---------------------------------------------------------------------------


def get_assessment_service(
    session: AsyncSession = Depends(get_db_session),
    publisher: EventPublisher = Depends(get_event_publisher),
) -> AssessmentService:
    """Build AssessmentService with injected dependencies."""
    return AssessmentService(
        assessment_repo=AssessmentRepository(session),
        response_repo=AssessmentResponseRepository(session),
        scoring_engine=ScoringEngine(),
        event_publisher=MaturityEventPublisher(publisher),
    )


def get_benchmark_service(
    session: AsyncSession = Depends(get_db_session),
    publisher: EventPublisher = Depends(get_event_publisher),
) -> BenchmarkService:
    """Build BenchmarkService with injected dependencies."""
    return BenchmarkService(
        benchmark_repo=BenchmarkRepository(session),
        event_publisher=MaturityEventPublisher(publisher),
    )


def get_roadmap_service(
    session: AsyncSession = Depends(get_db_session),
    publisher: EventPublisher = Depends(get_event_publisher),
) -> RoadmapService:
    """Build RoadmapService with injected dependencies."""
    return RoadmapService(
        roadmap_repo=RoadmapRepository(session),
        assessment_repo=AssessmentRepository(session),
        benchmark_repo=BenchmarkRepository(session),
        roadmap_generator=RoadmapGeneratorAdapter(settings=settings),
        event_publisher=MaturityEventPublisher(publisher),
        default_horizon_months=settings.roadmap_default_horizon_months,
    )


def get_pilot_service(
    session: AsyncSession = Depends(get_db_session),
    publisher: EventPublisher = Depends(get_event_publisher),
) -> PilotService:
    """Build PilotService with injected dependencies."""
    return PilotService(
        pilot_repo=PilotRepository(session),
        roadmap_repo=RoadmapRepository(session),
        event_publisher=MaturityEventPublisher(publisher),
    )


def get_report_service(
    session: AsyncSession = Depends(get_db_session),
    publisher: EventPublisher = Depends(get_event_publisher),
) -> ReportService:
    """Build ReportService with injected dependencies."""
    return ReportService(
        report_repo=ReportRepository(session),
        assessment_repo=AssessmentRepository(session),
        benchmark_repo=BenchmarkRepository(session),
        roadmap_repo=RoadmapRepository(session),
        report_generator=ReportGeneratorAdapter(settings=settings),
        event_publisher=MaturityEventPublisher(publisher),
        include_benchmarks=settings.report_include_benchmarks,
    )


# ---------------------------------------------------------------------------
# Assessment endpoints
# ---------------------------------------------------------------------------


@router.post("/assessments", response_model=AssessmentResponse, status_code=201)
async def create_assessment(
    body: CreateAssessmentRequest,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    user: Annotated[UserContext, Depends(get_current_user)],
    service: AssessmentService = Depends(get_assessment_service),
) -> AssessmentResponse:
    """Create a new maturity assessment for an enterprise organization.

    Initializes the assessment in-progress. Responses must be submitted
    separately, then the assessment can be scored to completion.
    """
    weights_dict = None
    if body.dimension_weights:
        weights_dict = {
            "data": body.dimension_weights.data,
            "process": body.dimension_weights.process,
            "people": body.dimension_weights.people,
            "technology": body.dimension_weights.technology,
            "governance": body.dimension_weights.governance,
        }

    assessment = await service.create_assessment(
        tenant_id=tenant.tenant_id,
        organization_name=body.organization_name,
        industry=body.industry,
        organization_size=body.organization_size,
        dimension_weights=weights_dict,
        assessment_metadata=body.assessment_metadata,
        initiated_by=user.user_id,
    )
    return AssessmentResponse.model_validate(assessment, from_attributes=True)


@router.get("/assessments/{assessment_id}", response_model=AssessmentResponse)
async def get_assessment(
    assessment_id: uuid.UUID,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    service: AssessmentService = Depends(get_assessment_service),
) -> AssessmentResponse:
    """Retrieve a maturity assessment and its current results."""
    assessment = await service.get_assessment(assessment_id, tenant.tenant_id)
    return AssessmentResponse.model_validate(assessment, from_attributes=True)


@router.get("/assessments", response_model=AssessmentListResponse)
async def list_assessments(
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    status: Annotated[str | None, Query()] = None,
    industry: Annotated[str | None, Query()] = None,
    service: AssessmentService = Depends(get_assessment_service),
) -> AssessmentListResponse:
    """List maturity assessments for the current tenant with pagination."""
    assessments, total = await service.list_assessments(
        tenant_id=tenant.tenant_id,
        page=page,
        page_size=page_size,
        status=status,
        industry=industry,
    )
    return AssessmentListResponse(
        items=[AssessmentResponse.model_validate(a, from_attributes=True) for a in assessments],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/assessments/{assessment_id}/responses", response_model=SubmitResponsesResponse)
async def submit_responses(
    assessment_id: uuid.UUID,
    body: SubmitResponsesRequest,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    service: AssessmentService = Depends(get_assessment_service),
) -> SubmitResponsesResponse:
    """Submit diagnostic question responses for an in-progress assessment."""
    response_dicts = [
        {
            "question_id": r.question_id,
            "dimension": r.dimension,
            "response_value": r.response_value,
            "numeric_score": r.numeric_score,
            "weight": r.weight,
            "response_metadata": r.response_metadata,
        }
        for r in body.responses
    ]
    created = await service.submit_responses(
        assessment_id=assessment_id,
        tenant_id=tenant.tenant_id,
        responses=response_dicts,
    )
    from aumos_maturity_assessment.api.schemas import QuestionResponseRecord

    return SubmitResponsesResponse(
        assessment_id=assessment_id,
        submitted_count=len(created),
        responses=[
            QuestionResponseRecord.model_validate(r, from_attributes=True) for r in created
        ],
    )


@router.post("/assessments/{assessment_id}/score", response_model=AssessmentResponse)
async def score_assessment(
    assessment_id: uuid.UUID,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    service: AssessmentService = Depends(get_assessment_service),
) -> AssessmentResponse:
    """Compute multi-dimensional scores and complete an assessment.

    Requires responses covering all five dimensions to have been submitted.
    """
    assessment = await service.score_assessment(
        assessment_id=assessment_id,
        tenant_id=tenant.tenant_id,
    )
    return AssessmentResponse.model_validate(assessment, from_attributes=True)


@router.get("/assessments/{assessment_id}/score", response_model=DetailedScoreResponse)
async def get_detailed_scores(
    assessment_id: uuid.UUID,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    service: AssessmentService = Depends(get_assessment_service),
) -> DetailedScoreResponse:
    """Get detailed per-dimension scoring breakdown for a completed assessment."""
    scores = await service.get_detailed_scores(
        assessment_id=assessment_id,
        tenant_id=tenant.tenant_id,
    )
    return DetailedScoreResponse.model_validate(scores)


# ---------------------------------------------------------------------------
# Benchmark endpoints
# ---------------------------------------------------------------------------


@router.post("/benchmarks/compare", response_model=BenchmarkCompareResponse)
async def compare_against_benchmarks(
    body: BenchmarkCompareRequest,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    assessment_service: AssessmentService = Depends(get_assessment_service),
    benchmark_service: BenchmarkService = Depends(get_benchmark_service),
) -> BenchmarkCompareResponse:
    """Compare an assessment's scores against industry peer benchmarks."""
    assessment = await assessment_service.get_assessment(body.assessment_id, tenant.tenant_id)
    comparison = await benchmark_service.compare_assessment(
        tenant_id=tenant.tenant_id,
        assessment=assessment,
    )
    return BenchmarkCompareResponse.model_validate(comparison)


@router.get("/benchmarks/{industry}", response_model=BenchmarkListResponse)
async def get_industry_benchmarks(
    industry: str,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    service: BenchmarkService = Depends(get_benchmark_service),
) -> BenchmarkListResponse:
    """List all available benchmark data for an industry vertical."""
    benchmarks = await service.list_industry_benchmarks(
        tenant_id=tenant.tenant_id,
        industry=industry,
    )
    return BenchmarkListResponse(
        items=[BenchmarkResponse.model_validate(b, from_attributes=True) for b in benchmarks],
        total=len(benchmarks),
    )


# ---------------------------------------------------------------------------
# Roadmap endpoints
# ---------------------------------------------------------------------------


@router.post("/roadmaps/generate", response_model=RoadmapResponse, status_code=201)
async def generate_roadmap(
    body: GenerateRoadmapRequest,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    service: RoadmapService = Depends(get_roadmap_service),
) -> RoadmapResponse:
    """Auto-generate a prioritized AI adoption roadmap from a completed assessment.

    Uses assessment scores and industry benchmarks to produce a structured
    set of initiatives organized by time horizon and expected impact.
    """
    roadmap = await service.generate_roadmap(
        assessment_id=body.assessment_id,
        tenant_id=tenant.tenant_id,
        horizon_months=body.horizon_months,
        target_maturity_level=body.target_maturity_level,
    )
    return RoadmapResponse.model_validate(roadmap, from_attributes=True)


@router.get("/roadmaps/{roadmap_id}", response_model=RoadmapResponse)
async def get_roadmap(
    roadmap_id: uuid.UUID,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    service: RoadmapService = Depends(get_roadmap_service),
) -> RoadmapResponse:
    """Retrieve a roadmap and its generated initiatives."""
    roadmap = await service.get_roadmap(roadmap_id, tenant.tenant_id)
    return RoadmapResponse.model_validate(roadmap, from_attributes=True)


@router.post("/roadmaps/{roadmap_id}/publish", response_model=RoadmapResponse)
async def publish_roadmap(
    roadmap_id: uuid.UUID,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    service: RoadmapService = Depends(get_roadmap_service),
) -> RoadmapResponse:
    """Publish a draft roadmap to make it visible to the client."""
    roadmap = await service.publish_roadmap(roadmap_id, tenant.tenant_id)
    return RoadmapResponse.model_validate(roadmap, from_attributes=True)


# ---------------------------------------------------------------------------
# Pilot endpoints
# ---------------------------------------------------------------------------


@router.post("/pilots/design", response_model=PilotResponse, status_code=201)
async def design_pilot(
    body: DesignPilotRequest,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    service: PilotService = Depends(get_pilot_service),
) -> PilotResponse:
    """Design a structured AI pilot initiative.

    Enforces ≥3 measurable success criteria to address the 88% AI pilot
    failure rate pattern of launching without measurable objectives.
    """
    pilot = await service.design_pilot(
        roadmap_id=body.roadmap_id,
        tenant_id=tenant.tenant_id,
        title=body.title,
        dimension=body.dimension,
        success_criteria=[sc.model_dump() for sc in body.success_criteria],
        failure_modes=[fm.model_dump() for fm in body.failure_modes],
        stakeholder_map=body.stakeholder_map,
        resource_requirements=body.resource_requirements,
        duration_weeks=body.duration_weeks,
    )
    return PilotResponse.model_validate(pilot, from_attributes=True)


@router.get("/pilots/{pilot_id}", response_model=PilotResponse)
async def get_pilot(
    pilot_id: uuid.UUID,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    service: PilotService = Depends(get_pilot_service),
) -> PilotResponse:
    """Retrieve a pilot and its current execution status."""
    pilot = await service.get_pilot(pilot_id, tenant.tenant_id)
    return PilotResponse.model_validate(pilot, from_attributes=True)


@router.put("/pilots/{pilot_id}/status", response_model=PilotResponse)
async def update_pilot_status(
    pilot_id: uuid.UUID,
    body: UpdatePilotStatusRequest,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    service: PilotService = Depends(get_pilot_service),
) -> PilotResponse:
    """Transition a pilot to a new lifecycle status."""
    pilot = await service.update_pilot_status(
        pilot_id=pilot_id,
        tenant_id=tenant.tenant_id,
        new_status=body.status,
    )
    return PilotResponse.model_validate(pilot, from_attributes=True)


@router.post("/pilots/{pilot_id}/execution-log", response_model=PilotResponse)
async def log_pilot_execution_update(
    pilot_id: uuid.UUID,
    body: LogExecutionUpdateRequest,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    service: PilotService = Depends(get_pilot_service),
) -> PilotResponse:
    """Append a weekly execution update to a running pilot."""
    pilot = await service.log_execution_update(
        pilot_id=pilot_id,
        tenant_id=tenant.tenant_id,
        week=body.week,
        status=body.status,
        metrics=body.metrics,
        blockers=body.blockers,
        notes=body.notes,
    )
    return PilotResponse.model_validate(pilot, from_attributes=True)


# ---------------------------------------------------------------------------
# Report endpoints
# ---------------------------------------------------------------------------


@router.post("/reports/generate", response_model=ReportResponse, status_code=201)
async def generate_report(
    body: GenerateReportRequest,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    service: ReportService = Depends(get_report_service),
) -> ReportResponse:
    """Generate an executive report from a completed assessment.

    Consolidates maturity scores, benchmark comparisons, and roadmap
    recommendations into a polished deliverable in the requested format.
    """
    report = await service.generate_report(
        assessment_id=body.assessment_id,
        tenant_id=tenant.tenant_id,
        report_type=body.report_type,
        format=body.format,
        roadmap_id=body.roadmap_id,
        include_benchmarks=body.include_benchmarks,
    )
    return ReportResponse.model_validate(report, from_attributes=True)


@router.get("/reports/{report_id}", response_model=ReportResponse)
async def get_report(
    report_id: uuid.UUID,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    service: ReportService = Depends(get_report_service),
) -> ReportResponse:
    """Retrieve a generated executive report."""
    report = await service.get_report(report_id, tenant.tenant_id)
    return ReportResponse.model_validate(report, from_attributes=True)
