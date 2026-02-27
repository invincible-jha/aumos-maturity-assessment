"""Service layer orchestrating the AI Readiness Assessment lead magnet workflow.

Implements the full self-service assessment flow:
    1. start_assessment()    — creates a session and returns the question set
    2. submit_answer()       — stores one answer and reports progress
    3. complete_assessment() — triggers scoring, generates results and roadmap
    4. get_benchmarks()      — returns industry benchmark data

All database access goes through repository interfaces. No SQLAlchemy or
FastAPI imports belong here — those live in the adapters and routes layers.
"""

import uuid
from datetime import datetime, timezone
from typing import Any

from aumos_common.observability import get_logger

from aumos_maturity_assessment.core.interfaces import (
    ILMBenchmarkRepository,
    ILMResponseRepository,
    ILMResultRepository,
)
from aumos_maturity_assessment.core.models.assessment import (
    LMAssessmentBenchmark,
)
from aumos_maturity_assessment.core.questions import (
    ALL_DIMENSIONS,
    QUESTION_BANK,
    QUESTIONS_BY_ID,
    AssessmentQuestion,
)
from aumos_maturity_assessment.core.roadmap_config import RoadmapItem
from aumos_maturity_assessment.core.scoring import AnswerRecord, AssessmentScorer

logger = get_logger(__name__)

_TOTAL_QUESTIONS: int = len(QUESTION_BANK)
_SCORER: AssessmentScorer = AssessmentScorer()


class AssessmentNotFoundError(Exception):
    """Raised when no responses exist for the requested session."""


class AssessmentAlreadyCompletedError(Exception):
    """Raised when attempting to complete an already completed session."""


class QuestionNotFoundError(Exception):
    """Raised when the submitted question_id is not in the question bank."""


