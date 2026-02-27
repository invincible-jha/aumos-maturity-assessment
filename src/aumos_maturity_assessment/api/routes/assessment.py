"""FastAPI router for the AI Readiness Assessment self-service lead magnet.

All routes are thin: they parse inputs, build dependencies, delegate to
AssessmentService, and serialise responses. No business logic lives here.

API prefix: /api/v1/assessments
Auth: None — this is an anonymous self-service flow for lead capture.
"""

import time
import uuid
from collections import defaultdict
from typing import Callable

import structlog
from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from aumos_common.database import get_db_session

from aumos_maturity_assessment.adapters.repositories.assessment_repository import (
    AssessmentBenchmarkRepository,
    AssessmentResponseRepository,
    AssessmentResultRepository,
)
from aumos_maturity_assessment.api.schemas.assessment import (
    AnswerRequest,
    AnswerResponse,
    BenchmarkListResponse,
    BenchmarkResponse,
    CompleteAssessmentRequest,
    CompleteAssessmentResponse,
    QuestionSchema,
    RoadmapItemSchema,
    StartAssessmentRequest,
    StartAssessmentResponse,
)
from aumos_maturity_assessment.core.services.assessment_service import (
    AssessmentAlreadyCompletedError,
    AssessmentNotFoundError,
    AssessmentService,
    QuestionNotFoundError,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/assessments", tags=["AI Readiness Assessment"])


# ---------------------------------------------------------------------------
# In-memory token bucket rate limiter
# ---------------------------------------------------------------------------


class _TokenBucket:
    """Per-key token bucket for rate limiting.

    Each key (IP address) gets a refilling bucket of tokens. A request
    consumes one token; when the bucket is empty the request is rejected.
    Tokens refill continuously at ``rate_per_minute / 60`` tokens per second.

    This implementation is intentionally simple — no external dependencies.
    In a multi-process deployment, consider a Redis-backed alternative via
    aumos-common.

    Args:
        rate_per_minute: Maximum number of requests allowed per minute per key.
        burst: Maximum bucket capacity (allows short bursts). Defaults to
            ``rate_per_minute`` (no additional burst beyond the steady rate).
    """

    def __init__(self, rate_per_minute: int, burst: int | None = None) -> None:
        self._rate_per_second: float = rate_per_minute / 60.0
        self._burst: float = float(burst if burst is not None else rate_per_minute)
        # key -> (tokens, last_refill_timestamp)
        self._buckets: dict[str, tuple[float, float]] = defaultdict(
            lambda: (self._burst, time.monotonic())
        )

    def allow(self, key: str) -> bool:
        """Attempt to consume one token for the given key.

        Args:
            key: Rate limit key (typically a client IP address).

        Returns:
            True if the request is allowed; False if the rate limit is exceeded.
        """
        tokens, last_refill = self._buckets[key]
        now = time.monotonic()
        elapsed = now - last_refill
        tokens = min(self._burst, tokens + elapsed * self._rate_per_second)

        if tokens < 1.0:
            self._buckets[key] = (tokens, now)
            return False

        self._buckets[key] = (tokens - 1.0, now)
        return True


# One bucket per endpoint with the limits from the spec.
_start_limiter: _TokenBucket = _TokenBucket(rate_per_minute=10)
_answer_limiter: _TokenBucket = _TokenBucket(rate_per_minute=120)
_complete_limiter: _TokenBucket = _TokenBucket(rate_per_minute=5)
_benchmarks_limiter: _TokenBucket = _TokenBucket(rate_per_minute=30)


def _make_rate_limit_dependency(bucket: _TokenBucket) -> Callable[[Request], None]:
    """Return a FastAPI dependency that enforces the given token bucket.

    Args:
        bucket: The token bucket to draw from.

    Returns:
        A synchronous dependency callable that raises HTTP 429 when the
        rate limit for the requesting IP is exceeded.
    """

    def _check_rate_limit(request: Request) -> None:
        client_ip: str = (request.client.host if request.client else "") or "unknown"
        if not bucket.allow(client_ip):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please slow down and try again.",
            )

    return _check_rate_limit


