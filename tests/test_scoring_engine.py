"""Unit tests for the maturity scoring engine adapter."""

import pytest

from aumos_maturity_assessment.adapters.scoring_engine import (
    ScoringEngine,
    _score_to_maturity_level,
)


@pytest.fixture()
def engine() -> ScoringEngine:
    return ScoringEngine()


STANDARD_WEIGHTS: dict[str, float] = {
    "data": 0.25,
    "process": 0.20,
    "people": 0.20,
    "technology": 0.20,
    "governance": 0.15,
}


class TestScoringEngine:
    """Tests for ScoringEngine.compute_scores."""

    @pytest.mark.asyncio()
    async def test_all_zero_scores_level_1(self, engine: ScoringEngine) -> None:
        """All-zero responses produce level 1 overall score."""
        responses = [
            {"dimension": dim, "numeric_score": 0.0, "weight": 1.0}
            for dim in ["data", "process", "people", "technology", "governance"]
        ]
        scores = await engine.compute_scores(responses, STANDARD_WEIGHTS)
        assert scores["overall_score"] == 0.0
        assert scores["maturity_level"] == 1

    @pytest.mark.asyncio()
    async def test_all_perfect_scores_level_5(self, engine: ScoringEngine) -> None:
        """All-100 responses produce level 5 overall score."""
        responses = [
            {"dimension": dim, "numeric_score": 100.0, "weight": 1.0}
            for dim in ["data", "process", "people", "technology", "governance"]
        ]
        scores = await engine.compute_scores(responses, STANDARD_WEIGHTS)
        assert scores["overall_score"] == 100.0
        assert scores["maturity_level"] == 5

    @pytest.mark.asyncio()
    async def test_weighted_average_per_dimension(self, engine: ScoringEngine) -> None:
        """Verifies weighted average is computed correctly within a dimension."""
        responses = [
            {"dimension": "data", "numeric_score": 60.0, "weight": 2.0},
            {"dimension": "data", "numeric_score": 30.0, "weight": 1.0},
            # Other dimensions at 50 to not affect overall too much
            {"dimension": "process", "numeric_score": 50.0, "weight": 1.0},
            {"dimension": "people", "numeric_score": 50.0, "weight": 1.0},
            {"dimension": "technology", "numeric_score": 50.0, "weight": 1.0},
            {"dimension": "governance", "numeric_score": 50.0, "weight": 1.0},
        ]
        scores = await engine.compute_scores(responses, STANDARD_WEIGHTS)
        # data weighted avg = (60*2 + 30*1) / 3 = 50.0
        assert scores["data_score"] == 50.0

    @pytest.mark.asyncio()
    async def test_missing_dimension_defaults_to_zero(self, engine: ScoringEngine) -> None:
        """Missing dimension responses score as zero, not an error."""
        responses = [
            {"dimension": "data", "numeric_score": 80.0, "weight": 1.0},
            # process, people, technology, governance absent
        ]
        scores = await engine.compute_scores(responses, STANDARD_WEIGHTS)
        assert scores["process_score"] == 0.0
        assert scores["people_score"] == 0.0

    @pytest.mark.asyncio()
    async def test_returns_all_required_keys(self, engine: ScoringEngine) -> None:
        """Returned dict contains all required score keys."""
        responses = [
            {"dimension": dim, "numeric_score": 50.0, "weight": 1.0}
            for dim in ["data", "process", "people", "technology", "governance"]
        ]
        scores = await engine.compute_scores(responses, STANDARD_WEIGHTS)
        required_keys = {
            "overall_score",
            "maturity_level",
            "data_score",
            "process_score",
            "people_score",
            "technology_score",
            "governance_score",
        }
        assert required_keys.issubset(scores.keys())


class TestScoreToMaturityLevel:
    """Tests for _score_to_maturity_level mapping function."""

    def test_score_0_is_level_1(self) -> None:
        assert _score_to_maturity_level(0.0) == 1

    def test_score_19_is_level_1(self) -> None:
        assert _score_to_maturity_level(19.9) == 1

    def test_score_20_is_level_2(self) -> None:
        assert _score_to_maturity_level(20.0) == 2

    def test_score_40_is_level_3(self) -> None:
        assert _score_to_maturity_level(40.0) == 3

    def test_score_60_is_level_4(self) -> None:
        assert _score_to_maturity_level(60.0) == 4

    def test_score_80_is_level_5(self) -> None:
        assert _score_to_maturity_level(80.0) == 5

    def test_score_100_is_level_5(self) -> None:
        assert _score_to_maturity_level(100.0) == 5
