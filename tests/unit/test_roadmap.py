"""Unit tests for roadmap configuration and recommendation generation.

Tests cover:
- ROADMAP_MAPPINGS has all 6 dimensions with low/medium/high bands
- get_score_band returns correct band for score boundaries
- get_roadmap_items_for_dimension returns correct module IDs per band
- RoadmapItem fields are fully populated
- AssessmentScorer.generate_roadmap orders by weakest dimension first
- Each dimension at each score band produces recommendations
"""

import pytest

from aumos_maturity_assessment.core.questions import ALL_DIMENSIONS
from aumos_maturity_assessment.core.roadmap_config import (
    ROADMAP_MAPPINGS,
    RoadmapItem,
    get_roadmap_items_for_dimension,
    get_score_band,
)
from aumos_maturity_assessment.core.scoring import AnswerRecord, AssessmentScorer


_ALL_SCORE_BANDS = ("low", "medium", "high")


# ---------------------------------------------------------------------------
# ROADMAP_MAPPINGS structure tests
# ---------------------------------------------------------------------------


class TestRoadmapMappingsStructure:
    """Verify the ROADMAP_MAPPINGS config has all required entries."""

    def test_all_six_dimensions_in_mappings(self) -> None:
        """ROADMAP_MAPPINGS must include all 6 assessment dimensions."""
        for dimension in ALL_DIMENSIONS:
            assert dimension in ROADMAP_MAPPINGS, (
                f"Dimension {dimension!r} not found in ROADMAP_MAPPINGS"
            )

    def test_each_dimension_has_three_bands(self) -> None:
        """Each dimension must have low, medium, and high bands."""
        for dimension in ALL_DIMENSIONS:
            bands = ROADMAP_MAPPINGS[dimension]
            for band in _ALL_SCORE_BANDS:
                assert band in bands, (
                    f"Dimension {dimension!r} missing band {band!r}"
                )

    def test_each_band_has_at_least_one_module(self) -> None:
        """Every score band must map to at least one AumOS module."""
        for dimension in ALL_DIMENSIONS:
            for band in _ALL_SCORE_BANDS:
                modules = ROADMAP_MAPPINGS[dimension][band]
                assert len(modules) >= 1, (
                    f"Dimension {dimension!r} band {band!r} has no modules"
                )

    def test_module_ids_are_strings(self) -> None:
        """All module IDs must be non-empty strings."""
        for dimension, bands in ROADMAP_MAPPINGS.items():
            for band, modules in bands.items():
                for module_id in modules:
                    assert isinstance(module_id, str), (
                        f"Module ID {module_id!r} in {dimension}/{band} is not a string"
                    )
                    assert module_id.startswith("aumos-"), (
                        f"Module ID {module_id!r} should start with 'aumos-'"
                    )


# ---------------------------------------------------------------------------
# get_score_band
# ---------------------------------------------------------------------------


class TestGetScoreBand:
    """Tests for the score -> band mapping function."""

    @pytest.mark.parametrize(
        ("score", "expected_band"),
        [
            (0.0, "low"),
            (19.9, "low"),
            (39.9, "low"),
            (40.0, "medium"),
            (55.0, "medium"),
            (69.9, "medium"),
            (70.0, "high"),
            (85.0, "high"),
            (100.0, "high"),
        ],
    )
    def test_score_band_boundaries(self, score: float, expected_band: str) -> None:
        """Verify score band assignment at boundary values."""
        assert get_score_band(score) == expected_band, (
            f"Score {score} should map to band {expected_band!r}, "
            f"got {get_score_band(score)!r}"
        )


# ---------------------------------------------------------------------------
# get_roadmap_items_for_dimension
# ---------------------------------------------------------------------------


