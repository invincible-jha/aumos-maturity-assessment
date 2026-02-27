"""Integration tests for the AI Readiness Assessment self-service API.

Tests the full assessment lifecycle end-to-end using mocked repositories,
simulating the HTTP flow from session creation through completion.

Each test uses a fresh async HTTP client with the FastAPI dependency injection
overridden to substitute mock repositories and services.
"""

import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from httpx import AsyncClient

from aumos_maturity_assessment.core.questions import QUESTION_BANK


# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------


_VALID_SESSION_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
_START_REQUEST = {
    "industry_vertical": "technology",
    "company_size": "enterprise",
}
_ANSWER_REQUEST = {
    "question_id": "DATA_01",
    "answer_value": 4,
    "industry_vertical": "technology",
}
_COMPLETE_REQUEST = {
    "email": "cto@acmecorp.com",
    "company_name": "Acme Corporation",
    "industry_vertical": "technology",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_response_record(
    session_id: uuid.UUID,
    question_id: str,
    answer_value: int,
) -> MagicMock:
    """Build a mock LMAssessmentResponse ORM-like object.

    Args:
        session_id: Session UUID.
        question_id: Question identifier.
        answer_value: Likert answer value.

    Returns:
        MagicMock with relevant attributes set.
    """
    record = MagicMock()
    record.id = uuid.uuid4()
    record.session_id = session_id
    record.question_id = question_id
    record.answer_value = answer_value
    record.industry_vertical = "technology"
    record.answered_at = datetime.now(tz=timezone.utc)
    return record


def _make_mock_result_record(session_id: uuid.UUID) -> MagicMock:
    """Build a mock LMAssessmentResult ORM-like object.

    Args:
        session_id: Session UUID.

    Returns:
        MagicMock with all result fields set.
    """
    record = MagicMock()
    record.id = uuid.uuid4()
    record.session_id = session_id
    record.email = "cto@acmecorp.com"
    record.company_name = "Acme Corporation"
    record.overall_score = 75.0
    record.dimension_scores = {
        "data_infrastructure": 70.0,
        "governance": 65.0,
        "talent_culture": 80.0,
        "technology_stack": 75.0,
        "security_posture": 60.0,
        "strategic_alignment": 85.0,
    }
    record.maturity_level = 4
    record.industry_vertical = "technology"
    record.peer_percentile = 72.5
    record.crm_sync_status = "pending"
    record.created_at = datetime.now(tz=timezone.utc)
    record.updated_at = datetime.now(tz=timezone.utc)
    return record


def _make_mock_benchmark(industry: str, dimension: str) -> MagicMock:
    """Build a mock LMAssessmentBenchmark record.

    Args:
        industry: Industry vertical.
        dimension: Assessment dimension.

    Returns:
        MagicMock with benchmark fields.
    """
    record = MagicMock()
    record.id = uuid.uuid4()
    record.industry_vertical = industry
    record.dimension = dimension
    record.p25_score = 35.0
    record.p50_score = 55.0
    record.p75_score = 70.0
    record.sample_size = 150
    record.updated_at = datetime.now(tz=timezone.utc)
    return record


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_response_repo() -> AsyncMock:
    """Mock AssessmentResponseRepository."""
    return AsyncMock()


@pytest.fixture()
def mock_result_repo() -> AsyncMock:
    """Mock AssessmentResultRepository."""
    return AsyncMock()


@pytest.fixture()
def mock_benchmark_repo() -> AsyncMock:
    """Mock AssessmentBenchmarkRepository."""
    return AsyncMock()


@pytest.fixture()
def mock_assessment_service(
    mock_response_repo: AsyncMock,
    mock_result_repo: AsyncMock,
    mock_benchmark_repo: AsyncMock,
) -> Any:
    """Build AssessmentService with mock repositories."""
    from aumos_maturity_assessment.core.services.assessment_service import AssessmentService

    return AssessmentService(
        response_repository=mock_response_repo,
        result_repository=mock_result_repo,
        benchmark_repository=mock_benchmark_repo,
    )


@pytest.fixture()
async def api_client(mock_assessment_service: Any) -> AsyncClient:
    """Async HTTP client with assessment service dependency overridden."""
    from httpx import ASGITransport

    from aumos_maturity_assessment.api.routes.assessment import get_assessment_service
    from aumos_maturity_assessment.main import app

    app.dependency_overrides[get_assessment_service] = lambda: mock_assessment_service

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        yield client

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /api/v1/assessments/start
# ---------------------------------------------------------------------------


class TestStartAssessment:
    """Tests for the assessment session creation endpoint."""

    @pytest.mark.asyncio()
    async def test_start_returns_201(self, api_client: AsyncClient) -> None:
        """POST /start should return HTTP 201."""
        response = await api_client.post(
            "/api/v1/assessments/start",
            json=_START_REQUEST,
        )
        assert response.status_code == status.HTTP_201_CREATED

    @pytest.mark.asyncio()
    async def test_start_returns_session_id(self, api_client: AsyncClient) -> None:
        """Response must include a valid UUID session_id."""
        response = await api_client.post(
            "/api/v1/assessments/start",
            json=_START_REQUEST,
        )
        body = response.json()
        assert "session_id" in body
        # Validate it parses as UUID
        uuid.UUID(body["session_id"])

    @pytest.mark.asyncio()
    async def test_start_returns_50_questions(self, api_client: AsyncClient) -> None:
        """Response must include exactly 50 questions."""
        response = await api_client.post(
            "/api/v1/assessments/start",
            json=_START_REQUEST,
        )
        body = response.json()
        assert body["total_questions"] == 50
        assert len(body["questions"]) == 50

    @pytest.mark.asyncio()
    async def test_start_returns_six_dimensions(self, api_client: AsyncClient) -> None:
        """Response must list all 6 assessment dimensions."""
        response = await api_client.post(
            "/api/v1/assessments/start",
            json=_START_REQUEST,
        )
        body = response.json()
        assert len(body["dimensions"]) == 6

    @pytest.mark.asyncio()
    async def test_start_missing_industry_vertical_returns_422(
        self, api_client: AsyncClient
    ) -> None:
        """Missing required field should return HTTP 422."""
        response = await api_client.post(
            "/api/v1/assessments/start",
            json={"company_size": "enterprise"},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio()
    async def test_start_question_has_required_fields(
        self, api_client: AsyncClient
    ) -> None:
        """Each returned question must have question_id, dimension, text, weight."""
        response = await api_client.post(
            "/api/v1/assessments/start",
            json=_START_REQUEST,
        )
        body = response.json()
        for question in body["questions"]:
            assert "question_id" in question
            assert "dimension" in question
            assert "text" in question
            assert "weight" in question


# ---------------------------------------------------------------------------
# POST /api/v1/assessments/{session_id}/answer
# ---------------------------------------------------------------------------


class TestSubmitAnswer:
    """Tests for the answer submission endpoint."""

    @pytest.mark.asyncio()
    async def test_valid_answer_returns_200(
        self,
        api_client: AsyncClient,
        mock_response_repo: AsyncMock,
    ) -> None:
        """Submitting a valid answer should return HTTP 200."""
        mock_response_repo.create_response.return_value = _make_mock_response_record(
            _VALID_SESSION_ID, "DATA_01", 4
        )
        mock_response_repo.count_responses_by_session.return_value = 1

        response = await api_client.post(
            f"/api/v1/assessments/{_VALID_SESSION_ID}/answer",
            json=_ANSWER_REQUEST,
        )
        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.asyncio()
    async def test_valid_answer_response_structure(
        self,
        api_client: AsyncClient,
        mock_response_repo: AsyncMock,
    ) -> None:
        """Response must include session_id, question_id, answer_value, progress."""
        mock_response_repo.create_response.return_value = _make_mock_response_record(
            _VALID_SESSION_ID, "DATA_01", 4
        )
        mock_response_repo.count_responses_by_session.return_value = 10

        response = await api_client.post(
            f"/api/v1/assessments/{_VALID_SESSION_ID}/answer",
            json=_ANSWER_REQUEST,
        )
        body = response.json()
        assert body["session_id"] == str(_VALID_SESSION_ID)
        assert body["question_id"] == "DATA_01"
        assert body["answer_value"] == 4
        assert "progress" in body
        assert "answered_count" in body
        assert body["total_questions"] == 50

    @pytest.mark.asyncio()
    async def test_answer_value_out_of_range_returns_422(
        self, api_client: AsyncClient
    ) -> None:
        """Answer value outside 1-5 should return HTTP 422."""
        response = await api_client.post(
            f"/api/v1/assessments/{_VALID_SESSION_ID}/answer",
            json={
                "question_id": "DATA_01",
                "answer_value": 6,
                "industry_vertical": "technology",
            },
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio()
    async def test_invalid_question_id_returns_422(
        self,
        api_client: AsyncClient,
        mock_response_repo: AsyncMock,
    ) -> None:
        """Unknown question_id should return HTTP 422."""
        response = await api_client.post(
            f"/api/v1/assessments/{_VALID_SESSION_ID}/answer",
            json={
                "question_id": "INVALID_999",
                "answer_value": 3,
                "industry_vertical": "technology",
            },
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio()
    async def test_progress_calculation(
        self,
        api_client: AsyncClient,
        mock_response_repo: AsyncMock,
    ) -> None:
        """Progress should equal answered_count / 50."""
        mock_response_repo.create_response.return_value = _make_mock_response_record(
            _VALID_SESSION_ID, "GOV_01", 3
        )
        mock_response_repo.count_responses_by_session.return_value = 25

        response = await api_client.post(
            f"/api/v1/assessments/{_VALID_SESSION_ID}/answer",
            json={
                "question_id": "GOV_01",
                "answer_value": 3,
                "industry_vertical": "technology",
            },
        )
        body = response.json()
        assert abs(body["progress"] - 0.5) < 0.01  # 25/50 = 0.5


# ---------------------------------------------------------------------------
# POST /api/v1/assessments/{session_id}/complete
# ---------------------------------------------------------------------------


class TestCompleteAssessment:
    """Tests for the assessment completion endpoint."""

    def _build_all_answers(self, session_id: uuid.UUID) -> list[MagicMock]:
        """Build mock response records for all 50 questions."""
        return [
            _make_mock_response_record(session_id, q.question_id, 4)
            for q in QUESTION_BANK
        ]

    @pytest.mark.asyncio()
    async def test_complete_returns_200(
        self,
        api_client: AsyncClient,
        mock_response_repo: AsyncMock,
        mock_result_repo: AsyncMock,
        mock_benchmark_repo: AsyncMock,
    ) -> None:
        """Completing a valid session should return HTTP 200."""
        mock_result_repo.get_result_by_session.return_value = None
        mock_response_repo.get_responses_by_session.return_value = (
            self._build_all_answers(_VALID_SESSION_ID)
        )
        mock_benchmark_repo.get_benchmarks_by_industry.return_value = []
        mock_result_repo.create_result.return_value = _make_mock_result_record(
            _VALID_SESSION_ID
        )

        response = await api_client.post(
            f"/api/v1/assessments/{_VALID_SESSION_ID}/complete",
            json=_COMPLETE_REQUEST,
        )
        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.asyncio()
    async def test_complete_response_structure(
        self,
        api_client: AsyncClient,
        mock_response_repo: AsyncMock,
        mock_result_repo: AsyncMock,
        mock_benchmark_repo: AsyncMock,
    ) -> None:
        """Completion response must include all required fields."""
        mock_result_repo.get_result_by_session.return_value = None
        mock_response_repo.get_responses_by_session.return_value = (
            self._build_all_answers(_VALID_SESSION_ID)
        )
        mock_benchmark_repo.get_benchmarks_by_industry.return_value = []
        mock_result_repo.create_result.return_value = _make_mock_result_record(
            _VALID_SESSION_ID
        )

        response = await api_client.post(
            f"/api/v1/assessments/{_VALID_SESSION_ID}/complete",
            json=_COMPLETE_REQUEST,
        )
        body = response.json()

        required_keys = [
            "session_id",
            "email",
            "company_name",
            "overall_score",
            "maturity_level",
            "maturity_label",
            "dimension_scores",
            "peer_percentile",
            "roadmap_items",
            "benchmark_comparison",
            "industry_vertical",
            "completed_at",
        ]
        for key in required_keys:
            assert key in body, f"Missing key {key!r} in completion response"

    @pytest.mark.asyncio()
    async def test_complete_no_answers_returns_404(
        self,
        api_client: AsyncClient,
        mock_response_repo: AsyncMock,
        mock_result_repo: AsyncMock,
        mock_benchmark_repo: AsyncMock,
    ) -> None:
        """Completing a session with no submitted answers should return HTTP 404."""
        mock_result_repo.get_result_by_session.return_value = None
        mock_response_repo.get_responses_by_session.return_value = []
        mock_benchmark_repo.get_benchmarks_by_industry.return_value = []

        response = await api_client.post(
            f"/api/v1/assessments/{_VALID_SESSION_ID}/complete",
            json=_COMPLETE_REQUEST,
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio()
    async def test_complete_already_completed_returns_409(
        self,
        api_client: AsyncClient,
        mock_result_repo: AsyncMock,
        mock_benchmark_repo: AsyncMock,
        mock_response_repo: AsyncMock,
    ) -> None:
        """Attempting to complete an already completed session should return HTTP 409."""
        mock_result_repo.get_result_by_session.return_value = _make_mock_result_record(
            _VALID_SESSION_ID
        )

        response = await api_client.post(
            f"/api/v1/assessments/{_VALID_SESSION_ID}/complete",
            json=_COMPLETE_REQUEST,
        )
        assert response.status_code == status.HTTP_409_CONFLICT

    @pytest.mark.asyncio()
    async def test_complete_dimension_scores_all_six_dimensions(
        self,
        api_client: AsyncClient,
        mock_response_repo: AsyncMock,
        mock_result_repo: AsyncMock,
        mock_benchmark_repo: AsyncMock,
    ) -> None:
        """dimension_scores in response must include all 6 assessment dimensions."""
        mock_result_repo.get_result_by_session.return_value = None
        mock_response_repo.get_responses_by_session.return_value = (
            self._build_all_answers(_VALID_SESSION_ID)
        )
        mock_benchmark_repo.get_benchmarks_by_industry.return_value = []
        mock_result_repo.create_result.return_value = _make_mock_result_record(
            _VALID_SESSION_ID
        )

        response = await api_client.post(
            f"/api/v1/assessments/{_VALID_SESSION_ID}/complete",
            json=_COMPLETE_REQUEST,
        )
        body = response.json()
        dimension_scores = body["dimension_scores"]

        expected_dimensions = [
            "data_infrastructure",
            "governance",
            "talent_culture",
            "technology_stack",
            "security_posture",
            "strategic_alignment",
        ]
        for dimension in expected_dimensions:
            assert dimension in dimension_scores, (
                f"Dimension {dimension!r} missing from dimension_scores"
            )

    @pytest.mark.asyncio()
    async def test_complete_roadmap_items_non_empty(
        self,
        api_client: AsyncClient,
        mock_response_repo: AsyncMock,
        mock_result_repo: AsyncMock,
        mock_benchmark_repo: AsyncMock,
    ) -> None:
        """roadmap_items must be a non-empty list in the completion response."""
        mock_result_repo.get_result_by_session.return_value = None
        mock_response_repo.get_responses_by_session.return_value = (
            self._build_all_answers(_VALID_SESSION_ID)
        )
        mock_benchmark_repo.get_benchmarks_by_industry.return_value = []
        mock_result_repo.create_result.return_value = _make_mock_result_record(
            _VALID_SESSION_ID
        )

        response = await api_client.post(
            f"/api/v1/assessments/{_VALID_SESSION_ID}/complete",
            json=_COMPLETE_REQUEST,
        )
        body = response.json()
        assert isinstance(body["roadmap_items"], list)
        assert len(body["roadmap_items"]) > 0

    @pytest.mark.asyncio()
    async def test_complete_maturity_level_valid_range(
        self,
        api_client: AsyncClient,
        mock_response_repo: AsyncMock,
        mock_result_repo: AsyncMock,
        mock_benchmark_repo: AsyncMock,
    ) -> None:
        """maturity_level must be in the valid 1-5 range."""
        mock_result_repo.get_result_by_session.return_value = None
        mock_response_repo.get_responses_by_session.return_value = (
            self._build_all_answers(_VALID_SESSION_ID)
        )
        mock_benchmark_repo.get_benchmarks_by_industry.return_value = []
        mock_result_repo.create_result.return_value = _make_mock_result_record(
            _VALID_SESSION_ID
        )

        response = await api_client.post(
            f"/api/v1/assessments/{_VALID_SESSION_ID}/complete",
            json=_COMPLETE_REQUEST,
        )
        body = response.json()
        assert 1 <= body["maturity_level"] <= 5


# ---------------------------------------------------------------------------
# GET /api/v1/assessments/benchmarks/{industry_vertical}
# ---------------------------------------------------------------------------


class TestGetBenchmarks:
    """Tests for the benchmark data retrieval endpoint."""

    @pytest.mark.asyncio()
    async def test_benchmarks_returns_200(
        self,
        api_client: AsyncClient,
        mock_benchmark_repo: AsyncMock,
    ) -> None:
        """GET /benchmarks/{industry} should return HTTP 200."""
        mock_benchmark_repo.get_benchmarks_by_industry.return_value = []

        response = await api_client.get(
            "/api/v1/assessments/benchmarks/technology"
        )
        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.asyncio()
    async def test_benchmarks_returns_correct_industry(
        self,
        api_client: AsyncClient,
        mock_benchmark_repo: AsyncMock,
    ) -> None:
        """Response must echo back the requested industry_vertical."""
        mock_benchmark_repo.get_benchmarks_by_industry.return_value = []

        response = await api_client.get(
            "/api/v1/assessments/benchmarks/healthcare"
        )
        body = response.json()
        assert body["industry_vertical"] == "healthcare"

    @pytest.mark.asyncio()
    async def test_benchmarks_returns_all_dimensions(
        self,
        api_client: AsyncClient,
        mock_benchmark_repo: AsyncMock,
    ) -> None:
        """When benchmarks exist, each dimension should be represented."""
        from aumos_maturity_assessment.core.questions import ALL_DIMENSIONS

        benchmark_records = [
            _make_mock_benchmark("technology", dimension)
            for dimension in ALL_DIMENSIONS
        ]
        mock_benchmark_repo.get_benchmarks_by_industry.return_value = benchmark_records

        response = await api_client.get(
            "/api/v1/assessments/benchmarks/technology"
        )
        body = response.json()
        assert body["total"] == 6
        dimensions_in_response = {b["dimension"] for b in body["benchmarks"]}
        assert dimensions_in_response == set(ALL_DIMENSIONS)

    @pytest.mark.asyncio()
    async def test_benchmarks_empty_when_none_exist(
        self,
        api_client: AsyncClient,
        mock_benchmark_repo: AsyncMock,
    ) -> None:
        """If no benchmarks exist for the industry, return empty list with total 0."""
        mock_benchmark_repo.get_benchmarks_by_industry.return_value = []

        response = await api_client.get(
            "/api/v1/assessments/benchmarks/unknown_industry"
        )
        body = response.json()
        assert body["total"] == 0
        assert body["benchmarks"] == []

    @pytest.mark.asyncio()
    async def test_benchmark_record_has_required_fields(
        self,
        api_client: AsyncClient,
        mock_benchmark_repo: AsyncMock,
    ) -> None:
        """Each benchmark record must include all required fields."""
        mock_benchmark_repo.get_benchmarks_by_industry.return_value = [
            _make_mock_benchmark("technology", "data_infrastructure")
        ]

        response = await api_client.get(
            "/api/v1/assessments/benchmarks/technology"
        )
        body = response.json()
        record = body["benchmarks"][0]

        for field in ["id", "industry_vertical", "dimension", "p25_score",
                      "p50_score", "p75_score", "sample_size", "updated_at"]:
            assert field in record, f"Missing field {field!r} in benchmark response"
