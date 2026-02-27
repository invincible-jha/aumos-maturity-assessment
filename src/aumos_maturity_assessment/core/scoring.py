"""AI Readiness Assessment scoring algorithm.

Implements weighted scoring across the 6 assessment dimensions for the
self-service lead magnet flow. Answers are on a 1-5 Likert scale, normalised
to 0-100 before weighting. The overall score is the weighted mean of dimension
scores. Maturity levels map score ranges to 1-5 labels.

This module is intentionally independent of the database layer so that
the scoring logic can be unit-tested without any infrastructure.
"""

try:
    from aumos_common.observability import get_logger
except ImportError:
    import logging as _logging

    def get_logger(name: str) -> _logging.Logger:  # type: ignore[misc]
        """Fallback logger when aumos_common is not available."""
        return _logging.getLogger(name)


from aumos_maturity_assessment.core.questions import (
    ALL_DIMENSIONS,
    QUESTIONS_BY_ID,
    AssessmentQuestion,
)
from aumos_maturity_assessment.core.roadmap_config import (
    RoadmapItem,
    get_roadmap_items_for_dimension,
)

logger = get_logger(__name__)

# Dimension weights must sum to 1.0
DIMENSION_WEIGHTS: dict[str, float] = {
    "data_infrastructure": 0.25,
    "governance": 0.20,
    "talent_culture": 0.20,
    "technology_stack": 0.15,
    "security_posture": 0.10,
    "strategic_alignment": 0.10,
}

# Maturity level boundary thresholds (inclusive lower bound).
# These must match the enterprise scoring thresholds defined in CLAUDE.md:
#   80-100 -> Level 5 (Optimizing)
#   60-79  -> Level 4 (Managed)
#   40-59  -> Level 3 (Defined)
#   20-39  -> Level 2 (Developing)
#   0-19   -> Level 1 (Initial)
_MATURITY_THRESHOLDS: list[tuple[float, int]] = [
    (80.0, 5),  # Optimizing
    (60.0, 4),  # Managed
    (40.0, 3),  # Defined
    (20.0, 2),  # Developing
    (0.0, 1),   # Initial
]

_MATURITY_LABELS: dict[int, str] = {
    1: "Initial",
    2: "Developing",
    3: "Defined",
    4: "Managed",
    5: "Optimizing",
}

# Likert scale normalisation: convert 1-5 answer to 0-100 score
_LIKERT_SCALE_FACTOR: float = 25.0  # (answer - 1) * 25 maps 1->0, 5->100


class AnswerRecord:
    """Lightweight container for a single question answer.

    Attributes:
        question_id: Reference to the question in QUESTION_BANK.
        answer_value: Integer answer on 1-5 scale.
    """

    __slots__ = ("question_id", "answer_value")

    def __init__(self, question_id: str, answer_value: int) -> None:
        """Initialise an AnswerRecord.

        Args:
            question_id: Question identifier (e.g., 'DATA_01').
            answer_value: Answer integer in range 1-5.

        Raises:
            ValueError: If answer_value is outside the 1-5 range.
        """
        if not (1 <= answer_value <= 5):
            raise ValueError(
                f"answer_value must be between 1 and 5, got {answer_value!r} "
                f"for question {question_id!r}"
            )
        self.question_id = question_id
        self.answer_value = answer_value


