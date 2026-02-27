"""Unit tests for the AI Readiness Assessment scoring algorithm.

Tests cover:
- Dimension weights sum to exactly 1.0
- score_dimension with known inputs (Likert -> 0-100)
- score_overall weighted combination
- compute_maturity_level boundary conditions
- compute_peer_percentile interpolation
- generate_roadmap dimension ordering
- score_assessment full pipeline
- Edge cases: all-1 answers, all-5 answers, missing dimension answers
"""

import pytest

from aumos_maturity_assessment.core.questions import ALL_DIMENSIONS, QUESTION_BANK
from aumos_maturity_assessment.core.scoring import (
    DIMENSION_WEIGHTS,
    AnswerRecord,
    AssessmentScorer,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def scorer() -> AssessmentScorer:
    """Provide a fresh AssessmentScorer instance."""
    return AssessmentScorer()


def _make_answers(answer_value: int, dimensions: list[str] | None = None) -> list[AnswerRecord]:
    """Build AnswerRecord list with a uniform answer value for all (or selected) dimensions.

    Args:
        answer_value: Likert value 1-5 to apply uniformly.
        dimensions: Optional subset of dimensions to include. Defaults to all.

    Returns:
        List of AnswerRecord objects for the selected questions.
    """
    target_dimensions = set(dimensions) if dimensions else set(ALL_DIMENSIONS)
    return [
        AnswerRecord(question_id=q.question_id, answer_value=answer_value)
        for q in QUESTION_BANK
        if q.dimension in target_dimensions
    ]


# ---------------------------------------------------------------------------
# DIMENSION_WEIGHTS validation
# ---------------------------------------------------------------------------


class TestDimensionWeights:
    """Verify the dimension weight configuration."""

    def test_weights_sum_to_one(self) -> None:
        """All DIMENSION_WEIGHTS must sum to exactly 1.0 within floating-point tolerance."""
        total = sum(DIMENSION_WEIGHTS.values())
        assert abs(total - 1.0) < 1e-9, f"Weights sum to {total}, expected 1.0"

    def test_all_six_dimensions_have_weights(self) -> None:
        """DIMENSION_WEIGHTS must include all 6 assessment dimensions."""
        expected_dimensions = {
            "data_infrastructure",
            "governance",
            "talent_culture",
            "technology_stack",
            "security_posture",
            "strategic_alignment",
        }
        assert set(DIMENSION_WEIGHTS.keys()) == expected_dimensions

    def test_all_weights_positive(self) -> None:
        """Every dimension weight must be strictly positive."""
        for dimension, weight in DIMENSION_WEIGHTS.items():
            assert weight > 0.0, f"Weight for {dimension!r} is non-positive: {weight}"


# ---------------------------------------------------------------------------
# AnswerRecord validation
# ---------------------------------------------------------------------------


class TestAnswerRecord:
    """Verify AnswerRecord construction and validation."""

    def test_valid_answer_values(self) -> None:
        """AnswerRecord accepts all valid 1-5 values without error."""
        for value in range(1, 6):
            record = AnswerRecord(question_id="DATA_01", answer_value=value)
            assert record.answer_value == value

    def test_answer_value_zero_raises(self) -> None:
        """AnswerRecord rejects answer_value=0."""
        with pytest.raises(ValueError, match="must be between 1 and 5"):
            AnswerRecord(question_id="DATA_01", answer_value=0)

    def test_answer_value_six_raises(self) -> None:
        """AnswerRecord rejects answer_value=6."""
        with pytest.raises(ValueError, match="must be between 1 and 5"):
            AnswerRecord(question_id="DATA_01", answer_value=6)

    def test_answer_value_negative_raises(self) -> None:
        """AnswerRecord rejects negative answer_value."""
        with pytest.raises(ValueError, match="must be between 1 and 5"):
            AnswerRecord(question_id="DATA_01", answer_value=-1)


# ---------------------------------------------------------------------------
# score_dimension
# ---------------------------------------------------------------------------


class TestScoreDimension:
    """Tests for AssessmentScorer.score_dimension."""

    def test_all_answers_1_produces_score_0(self, scorer: AssessmentScorer) -> None:
        """All answers of 1 (minimum) should produce a dimension score of 0."""
        answers = _make_answers(1, ["data_infrastructure"])
        score = scorer.score_dimension(answers, "data_infrastructure")
        assert score == 0.0

    def test_all_answers_5_produces_score_100(self, scorer: AssessmentScorer) -> None:
        """All answers of 5 (maximum) should produce a dimension score of 100."""
        answers = _make_answers(5, ["data_infrastructure"])
        score = scorer.score_dimension(answers, "data_infrastructure")
        assert score == 100.0

    def test_all_answers_3_produces_score_50(self, scorer: AssessmentScorer) -> None:
        """All answers of 3 (midpoint) should produce a dimension score of 50."""
        answers = _make_answers(3, ["governance"])
        score = scorer.score_dimension(answers, "governance")
        assert score == 50.0

    def test_no_answers_for_dimension_returns_zero(self, scorer: AssessmentScorer) -> None:
        """Missing dimension answers should return 0.0 not raise an error."""
        # Only supply answers for data_infrastructure
        answers = _make_answers(4, ["data_infrastructure"])
        score = scorer.score_dimension(answers, "governance")
        assert score == 0.0

    def test_score_is_bounded_0_to_100(self, scorer: AssessmentScorer) -> None:
        """Scores must remain within 0-100 for any valid answer set."""
        for answer_value in [1, 2, 3, 4, 5]:
            answers = _make_answers(answer_value)
            for dimension in ALL_DIMENSIONS:
                score = scorer.score_dimension(answers, dimension)
                assert 0.0 <= score <= 100.0, (
                    f"Score {score} out of range for dimension {dimension!r} "
                    f"with answer_value {answer_value}"
                )

    def test_higher_answer_produces_higher_score(self, scorer: AssessmentScorer) -> None:
        """Monotonically increasing answers should produce monotonically increasing scores."""
        scores = []
        for answer_value in [1, 2, 3, 4, 5]:
            answers = _make_answers(answer_value, ["technology_stack"])
            score = scorer.score_dimension(answers, "technology_stack")
            scores.append(score)

        for i in range(1, len(scores)):
            assert scores[i] > scores[i - 1], (
                f"Score did not increase monotonically: {scores}"
            )

    def test_score_excludes_wrong_dimension_answers(self, scorer: AssessmentScorer) -> None:
        """Answers for other dimensions must not influence the scored dimension."""
        low_answers = _make_answers(1, ["strategic_alignment"])
        high_answers = _make_answers(5, ["data_infrastructure"])
        combined = low_answers + high_answers

        data_score = scorer.score_dimension(combined, "data_infrastructure")
        strategy_score = scorer.score_dimension(combined, "strategic_alignment")

        assert data_score == 100.0
        assert strategy_score == 0.0


# ---------------------------------------------------------------------------
# score_overall
# ---------------------------------------------------------------------------


class TestScoreOverall:
    """Tests for AssessmentScorer.score_overall."""

    def test_all_dimension_scores_100_gives_overall_100(
        self, scorer: AssessmentScorer
    ) -> None:
        """All dimensions at 100 should produce overall_score of 100."""
        dimension_scores = {dim: 100.0 for dim in ALL_DIMENSIONS}
        overall = scorer.score_overall(dimension_scores)
        assert overall == 100.0

    def test_all_dimension_scores_0_gives_overall_0(
        self, scorer: AssessmentScorer
    ) -> None:
        """All dimensions at 0 should produce overall_score of 0."""
        dimension_scores = {dim: 0.0 for dim in ALL_DIMENSIONS}
        overall = scorer.score_overall(dimension_scores)
        assert overall == 0.0

    def test_weighted_combination_is_correct(self, scorer: AssessmentScorer) -> None:
        """Spot-check weighted combination formula."""
        # Only data_infrastructure has a non-zero score
        dimension_scores = {dim: 0.0 for dim in ALL_DIMENSIONS}
        dimension_scores["data_infrastructure"] = 100.0

        overall = scorer.score_overall(dimension_scores)
        # Expected: 100 * 0.25 = 25.0
        assert abs(overall - 25.0) < 0.01

    def test_missing_dimension_treated_as_zero(self, scorer: AssessmentScorer) -> None:
        """Missing dimension in dimension_scores dict should be treated as 0."""
        # Only provide two dimensions
        dimension_scores = {
            "data_infrastructure": 60.0,
            "governance": 60.0,
        }
        overall = scorer.score_overall(dimension_scores)
        # Expected: 60 * 0.25 + 60 * 0.20 = 15 + 12 = 27.0
        assert abs(overall - 27.0) < 0.01


# ---------------------------------------------------------------------------
# compute_maturity_level
# ---------------------------------------------------------------------------


class TestComputeMaturityLevel:
    """Tests for AssessmentScorer.compute_maturity_level boundary conditions."""

    @pytest.mark.parametrize(
        ("score", "expected_level"),
        [
            # Level 1: 0-20 (inclusive per task spec: 0-20=1)
            (0.0, 1),
            (20.0, 1),
            (20.9, 1),
            # Level 2: 21-40
            (21.0, 2),
            (40.0, 2),
            (40.9, 2),
            # Level 3: 41-60
            (41.0, 3),
            (60.0, 3),
            (60.9, 3),
            # Level 4: 61-80
            (61.0, 4),
            (80.0, 4),
            (80.9, 4),
            # Level 5: 81-100
            (81.0, 5),
            (100.0, 5),
        ],
    )
    def test_maturity_level_boundaries(
        self,
        scorer: AssessmentScorer,
        score: float,
        expected_level: int,
    ) -> None:
        """Verify level boundaries for key score values per task spec (0-20=1, 21-40=2, etc.)."""
        assert scorer.compute_maturity_level(score) == expected_level, (
            f"Score {score} should be level {expected_level}"
        )

    def test_all_1_answers_gives_level_1(self, scorer: AssessmentScorer) -> None:
        """All-minimum answers should produce the lowest maturity level."""
        answers = _make_answers(1)
        dimension_scores = {
            dim: scorer.score_dimension(answers, dim) for dim in ALL_DIMENSIONS
        }
        overall = scorer.score_overall(dimension_scores)
        level = scorer.compute_maturity_level(overall)
        assert level == 1

    def test_all_5_answers_gives_level_5(self, scorer: AssessmentScorer) -> None:
        """All-maximum answers should produce the highest maturity level."""
        answers = _make_answers(5)
        dimension_scores = {
            dim: scorer.score_dimension(answers, dim) for dim in ALL_DIMENSIONS
        }
        overall = scorer.score_overall(dimension_scores)
        level = scorer.compute_maturity_level(overall)
        assert level == 5


# ---------------------------------------------------------------------------
# compute_peer_percentile
# ---------------------------------------------------------------------------


class TestComputePeerPercentile:
    """Tests for AssessmentScorer.compute_peer_percentile interpolation."""

    def test_no_benchmarks_returns_50(self, scorer: AssessmentScorer) -> None:
        """When no benchmarks exist, default to 50th percentile."""
        result = scorer.compute_peer_percentile(75.0, "technology", [])
        assert result == 50.0

    def test_no_matching_industry_returns_50(self, scorer: AssessmentScorer) -> None:
        """Benchmarks for a different industry should not be used."""
        benchmarks = [
            {
                "industry_vertical": "healthcare",
                "p25_score": 30.0,
                "p50_score": 50.0,
                "p75_score": 70.0,
            }
        ]
        result = scorer.compute_peer_percentile(75.0, "technology", benchmarks)
        assert result == 50.0

    def test_score_at_median_returns_50(self, scorer: AssessmentScorer) -> None:
        """Score equal to p50 should return approximately 50th percentile."""
        benchmarks = [
            {
                "industry_vertical": "technology",
                "p25_score": 30.0,
                "p50_score": 50.0,
                "p75_score": 70.0,
            }
        ]
        result = scorer.compute_peer_percentile(50.0, "technology", benchmarks)
        assert abs(result - 50.0) < 0.1

    def test_score_at_p75_returns_75(self, scorer: AssessmentScorer) -> None:
        """Score equal to p75 should return approximately 75th percentile."""
        benchmarks = [
            {
                "industry_vertical": "technology",
                "p25_score": 30.0,
                "p50_score": 50.0,
                "p75_score": 70.0,
            }
        ]
        result = scorer.compute_peer_percentile(70.0, "technology", benchmarks)
        assert abs(result - 75.0) < 0.1

    def test_score_at_p25_returns_25(self, scorer: AssessmentScorer) -> None:
        """Score equal to p25 should return approximately 25th percentile."""
        benchmarks = [
            {
                "industry_vertical": "technology",
                "p25_score": 30.0,
                "p50_score": 50.0,
                "p75_score": 70.0,
            }
        ]
        result = scorer.compute_peer_percentile(30.0, "technology", benchmarks)
        assert abs(result - 25.0) < 0.1

    def test_percentile_is_bounded_0_to_100(self, scorer: AssessmentScorer) -> None:
        """Percentile must always be in 0-100 range."""
        benchmarks = [
            {
                "industry_vertical": "healthcare",
                "p25_score": 40.0,
                "p50_score": 55.0,
                "p75_score": 70.0,
            }
        ]
        for score in [0.0, 30.0, 55.0, 80.0, 100.0]:
            result = scorer.compute_peer_percentile(score, "healthcare", benchmarks)
            assert 0.0 <= result <= 100.0, f"Percentile {result} out of range for score {score}"


# ---------------------------------------------------------------------------
# generate_roadmap
# ---------------------------------------------------------------------------


class TestGenerateRoadmap:
    """Tests for AssessmentScorer.generate_roadmap."""

    def test_returns_list_of_roadmap_items(self, scorer: AssessmentScorer) -> None:
        """generate_roadmap should return a non-empty list."""
        dimension_scores = {dim: 30.0 for dim in ALL_DIMENSIONS}
        items = scorer.generate_roadmap(dimension_scores)
        assert isinstance(items, list)
        assert len(items) > 0

    def test_weakest_dimension_appears_first(self, scorer: AssessmentScorer) -> None:
        """Items for the weakest dimension should appear before stronger ones."""
        dimension_scores = {dim: 80.0 for dim in ALL_DIMENSIONS}
        dimension_scores["security_posture"] = 10.0  # weakest

        items = scorer.generate_roadmap(dimension_scores)
        # First item should be for security_posture
        assert items[0].dimension == "security_posture"

    def test_low_score_produces_low_band_recommendations(
        self, scorer: AssessmentScorer
    ) -> None:
        """Scores below 40 should produce 'low' band recommendations."""
        dimension_scores = {dim: 20.0 for dim in ALL_DIMENSIONS}
        items = scorer.generate_roadmap(dimension_scores)

        for item in items:
            assert item.score_band == "low", (
                f"Expected 'low' band but got {item.score_band!r} for {item.module!r}"
            )

    def test_high_score_produces_high_band_recommendations(
        self, scorer: AssessmentScorer
    ) -> None:
        """Scores at 75+ should produce 'high' band recommendations."""
        dimension_scores = {dim: 80.0 for dim in ALL_DIMENSIONS}
        items = scorer.generate_roadmap(dimension_scores)

        for item in items:
            assert item.score_band == "high", (
                f"Expected 'high' band but got {item.score_band!r} for {item.module!r}"
            )

    def test_roadmap_covers_all_dimensions(self, scorer: AssessmentScorer) -> None:
        """The roadmap should include recommendations for every dimension."""
        dimension_scores = {dim: 50.0 for dim in ALL_DIMENSIONS}
        items = scorer.generate_roadmap(dimension_scores)

        covered_dimensions = {item.dimension for item in items}
        for dimension in ALL_DIMENSIONS:
            assert dimension in covered_dimensions, (
                f"Dimension {dimension!r} has no roadmap recommendations"
            )

    def test_each_roadmap_item_has_required_fields(
        self, scorer: AssessmentScorer
    ) -> None:
        """Every RoadmapItem must have all required fields populated."""
        dimension_scores = {dim: 40.0 for dim in ALL_DIMENSIONS}
        items = scorer.generate_roadmap(dimension_scores)

        for item in items:
            assert item.module, f"Item {item!r} has empty module"
            assert item.dimension, f"Item {item!r} has empty dimension"
            assert item.score_band in ("low", "medium", "high"), (
                f"Item {item!r} has invalid score_band {item.score_band!r}"
            )
            assert item.title, f"Item {item!r} has empty title"
            assert item.description, f"Item {item!r} has empty description"
            assert item.priority in ("critical", "high", "medium", "low"), (
                f"Item {item!r} has invalid priority {item.priority!r}"
            )
            assert item.estimated_effort_weeks > 0, (
                f"Item {item!r} has non-positive effort estimate"
            )


# ---------------------------------------------------------------------------
# score_assessment (full pipeline)
# ---------------------------------------------------------------------------


class TestScoreAssessment:
    """Tests for AssessmentScorer.score_assessment full pipeline."""

    def test_all_1_answers(self, scorer: AssessmentScorer) -> None:
        """All-minimum answers should produce level 1, score ~0."""
        answers = _make_answers(1)
        result = scorer.score_assessment(answers)

        assert result["overall_score"] == 0.0
        assert result["maturity_level"] == 1
        assert result["maturity_label"] == "Initial"
        assert result["peer_percentile"] == 50.0  # No benchmarks → default

    def test_all_5_answers(self, scorer: AssessmentScorer) -> None:
        """All-maximum answers should produce level 5, score 100."""
        answers = _make_answers(5)
        result = scorer.score_assessment(answers)

        assert result["overall_score"] == 100.0
        assert result["maturity_level"] == 5
        assert result["maturity_label"] == "Optimizing"

    def test_mixed_answers_produces_intermediate_result(
        self, scorer: AssessmentScorer
    ) -> None:
        """Mixed answers (3 across all) should produce a level 3 result."""
        answers = _make_answers(3)
        result = scorer.score_assessment(answers)

        assert result["overall_score"] == 50.0
        assert result["maturity_level"] == 3
        assert result["maturity_label"] == "Defined"

    def test_result_contains_all_required_keys(self, scorer: AssessmentScorer) -> None:
        """score_assessment result must contain all required output keys."""
        answers = _make_answers(3)
        result = scorer.score_assessment(answers)

        required_keys = {
            "dimension_scores",
            "overall_score",
            "maturity_level",
            "maturity_label",
            "peer_percentile",
            "roadmap_items",
        }
        for key in required_keys:
            assert key in result, f"Missing key {key!r} in scoring result"

    def test_dimension_scores_covers_all_dimensions(
        self, scorer: AssessmentScorer
    ) -> None:
        """dimension_scores must include all 6 assessment dimensions."""
        answers = _make_answers(3)
        result = scorer.score_assessment(answers)

        dimension_scores = result["dimension_scores"]
        for dimension in ALL_DIMENSIONS:
            assert dimension in dimension_scores, (
                f"Dimension {dimension!r} missing from dimension_scores"
            )

    def test_roadmap_items_is_non_empty_list(self, scorer: AssessmentScorer) -> None:
        """roadmap_items must be a non-empty list for any valid answer set."""
        answers = _make_answers(2)
        result = scorer.score_assessment(answers)

        roadmap_items = result["roadmap_items"]
        assert isinstance(roadmap_items, list)
        assert len(roadmap_items) > 0

    def test_with_benchmarks_affects_percentile(self, scorer: AssessmentScorer) -> None:
        """Providing benchmark data should produce a non-default percentile."""
        answers = _make_answers(4)  # Should score above median
        benchmarks = [
            {
                "industry_vertical": "technology",
                "p25_score": 40.0,
                "p50_score": 55.0,
                "p75_score": 70.0,
            }
        ]
        result = scorer.score_assessment(
            answers,
            industry="technology",
            benchmarks=benchmarks,
        )
        # With answer=4 the score should be ~75, which is > p75=70, so >75th percentile
        assert result["peer_percentile"] > 75.0