class AssessmentService:
    """Orchestrates the self-service AI readiness assessment workflow.

    Depends on repository instances injected at construction time.
    Contains no framework-specific code.
    """

    def __init__(
        self,
        response_repository: ILMResponseRepository,
        result_repository: ILMResultRepository,
        benchmark_repository: ILMBenchmarkRepository,
    ) -> None:
        """Initialise the service with repository dependencies.

        The parameters accept any object satisfying the Protocol interfaces
        defined in ``core/interfaces.py``. Concrete implementations are
        injected from the route dependency factory — the core layer never
        imports from the adapters layer.

        Args:
            response_repository: Repository for question answer records.
            result_repository: Repository for finalised assessment results.
            benchmark_repository: Repository for industry benchmark data.
        """
        self._response_repo = response_repository
        self._result_repo = result_repository
        self._benchmark_repo = benchmark_repository

    async def start_assessment(
        self,
        industry_vertical: str,
        company_size: str,
    ) -> dict[str, object]:
        """Create a new assessment session and return the full question set.

        Generates a fresh session UUID that the client must use in all
        subsequent answer submissions and the completion call.

        Args:
            industry_vertical: The respondent's industry vertical.
            company_size: Organisation size category.

        Returns:
            Dict with session_id, questions list, total_questions, and dimensions.
        """
        session_id = uuid.uuid4()

        questions_data = [
            {
                "question_id": q.question_id,
                "dimension": q.dimension,
                "text": q.text,
                "weight": q.weight,
            }
            for q in QUESTION_BANK
        ]

        logger.info(
            "Assessment session started",
            session_id=str(session_id),
            industry_vertical=industry_vertical,
            company_size=company_size,
            question_count=_TOTAL_QUESTIONS,
        )

        return {
            "session_id": session_id,
            "questions": questions_data,
            "total_questions": _TOTAL_QUESTIONS,
            "dimensions": ALL_DIMENSIONS,
        }

    async def submit_answer(
        self,
        session_id: uuid.UUID,
        question_id: str,
        answer_value: int,
        industry_vertical: str,
    ) -> dict[str, object]:
        """Store a single question answer and return session progress.

        Args:
            session_id: Assessment session UUID from start_assessment().
            question_id: Question identifier being answered.
            answer_value: Likert-scale answer 1-5.
            industry_vertical: Industry vertical (must match session).

        Returns:
            Dict with session_id, question_id, answer_value, answered_at,
            progress, answered_count, and total_questions.

        Raises:
            QuestionNotFoundError: If question_id is not in the question bank.
        """
        if question_id not in QUESTIONS_BY_ID:
            raise QuestionNotFoundError(
                f"Question {question_id!r} is not a valid assessment question."
            )

        answered_at = datetime.now(tz=timezone.utc)
        await self._response_repo.create_response(
            session_id=session_id,
            question_id=question_id,
            answer_value=answer_value,
            industry_vertical=industry_vertical,
            answered_at=answered_at,
        )

        answered_count = await self._response_repo.count_responses_by_session(session_id)
        progress = round(answered_count / _TOTAL_QUESTIONS, 4)

        logger.debug(
            "Answer submitted",
            session_id=str(session_id),
            question_id=question_id,
            answered_count=answered_count,
            progress=progress,
        )

        return {
            "session_id": session_id,
            "question_id": question_id,
            "answer_value": answer_value,
            "answered_at": answered_at,
            "progress": progress,
            "answered_count": answered_count,
            "total_questions": _TOTAL_QUESTIONS,
        }

    async def complete_assessment(
        self,
        session_id: uuid.UUID,
        email: str,
        company_name: str,
        industry_vertical: str,
    ) -> dict[str, object]:
        """Finalise the assessment, compute scores, and return full results.

        Retrieves all submitted answers, runs the scoring pipeline, persists
        the result record, and returns the complete assessment output including
        dimension scores, overall score, maturity level, peer percentile,
        benchmark comparisons, and roadmap recommendations.

        Args:
            session_id: Assessment session UUID.
            email: Contact email for lead capture.
            company_name: Organisation name.
            industry_vertical: Industry vertical for benchmark lookup.

        Returns:
            Dict with all scoring outputs, roadmap_items, and benchmark_comparison.

        Raises:
            AssessmentNotFoundError: If no answers exist for this session.
            AssessmentAlreadyCompletedError: If this session was already completed.
        """
        # Verify session has not already been completed
        existing_result = await self._result_repo.get_result_by_session(session_id)
        if existing_result is not None:
            raise AssessmentAlreadyCompletedError(
                f"Session {session_id} has already been completed."
            )

        # Retrieve all answers
        response_records = await self._response_repo.get_responses_by_session(session_id)
        if not response_records:
            raise AssessmentNotFoundError(
                f"No answers found for session {session_id}. "
                "Submit answers before completing the assessment."
            )

        # Build AnswerRecord objects for the scorer
        answer_records: list[AnswerRecord] = []
        for response in response_records:
            try:
                answer_records.append(
                    AnswerRecord(
                        question_id=response.question_id,
                        answer_value=response.answer_value,
                    )
                )
            except ValueError:
                logger.warning(
                    "Invalid answer value skipped during scoring",
                    session_id=str(session_id),
                    question_id=response.question_id,
                    answer_value=response.answer_value,
                )

        # Fetch benchmarks for peer percentile calculation
        benchmark_records = await self._benchmark_repo.get_benchmarks_by_industry(
            industry_vertical
        )
        benchmarks_as_dicts = _benchmarks_to_dicts(benchmark_records)

        # Run the full scoring pipeline
        scoring_result = _SCORER.score_assessment(
            answers=answer_records,
            industry=industry_vertical,
            benchmarks=benchmarks_as_dicts,
        )

        dimension_scores: dict[str, float] = scoring_result["dimension_scores"]  # type: ignore[assignment]
        overall_score: float = scoring_result["overall_score"]  # type: ignore[assignment]
        maturity_level: int = scoring_result["maturity_level"]  # type: ignore[assignment]
        maturity_label: str = scoring_result["maturity_label"]  # type: ignore[assignment]
        peer_percentile: float = scoring_result["peer_percentile"]  # type: ignore[assignment]
        roadmap_items: list[RoadmapItem] = scoring_result["roadmap_items"]  # type: ignore[assignment]

        # Persist the result
        result_record = await self._result_repo.create_result(
            session_id=session_id,
            email=email,
            company_name=company_name,
            overall_score=overall_score,
            dimension_scores=dimension_scores,
            maturity_level=maturity_level,
            industry_vertical=industry_vertical,
            peer_percentile=peer_percentile,
        )

        # Build benchmark comparison output
        benchmark_comparison = _build_benchmark_comparison(
            dimension_scores=dimension_scores,
            benchmark_records=benchmark_records,
        )

        completed_at = result_record.created_at

        logger.info(
            "Assessment completed",
            session_id=str(session_id),
            email=email,
            company_name=company_name,
            overall_score=overall_score,
            maturity_level=maturity_level,
            peer_percentile=peer_percentile,
            roadmap_item_count=len(roadmap_items),
        )

        return {
            "session_id": session_id,
            "email": email,
            "company_name": company_name,
            "overall_score": overall_score,
            "maturity_level": maturity_level,
            "maturity_label": maturity_label,
            "dimension_scores": dimension_scores,
            "peer_percentile": peer_percentile,
            "roadmap_items": [_roadmap_item_to_dict(item) for item in roadmap_items],
            "benchmark_comparison": benchmark_comparison,
            "industry_vertical": industry_vertical,
            "completed_at": completed_at,
        }

    async def get_benchmarks(
        self,
        industry_vertical: str,
    ) -> list[Any]:
        """Retrieve industry benchmark records for a given vertical.

        Args:
            industry_vertical: Industry vertical to query.

        Returns:
            List of benchmark records ordered by dimension.
        """
        return await self._benchmark_repo.get_benchmarks_by_industry(industry_vertical)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _benchmarks_to_dicts(
    records: list[LMAssessmentBenchmark],
) -> list[dict[str, object]]:
    """Convert ORM benchmark records to scorer-compatible dicts.

    Args:
        records: ORM benchmark records.

    Returns:
        List of dicts with keys: industry_vertical, dimension, p25_score,
        p50_score, p75_score, sample_size.
    """
    return [
        {
            "industry_vertical": record.industry_vertical,
            "dimension": record.dimension,
            "p25_score": float(record.p25_score),
            "p50_score": float(record.p50_score),
            "p75_score": float(record.p75_score),
            "sample_size": record.sample_size,
        }
        for record in records
    ]