class AssessmentScorer:
    """Scoring engine for the AI Readiness self-service assessment.

    Converts 1-5 Likert answers to 0-100 scores, applies per-question weights
    within dimensions, combines dimension scores using the DIMENSION_WEIGHTS
    map, and produces maturity levels and roadmap recommendations.

    DIMENSION_WEIGHTS sum to exactly 1.0:
        data_infrastructure  0.25
        governance           0.20
        talent_culture       0.20
        technology_stack     0.15
        security_posture     0.10
        strategic_alignment  0.10
    """

    DIMENSION_WEIGHTS: dict[str, float] = DIMENSION_WEIGHTS

    def score_dimension(
        self,
        answers: list[AnswerRecord],
        dimension: str,
    ) -> float:
        """Compute the 0-100 score for a single dimension.

        Filters answers to the given dimension, looks up each question's weight
        from the question bank, converts the 1-5 answer to 0-100, and computes
        the weighted mean.

        Args:
            answers: All answer records for the assessment session.
            dimension: The dimension to score (e.g., 'data_infrastructure').

        Returns:
            Weighted dimension score in range 0.0-100.0. Returns 0.0 if no
            answers exist for this dimension.
        """
        dimension_answers: list[tuple[AssessmentQuestion, AnswerRecord]] = []

        for answer in answers:
            question = QUESTIONS_BY_ID.get(answer.question_id)
            if question is None or question.dimension != dimension:
                continue
            dimension_answers.append((question, answer))

        if not dimension_answers:
            return 0.0

        total_weight: float = sum(q.weight for q, _ in dimension_answers)
        if total_weight == 0.0:
            return 0.0

        weighted_sum: float = sum(
            ((answer.answer_value - 1) * _LIKERT_SCALE_FACTOR) * question.weight
            for question, answer in dimension_answers
        )
        raw_score = weighted_sum / total_weight
        return round(raw_score, 2)

    def score_overall(self, dimension_scores: dict[str, float]) -> float:
        """Compute the weighted composite overall score from dimension scores.

        Args:
            dimension_scores: Mapping of dimension name to 0-100 score.

        Returns:
            Weighted overall score in range 0.0-100.0.
        """
        overall = sum(
            dimension_scores.get(dimension, 0.0) * weight
            for dimension, weight in DIMENSION_WEIGHTS.items()
        )
        return round(overall, 2)

    def compute_maturity_level(self, overall_score: float) -> int:
        """Map an overall score to a 1-5 maturity level.

        Thresholds:
            0-20   -> 1 (Initial)
            21-40  -> 2 (Developing)
            41-60  -> 3 (Defined)
            61-80  -> 4 (Managed)
            81-100 -> 5 (Optimizing)

        Args:
            overall_score: Composite score in range 0.0-100.0.

        Returns:
            Maturity level integer 1-5.
        """
        for threshold, level in _MATURITY_THRESHOLDS:
            if overall_score >= threshold:
                return level
        return 1

    def compute_peer_percentile(
        self,
        overall_score: float,
        industry: str,
        benchmarks: list[dict[str, object]],
    ) -> float:
        """Estimate the peer percentile for an overall score against benchmarks.

        Uses linear interpolation between p25, p50, and p75 benchmark
        percentiles to estimate the respondent's position.

        Args:
            overall_score: The assessment's composite overall score (0-100).
            industry: Industry vertical of the respondent.
            benchmarks: List of benchmark dicts with keys p25_score, p50_score,
                p75_score for the relevant industry. If empty or not matching,
                returns 50.0 as a neutral default.

        Returns:
            Estimated percentile rank in range 0.0-100.0.
        """
        industry_benchmarks = [
            b for b in benchmarks if b.get("industry_vertical") == industry
        ]
        if not industry_benchmarks:
            return 50.0

        # Use the first matching benchmark (most recent should be pre-sorted)
        benchmark = industry_benchmarks[0]
        p25 = float(benchmark.get("p25_score", 0.0))
        p50 = float(benchmark.get("p50_score", 50.0))
        p75 = float(benchmark.get("p75_score", 75.0))

        if overall_score <= p25:
            # Below 25th percentile — interpolate between 0 and 25
            if p25 == 0.0:
                return 0.0
            return round((overall_score / p25) * 25.0, 1)

        if overall_score <= p50:
            # Between p25 and p50
            if p50 == p25:
                return 25.0
            fraction = (overall_score - p25) / (p50 - p25)
            return round(25.0 + fraction * 25.0, 1)

        if overall_score <= p75:
            # Between p50 and p75
            if p75 == p50:
                return 50.0
            fraction = (overall_score - p50) / (p75 - p50)
            return round(50.0 + fraction * 25.0, 1)

        # Above p75 — interpolate between 75 and 100
        if p75 >= 100.0:
            return 100.0
        fraction = min((overall_score - p75) / (100.0 - p75), 1.0)
        return round(75.0 + fraction * 25.0, 1)

    def generate_roadmap(
        self,
        dimension_scores: dict[str, float],
    ) -> list[RoadmapItem]:
        """Generate roadmap recommendations based on dimension scores.

        Identifies the weakest dimensions and maps them to AumOS module
        recommendations using the ROADMAP_MAPPINGS configuration. Recommendations
        are ordered from the weakest dimension first to guide prioritisation.

        Args:
            dimension_scores: Mapping of dimension name to 0-100 score.

        Returns:
            Ordered list of RoadmapItem recommendations, weakest dimension first.
        """
        # Sort dimensions from lowest score to highest (biggest gaps first)
        sorted_dimensions = sorted(
            ALL_DIMENSIONS,
            key=lambda dimension: dimension_scores.get(dimension, 0.0),
        )

        roadmap_items: list[RoadmapItem] = []
        for dimension in sorted_dimensions:
            score = dimension_scores.get(dimension, 0.0)
            items = get_roadmap_items_for_dimension(dimension, score)
            roadmap_items.extend(items)

        logger.debug(
            "Roadmap generated from dimension scores",
            dimension_count=len(sorted_dimensions),
            roadmap_item_count=len(roadmap_items),
            weakest_dimension=sorted_dimensions[0] if sorted_dimensions else None,
        )
        return roadmap_items

    def score_assessment(
        self,
        answers: list[AnswerRecord],
        industry: str = "",
        benchmarks: list[dict[str, object]] | None = None,
    ) -> dict[str, object]:
        """Run the full scoring pipeline for an assessment session.

        Computes all dimension scores, the overall score, maturity level,
        peer percentile, and roadmap recommendations in a single call.

        Args:
            answers: All answer records submitted for the session.
            industry: Respondent's industry vertical for benchmark lookup.
            benchmarks: Optional list of benchmark dicts for percentile calculation.

        Returns:
            Dict with keys: dimension_scores, overall_score, maturity_level,
            maturity_label, peer_percentile, roadmap_items.
        """
        dimension_scores: dict[str, float] = {
            dimension: self.score_dimension(answers, dimension)
            for dimension in ALL_DIMENSIONS
        }
        overall_score = self.score_overall(dimension_scores)
        maturity_level = self.compute_maturity_level(overall_score)
        maturity_label = _MATURITY_LABELS.get(maturity_level, "Unknown")
        peer_percentile = self.compute_peer_percentile(
            overall_score,
            industry,
            benchmarks or [],
        )
        roadmap_items = self.generate_roadmap(dimension_scores)

        logger.info(
            "Assessment scoring complete",
            overall_score=overall_score,
            maturity_level=maturity_level,
            peer_percentile=peer_percentile,
            answer_count=len(answers),
            industry=industry,
        )

        return {
            "dimension_scores": dimension_scores,
            "overall_score": overall_score,
            "maturity_level": maturity_level,
            "maturity_label": maturity_label,
            "peer_percentile": peer_percentile,
            "roadmap_items": roadmap_items,
        }