class TestGetRoadmapItemsForDimension:
    """Tests for roadmap item retrieval per dimension and score."""

    @pytest.mark.parametrize("dimension", ALL_DIMENSIONS)
    @pytest.mark.parametrize(
        ("score", "expected_band"),
        [
            (20.0, "low"),
            (55.0, "medium"),
            (80.0, "high"),
        ],
    )
    def test_returns_items_for_all_dimensions_and_bands(
        self,
        dimension: str,
        score: float,
        expected_band: str,
    ) -> None:
        """Every dimension at every score band should return at least one item."""
        items = get_roadmap_items_for_dimension(dimension, score)
        assert len(items) >= 1, (
            f"No items for dimension {dimension!r} at score {score} (band {expected_band!r})"
        )

    @pytest.mark.parametrize("dimension", ALL_DIMENSIONS)
    def test_items_have_correct_dimension(self, dimension: str) -> None:
        """Returned items must carry the correct dimension label."""
        items = get_roadmap_items_for_dimension(dimension, 30.0)
        for item in items:
            assert item.dimension == dimension, (
                f"Item {item.module!r} has wrong dimension {item.dimension!r}, "
                f"expected {dimension!r}"
            )

    @pytest.mark.parametrize("dimension", ALL_DIMENSIONS)
    @pytest.mark.parametrize(
        ("score", "expected_band"),
        [
            (10.0, "low"),
            (50.0, "medium"),
            (85.0, "high"),
        ],
    )
    def test_items_have_correct_score_band(
        self,
        dimension: str,
        score: float,
        expected_band: str,
    ) -> None:
        """Items returned for a score must have the matching score_band."""
        items = get_roadmap_items_for_dimension(dimension, score)
        for item in items:
            assert item.score_band == expected_band, (
                f"Item {item.module!r} has band {item.score_band!r}, "
                f"expected {expected_band!r} for score {score}"
            )

    def test_unknown_dimension_raises_value_error(self) -> None:
        """Requesting roadmap items for an unknown dimension must raise ValueError."""
        with pytest.raises(ValueError, match="Unknown dimension"):
            get_roadmap_items_for_dimension("nonexistent_dimension", 50.0)

    def test_all_returned_items_are_roadmap_items(self) -> None:
        """Every returned object must be a RoadmapItem dataclass instance."""
        items = get_roadmap_items_for_dimension("governance", 40.0)
        for item in items:
            assert isinstance(item, RoadmapItem), (
                f"Item {item!r} is not a RoadmapItem instance"
            )

    @pytest.mark.parametrize("dimension", ALL_DIMENSIONS)
    def test_roadmap_item_fields_are_populated(self, dimension: str) -> None:
        """Every RoadmapItem must have all required fields non-empty."""
        items = get_roadmap_items_for_dimension(dimension, 25.0)
        for item in items:
            assert item.module, f"Empty module in item {item!r}"
            assert item.dimension, f"Empty dimension in item {item!r}"
            assert item.score_band in _ALL_SCORE_BANDS, (
                f"Invalid score_band {item.score_band!r} in item {item!r}"
            )
            assert item.title, f"Empty title in item {item!r}"
            assert item.description, f"Empty description in item {item!r}"
            assert item.priority in ("critical", "high", "medium", "low"), (
                f"Invalid priority {item.priority!r} in item {item!r}"
            )
            assert item.estimated_effort_weeks > 0, (
                f"Non-positive effort estimate in item {item!r}"
            )


# ---------------------------------------------------------------------------
# AssessmentScorer.generate_roadmap integration
# ---------------------------------------------------------------------------


class TestScorerGenerateRoadmap:
    """Integration tests verifying the scorer's roadmap generation."""

    @pytest.fixture()
    def scorer(self) -> AssessmentScorer:
        """Provide a fresh AssessmentScorer."""
        return AssessmentScorer()

    @pytest.mark.parametrize("dimension", ALL_DIMENSIONS)
    @pytest.mark.parametrize("score", [15.0, 55.0, 85.0])
    def test_generate_roadmap_all_dimensions_and_bands(
        self,
        scorer: AssessmentScorer,
        dimension: str,
        score: float,
    ) -> None:
        """generate_roadmap should produce items for any valid score configuration."""
        dimension_scores = {dim: 50.0 for dim in ALL_DIMENSIONS}
        dimension_scores[dimension] = score  # vary the target dimension

        items = scorer.generate_roadmap(dimension_scores)
        assert len(items) > 0, (
            f"No roadmap items generated for {dimension!r} at score {score}"
        )

    def test_weakest_dimension_first_in_roadmap(
        self, scorer: AssessmentScorer
    ) -> None:
        """The roadmap must start with items for the dimension with the lowest score."""
        dimension_scores = {dim: 80.0 for dim in ALL_DIMENSIONS}
        dimension_scores["talent_culture"] = 5.0  # clearly weakest

        items = scorer.generate_roadmap(dimension_scores)
        assert items[0].dimension == "talent_culture", (
            f"First item should be for 'talent_culture' but got {items[0].dimension!r}"
        )

    def test_generates_items_for_all_six_dimensions(
        self, scorer: AssessmentScorer
    ) -> None:
        """Roadmap should include recommendations for every dimension."""
        dimension_scores = {dim: 50.0 for dim in ALL_DIMENSIONS}
        items = scorer.generate_roadmap(dimension_scores)

        covered = {item.dimension for item in items}
        for dimension in ALL_DIMENSIONS:
            assert dimension in covered, (
                f"No roadmap items generated for dimension {dimension!r}"
            )

    def test_roadmap_items_match_expected_bands(
        self, scorer: AssessmentScorer
    ) -> None:
        """Items for each dimension must match the score band of that dimension's score."""
        dimension_scores = {
            "data_infrastructure": 10.0,   # low
            "governance": 55.0,            # medium
            "talent_culture": 80.0,        # high
            "technology_stack": 20.0,      # low
            "security_posture": 60.0,      # medium
            "strategic_alignment": 90.0,   # high
        }
        items = scorer.generate_roadmap(dimension_scores)

        for item in items:
            expected_band = get_score_band(dimension_scores[item.dimension])
            assert item.score_band == expected_band, (
                f"Item {item.module!r} for {item.dimension!r} has band {item.score_band!r}, "
                f"expected {expected_band!r}"
            )