# ---------------------------------------------------------------------------
# Dependency factory
# ---------------------------------------------------------------------------


def get_assessment_service(
    session: AsyncSession = Depends(get_db_session),
) -> AssessmentService:
    """Build AssessmentService with injected repository dependencies.

    Args:
        session: Async SQLAlchemy session from the database pool.

    Returns:
        Configured AssessmentService instance.
    """
    return AssessmentService(
        response_repository=AssessmentResponseRepository(session),
        result_repository=AssessmentResultRepository(session),
        benchmark_repository=AssessmentBenchmarkRepository(session),
    )


# ---------------------------------------------------------------------------
# Assessment lifecycle endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/start",
    response_model=StartAssessmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start a new AI readiness assessment session",
    dependencies=[Depends(_make_rate_limit_dependency(_start_limiter))],
)
async def start_assessment(
    body: StartAssessmentRequest,
    service: AssessmentService = Depends(get_assessment_service),
) -> StartAssessmentResponse:
    """Begin a self-service AI readiness assessment session.

    Creates a session UUID that the client uses for all subsequent answer
    submissions. Returns the complete 50-question set across 6 dimensions.

    The session is anonymous until the respondent completes the assessment
    and provides their email at the final step.
    """
    result = await service.start_assessment(
        industry_vertical=body.industry_vertical,
        company_size=body.company_size,
    )

    questions = [
        QuestionSchema(
            question_id=q["question_id"],  # type: ignore[index]
            dimension=q["dimension"],  # type: ignore[index]
            text=q["text"],  # type: ignore[index]
            weight=q["weight"],  # type: ignore[index]
        )
        for q in result["questions"]  # type: ignore[union-attr]
    ]

    logger.info(
        "Assessment session created",
        session_id=str(result["session_id"]),
        industry_vertical=body.industry_vertical,
        question_count=result["total_questions"],
    )

    return StartAssessmentResponse(
        session_id=result["session_id"],  # type: ignore[arg-type]
        questions=questions,
        total_questions=result["total_questions"],  # type: ignore[arg-type]
        dimensions=result["dimensions"],  # type: ignore[arg-type]
    )


@router.post(
    "/{session_id}/answer",
    response_model=AnswerResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit a single question answer",
    dependencies=[Depends(_make_rate_limit_dependency(_answer_limiter))],
)
async def submit_answer(
    session_id: uuid.UUID = Path(..., description="Assessment session UUID"),
    body: AnswerRequest = ...,
    service: AssessmentService = Depends(get_assessment_service),
) -> AnswerResponse:
    """Record a respondent's answer to a single assessment question.

    Answers are accepted on a 1-5 Likert scale:
        1 = Not at all implemented
        2 = Early / ad-hoc
        3 = Partially implemented
        4 = Mostly implemented
        5 = Fully implemented

    Returns progress indicating how many of the 50 questions have been
    answered so far for this session.
    """
    try:
        result = await service.submit_answer(
            session_id=session_id,
            question_id=body.question_id,
            answer_value=body.answer_value,
            industry_vertical=body.industry_vertical,
        )
    except QuestionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return AnswerResponse(
        session_id=result["session_id"],  # type: ignore[arg-type]
        question_id=result["question_id"],  # type: ignore[arg-type]
        answer_value=result["answer_value"],  # type: ignore[arg-type]
        answered_at=result["answered_at"],  # type: ignore[arg-type]
        progress=result["progress"],  # type: ignore[arg-type]
        answered_count=result["answered_count"],  # type: ignore[arg-type]
        total_questions=result["total_questions"],  # type: ignore[arg-type]
    )


