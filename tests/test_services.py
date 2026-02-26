"""Unit tests for maturity assessment business logic services."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aumos_common.errors import ConflictError, NotFoundError
from aumos_maturity_assessment.core.services import (
    AssessmentService,
    BenchmarkService,
    PilotService,
    RoadmapService,
    _compute_percentile,
    _maturity_level_label,
)


# ---------------------------------------------------------------------------
# AssessmentService tests
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_assessment_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture()
def mock_response_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture()
def mock_scoring_engine() -> AsyncMock:
    return AsyncMock()


@pytest.fixture()
def mock_publisher() -> AsyncMock:
    return AsyncMock()


@pytest.fixture()
def assessment_service(
    mock_assessment_repo: AsyncMock,
    mock_response_repo: AsyncMock,
    mock_scoring_engine: AsyncMock,
    mock_publisher: AsyncMock,
) -> AssessmentService:
    return AssessmentService(
        assessment_repo=mock_assessment_repo,
        response_repo=mock_response_repo,
        scoring_engine=mock_scoring_engine,
        event_publisher=mock_publisher,
    )


class TestCreateAssessment:
    """Tests for AssessmentService.create_assessment."""

    @pytest.mark.asyncio()
    async def test_create_assessment_success(
        self,
        assessment_service: AssessmentService,
        mock_assessment_repo: AsyncMock,
        mock_publisher: AsyncMock,
    ) -> None:
        """Successfully creates an assessment with valid inputs."""
        tenant_id = uuid.uuid4()
        mock_assessment = MagicMock()
        mock_assessment.id = uuid.uuid4()
        mock_assessment_repo.create.return_value = mock_assessment

        result = await assessment_service.create_assessment(
            tenant_id=tenant_id,
            organization_name="ACME Corp",
            industry="technology",
            organization_size="enterprise",
        )

        assert result is mock_assessment
        mock_assessment_repo.create.assert_called_once()
        mock_publisher.publish.assert_called_once()

    @pytest.mark.asyncio()
    async def test_create_assessment_invalid_industry(
        self, assessment_service: AssessmentService
    ) -> None:
        """Raises ConflictError for an invalid industry."""
        with pytest.raises(ConflictError, match="Invalid industry"):
            await assessment_service.create_assessment(
                tenant_id=uuid.uuid4(),
                organization_name="ACME Corp",
                industry="not_a_real_industry",
                organization_size="enterprise",
            )

    @pytest.mark.asyncio()
    async def test_create_assessment_invalid_org_size(
        self, assessment_service: AssessmentService
    ) -> None:
        """Raises ConflictError for an invalid organization_size."""
        with pytest.raises(ConflictError, match="Invalid organization_size"):
            await assessment_service.create_assessment(
                tenant_id=uuid.uuid4(),
                organization_name="ACME Corp",
                industry="technology",
                organization_size="giant_corporation",
            )

    @pytest.mark.asyncio()
    async def test_create_assessment_bad_weights(
        self, assessment_service: AssessmentService
    ) -> None:
        """Raises ConflictError when dimension weights do not sum to 1.0."""
        with pytest.raises(ConflictError, match="must sum to 1.0"):
            await assessment_service.create_assessment(
                tenant_id=uuid.uuid4(),
                organization_name="ACME Corp",
                industry="healthcare",
                organization_size="mid_market",
                dimension_weights={
                    "data": 0.5,
                    "process": 0.5,
                    "people": 0.5,
                    "technology": 0.5,
                    "governance": 0.5,
                },
            )


class TestScoreAssessment:
    """Tests for AssessmentService.score_assessment."""

    @pytest.mark.asyncio()
    async def test_score_assessment_missing_dimensions(
        self,
        assessment_service: AssessmentService,
        mock_assessment_repo: AsyncMock,
        mock_response_repo: AsyncMock,
    ) -> None:
        """Raises ConflictError when not all dimensions are covered by responses."""
        assessment_id = uuid.uuid4()
        tenant_id = uuid.uuid4()

        mock_assessment = MagicMock()
        mock_assessment.status = "in_progress"
        mock_assessment_repo.get_by_id.return_value = mock_assessment

        # Only data and process responses — missing people, technology, governance
        mock_resp_data = MagicMock()
        mock_resp_data.dimension = "data"
        mock_resp_process = MagicMock()
        mock_resp_process.dimension = "process"
        mock_response_repo.list_by_assessment.return_value = [
            mock_resp_data,
            mock_resp_process,
        ]

        with pytest.raises(ConflictError, match="missing responses for dimensions"):
            await assessment_service.score_assessment(
                assessment_id=assessment_id,
                tenant_id=tenant_id,
            )

    @pytest.mark.asyncio()
    async def test_score_assessment_not_in_progress(
        self,
        assessment_service: AssessmentService,
        mock_assessment_repo: AsyncMock,
    ) -> None:
        """Raises ConflictError when assessment is already completed."""
        assessment_id = uuid.uuid4()
        tenant_id = uuid.uuid4()

        mock_assessment = MagicMock()
        mock_assessment.id = assessment_id
        mock_assessment.status = "completed"
        mock_assessment_repo.get_by_id.return_value = mock_assessment

        with pytest.raises(ConflictError, match="status is completed"):
            await assessment_service.score_assessment(
                assessment_id=assessment_id,
                tenant_id=tenant_id,
            )


# ---------------------------------------------------------------------------
# PilotService tests
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_pilot_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture()
def mock_roadmap_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture()
def pilot_service(
    mock_pilot_repo: AsyncMock,
    mock_roadmap_repo: AsyncMock,
    mock_publisher: AsyncMock,
) -> PilotService:
    return PilotService(
        pilot_repo=mock_pilot_repo,
        roadmap_repo=mock_roadmap_repo,
        event_publisher=mock_publisher,
    )


class TestDesignPilot:
    """Tests for PilotService.design_pilot."""

    @pytest.mark.asyncio()
    async def test_design_pilot_insufficient_criteria(
        self,
        pilot_service: PilotService,
        mock_roadmap_repo: AsyncMock,
    ) -> None:
        """Raises ConflictError when fewer than 3 success criteria provided."""
        roadmap_id = uuid.uuid4()
        tenant_id = uuid.uuid4()

        mock_roadmap = MagicMock()
        mock_roadmap_repo.get_by_id.return_value = mock_roadmap

        with pytest.raises(ConflictError, match="success criteria required"):
            await pilot_service.design_pilot(
                roadmap_id=roadmap_id,
                tenant_id=tenant_id,
                title="Test Pilot",
                dimension="data",
                success_criteria=[
                    {"metric": "accuracy", "target_value": "95%", "measurement_method": "test_set", "baseline_value": "80%"},
                    {"metric": "latency", "target_value": "<100ms", "measurement_method": "p99", "baseline_value": None},
                ],  # Only 2 — needs 3
                failure_modes=[],
                stakeholder_map={"sponsor": "Jane"},
                resource_requirements={"compute": "GPU"},
            )

    @pytest.mark.asyncio()
    async def test_design_pilot_invalid_dimension(
        self,
        pilot_service: PilotService,
        mock_roadmap_repo: AsyncMock,
    ) -> None:
        """Raises ConflictError for an invalid dimension."""
        roadmap_id = uuid.uuid4()
        tenant_id = uuid.uuid4()

        mock_roadmap = MagicMock()
        mock_roadmap_repo.get_by_id.return_value = mock_roadmap

        with pytest.raises(ConflictError, match="Invalid dimension"):
            await pilot_service.design_pilot(
                roadmap_id=roadmap_id,
                tenant_id=tenant_id,
                title="Test Pilot",
                dimension="finance",  # not a valid dimension
                success_criteria=[
                    {"metric": "m1", "target_value": "v1", "measurement_method": "m", "baseline_value": None},
                    {"metric": "m2", "target_value": "v2", "measurement_method": "m", "baseline_value": None},
                    {"metric": "m3", "target_value": "v3", "measurement_method": "m", "baseline_value": None},
                ],
                failure_modes=[],
                stakeholder_map={"sponsor": "Bob"},
                resource_requirements={},
            )

    @pytest.mark.asyncio()
    async def test_design_pilot_roadmap_not_found(
        self,
        pilot_service: PilotService,
        mock_roadmap_repo: AsyncMock,
    ) -> None:
        """Raises NotFoundError when roadmap does not exist."""
        mock_roadmap_repo.get_by_id.return_value = None

        with pytest.raises(NotFoundError, match="Roadmap"):
            await pilot_service.design_pilot(
                roadmap_id=uuid.uuid4(),
                tenant_id=uuid.uuid4(),
                title="Test Pilot",
                dimension="data",
                success_criteria=[
                    {"metric": "m1", "target_value": "v1", "measurement_method": "m", "baseline_value": None},
                    {"metric": "m2", "target_value": "v2", "measurement_method": "m", "baseline_value": None},
                    {"metric": "m3", "target_value": "v3", "measurement_method": "m", "baseline_value": None},
                ],
                failure_modes=[],
                stakeholder_map={},
                resource_requirements={},
            )


# ---------------------------------------------------------------------------
# Utility function tests
# ---------------------------------------------------------------------------


class TestMaturityLevelLabel:
    """Tests for _maturity_level_label helper."""

    def test_level_1_is_initial(self) -> None:
        assert _maturity_level_label(1) == "Initial"

    def test_level_5_is_optimizing(self) -> None:
        assert _maturity_level_label(5) == "Optimizing"

    def test_none_returns_unknown(self) -> None:
        assert _maturity_level_label(None) == "Unknown"


class TestComputePercentile:
    """Tests for _compute_percentile helper."""

    def test_above_p90(self) -> None:
        result = _compute_percentile(95, 20, 40, 60, 80)
        assert result == 90

    def test_above_p50(self) -> None:
        result = _compute_percentile(55, 20, 40, 60, 80)
        assert result == 50

    def test_below_p25(self) -> None:
        result = _compute_percentile(10, 20, 40, 60, 80)
        assert result == 10