def _build_benchmark_comparison(
    dimension_scores: dict[str, float],
    benchmark_records: list[LMAssessmentBenchmark],
) -> list[dict[str, object]]:
    """Build the benchmark comparison list for the response.

    Args:
        dimension_scores: Per-dimension scores from the scorer.
        benchmark_records: Benchmark ORM records for the industry.

    Returns:
        List of comparison dicts, one per dimension that has benchmark data.
    """
    benchmark_by_dimension: dict[str, LMAssessmentBenchmark] = {
        record.dimension: record for record in benchmark_records
    }

    comparisons: list[dict[str, object]] = []
    for dimension, score in dimension_scores.items():
        benchmark = benchmark_by_dimension.get(dimension)
        if benchmark is None:
            continue

        comparisons.append(
            {
                "dimension": dimension,
                "respondent_score": score,
                "p25_score": float(benchmark.p25_score),
                "p50_score": float(benchmark.p50_score),
                "p75_score": float(benchmark.p75_score),
                "percentile_position": _SCORER.compute_peer_percentile(
                    score,
                    benchmark.industry_vertical,
                    _benchmarks_to_dicts([benchmark]),
                ),
            }
        )
    return comparisons


def _roadmap_item_to_dict(item: RoadmapItem) -> dict[str, object]:
    """Serialise a RoadmapItem dataclass to a plain dict.

    Args:
        item: RoadmapItem from the scoring engine.

    Returns:
        Dict representation for JSON serialisation.
    """
    return {
        "module": item.module,
        "dimension": item.dimension,
        "score_band": item.score_band,
        "title": item.title,
        "description": item.description,
        "priority": item.priority,
        "estimated_effort_weeks": item.estimated_effort_weeks,
    }