@router.post(
    "/{session_id}/complete",
    response_model=CompleteAssessmentResponse,
    status_code=status.HTTP_200_OK,
    summary="Finalise the assessment and receive results",
    dependencies=[Depends(_make_rate_limit_dependency(_complete_limiter))],
)
async def complete_assessment(
    session_id: uuid.UUID = Path(..., description="Assessment session UUID"),
    body: CompleteAssessmentRequest = ...,
    service: AssessmentService = Depends(get_assessment_service),
) -> CompleteAssessmentResponse:
    """Complete the assessment and receive the full AI readiness report.

    Triggers the scoring pipeline, computes dimension scores (0-100),
    overall maturity score, peer percentile position, and a prioritised
    AumOS module roadmap. The respondent's email is captured for lead
    management and CRM synchronisation.

    Returns the full diagnostic report including:
    - Overall AI readiness score (0-100) and maturity level (1-5)
    - Per-dimension scores across all 6 assessment dimensions
    - Estimated peer percentile vs industry benchmarks
    - Prioritised AumOS module recommendations (roadmap)
    - Per-dimension benchmark comparison charts data
    """
    try:
        result = await service.complete_assessment(
            session_id=session_id,
            email=str(body.email),
            company_name=body.company_name,
            industry_vertical=body.industry_vertical,
        )
    except AssessmentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except AssessmentAlreadyCompletedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    roadmap_items = [
        RoadmapItemSchema(**item)  # type: ignore[arg-type]
        for item in result["roadmap_items"]  # type: ignore[union-attr]
    ]

    from aumos_maturity_assessment.api.schemas.assessment import BenchmarkComparisonSchema

    benchmark_comparison = [
        BenchmarkComparisonSchema(**comp)  # type: ignore[arg-type]
        for comp in result["benchmark_comparison"]  # type: ignore[union-attr]
    ]

    logger.info(
        "Assessment completed and results returned",
        session_id=str(session_id),
        maturity_level=result["maturity_level"],
        overall_score=result["overall_score"],
    )

    return CompleteAssessmentResponse(
        session_id=result["session_id"],  # type: ignore[arg-type]
        email=result["email"],  # type: ignore[arg-type]
        company_name=result["company_name"],  # type: ignore[arg-type]
        overall_score=result["overall_score"],  # type: ignore[arg-type]
        maturity_level=result["maturity_level"],  # type: ignore[arg-type]
        maturity_label=result["maturity_label"],  # type: ignore[arg-type]
        dimension_scores=result["dimension_scores"],  # type: ignore[arg-type]
        peer_percentile=result["peer_percentile"],  # type: ignore[arg-type]
        roadmap_items=roadmap_items,
        benchmark_comparison=benchmark_comparison,
        industry_vertical=result["industry_vertical"],  # type: ignore[arg-type]
        completed_at=result["completed_at"],  # type: ignore[arg-type]
    )


@router.get(
    "/benchmarks/{industry_vertical}",
    response_model=BenchmarkListResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve industry benchmark data",
    dependencies=[Depends(_make_rate_limit_dependency(_benchmarks_limiter))],
)
async def get_benchmarks(
    industry_vertical: str = Path(
        ...,
        description="Industry vertical: financial_services | healthcare | manufacturing | etc.",
    ),
    service: AssessmentService = Depends(get_assessment_service),
) -> BenchmarkListResponse:
    """Retrieve industry benchmark percentile data for an industry vertical.

    Returns p25/p50/p75 benchmark scores per assessment dimension,
    useful for rendering comparison charts on the results page.
    Returns an empty list if no benchmarks exist for the industry.
    """
    benchmark_records = await service.get_benchmarks(industry_vertical)

    benchmark_responses = [
        BenchmarkResponse(
            id=record.id,
            industry_vertical=record.industry_vertical,
            dimension=record.dimension,
            p25_score=float(record.p25_score),
            p50_score=float(record.p50_score),
            p75_score=float(record.p75_score),
            sample_size=record.sample_size,
            updated_at=record.updated_at,
        )
        for record in benchmark_records
    ]

    return BenchmarkListResponse(
        industry_vertical=industry_vertical,
        benchmarks=benchmark_responses,
        total=len(benchmark_responses),
    )
