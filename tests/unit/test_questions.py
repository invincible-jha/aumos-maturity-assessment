"""Unit tests for the AI Readiness Assessment question bank.

Tests verify:
- Exactly 50 questions exist in QUESTION_BANK
- All 6 dimensions are represented
- Each dimension has at least 8 questions
- Question IDs are unique
- All weights within a dimension sum to approximately 1.0
- Weight values are positive and individually <= 1.0
- No question has empty text
- All dimensions match ALL_DIMENSIONS list
"""

import pytest

from aumos_maturity_assessment.core.questions import (
    ALL_DIMENSIONS,
    QUESTION_BANK,
    QUESTIONS_BY_DIMENSION,
    QUESTIONS_BY_ID,
    AssessmentQuestion,
)

_EXPECTED_TOTAL_QUESTIONS = 50
_EXPECTED_DIMENSIONS = {
    "data_infrastructure",
    "governance",
    "talent_culture",
    "technology_stack",
    "security_posture",
    "strategic_alignment",
}
_MIN_QUESTIONS_PER_DIMENSION = 8


class TestQuestionBankSize:
    """Tests verifying the total question count."""

    def test_exactly_50_questions(self) -> None:
        """QUESTION_BANK must contain exactly 50 questions."""
        assert len(QUESTION_BANK) == _EXPECTED_TOTAL_QUESTIONS, (
            f"Expected {_EXPECTED_TOTAL_QUESTIONS} questions, found {len(QUESTION_BANK)}"
        )

    def test_questions_by_id_has_all_questions(self) -> None:
        """QUESTIONS_BY_ID dict must have the same count as QUESTION_BANK."""
        assert len(QUESTIONS_BY_ID) == len(QUESTION_BANK)


class TestQuestionDimensions:
    """Tests verifying dimension coverage."""

    def test_all_six_dimensions_present(self) -> None:
        """All 6 assessment dimensions must appear in QUESTION_BANK."""
        present_dimensions = {q.dimension for q in QUESTION_BANK}
        assert present_dimensions == _EXPECTED_DIMENSIONS, (
            f"Missing dimensions: {_EXPECTED_DIMENSIONS - present_dimensions}"
        )

    def test_all_dimensions_in_all_dimensions_list(self) -> None:
        """ALL_DIMENSIONS list must include exactly the 6 expected dimensions."""
        assert set(ALL_DIMENSIONS) == _EXPECTED_DIMENSIONS

    def test_all_dimensions_list_has_six_entries(self) -> None:
        """ALL_DIMENSIONS must contain exactly 6 entries with no duplicates."""
        assert len(ALL_DIMENSIONS) == 6
        assert len(set(ALL_DIMENSIONS)) == 6

    @pytest.mark.parametrize("dimension", list(_EXPECTED_DIMENSIONS))
    def test_each_dimension_has_minimum_questions(self, dimension: str) -> None:
        """Each dimension must have at least 8 questions."""
        questions_in_dimension = [q for q in QUESTION_BANK if q.dimension == dimension]
        assert len(questions_in_dimension) >= _MIN_QUESTIONS_PER_DIMENSION, (
            f"Dimension {dimension!r} has only {len(questions_in_dimension)} questions, "
            f"expected at least {_MIN_QUESTIONS_PER_DIMENSION}"
        )

    def test_questions_by_dimension_dict_is_complete(self) -> None:
        """QUESTIONS_BY_DIMENSION must include all 6 dimensions."""
        assert set(QUESTIONS_BY_DIMENSION.keys()) == _EXPECTED_DIMENSIONS


class TestQuestionIds:
    """Tests verifying question ID uniqueness and format."""

    def test_all_question_ids_are_unique(self) -> None:
        """No two questions should share the same question_id."""
        all_ids = [q.question_id for q in QUESTION_BANK]
        assert len(all_ids) == len(set(all_ids)), (
            f"Duplicate question IDs found: {[i for i in all_ids if all_ids.count(i) > 1]}"
        )

    def test_questions_by_id_lookup_works(self) -> None:
        """Every question_id must be retrievable from QUESTIONS_BY_ID."""
        for question in QUESTION_BANK:
            found = QUESTIONS_BY_ID.get(question.question_id)
            assert found is not None, (
                f"Question {question.question_id!r} not found in QUESTIONS_BY_ID"
            )
            assert found.question_id == question.question_id

    @pytest.mark.parametrize("dimension_prefix,dimension", [
        ("DATA", "data_infrastructure"),
        ("GOV", "governance"),
        ("TAL", "talent_culture"),
        ("TECH", "technology_stack"),
        ("SEC", "security_posture"),
        ("STR", "strategic_alignment"),
    ])
    def test_question_id_prefix_matches_dimension(
        self,
        dimension_prefix: str,
        dimension: str,
    ) -> None:
        """Question IDs must start with the expected prefix for their dimension."""
        for question in QUESTION_BANK:
            if question.dimension == dimension:
                assert question.question_id.startswith(dimension_prefix), (
                    f"Question {question.question_id!r} in dimension {dimension!r} "
                    f"should start with {dimension_prefix!r}"
                )


class TestQuestionWeights:
    """Tests verifying question weight validity."""

    @pytest.mark.parametrize("dimension", list(_EXPECTED_DIMENSIONS))
    def test_weights_sum_to_approximately_one_per_dimension(
        self,
        dimension: str,
    ) -> None:
        """Weights within each dimension should sum to approximately 1.0."""
        questions_in_dimension = QUESTIONS_BY_DIMENSION.get(dimension, [])
        total_weight = sum(q.weight for q in questions_in_dimension)
        assert abs(total_weight - 1.0) < 0.01, (
            f"Dimension {dimension!r} weights sum to {total_weight:.4f}, expected ~1.0"
        )

    def test_all_weights_are_positive(self) -> None:
        """Every question weight must be strictly positive."""
        for question in QUESTION_BANK:
            assert question.weight > 0.0, (
                f"Question {question.question_id!r} has non-positive weight {question.weight}"
            )

    def test_all_weights_at_most_one(self) -> None:
        """No individual question weight should exceed 1.0."""
        for question in QUESTION_BANK:
            assert question.weight <= 1.0, (
                f"Question {question.question_id!r} has weight {question.weight} > 1.0"
            )


class TestQuestionText:
    """Tests verifying question text quality."""

    def test_no_empty_question_text(self) -> None:
        """Every question must have non-empty text."""
        for question in QUESTION_BANK:
            assert question.text.strip(), (
                f"Question {question.question_id!r} has empty text"
            )

    def test_question_text_minimum_length(self) -> None:
        """Question text should be at least 20 characters to be meaningful."""
        min_length = 20
        for question in QUESTION_BANK:
            assert len(question.text) >= min_length, (
                f"Question {question.question_id!r} text is too short "
                f"({len(question.text)} chars)"
            )

    def test_all_questions_are_assessment_question_instances(self) -> None:
        """All items in QUESTION_BANK must be AssessmentQuestion dataclass instances."""
        for question in QUESTION_BANK:
            assert isinstance(question, AssessmentQuestion), (
                f"Item {question!r} is not an AssessmentQuestion instance"
            )

    def test_all_dimensions_are_strings(self) -> None:
        """dimension field on every question must be a non-empty string."""
        for question in QUESTION_BANK:
            assert isinstance(question.dimension, str)
            assert question.dimension.strip()
