"""Pydantic schemas package for the AumOS Maturity Assessment service.

Re-exports all schemas from the original flat schemas.py module for backward
compatibility with existing imports in api/router.py, and also exposes the
new lead magnet schemas from the assessment sub-module.
"""

import importlib.util
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Load original enterprise schemas from the sibling flat schemas.py file.
# ---------------------------------------------------------------------------

_FLAT_FILE = Path(__file__).parent.parent / "schemas.py"

if _FLAT_FILE.exists():
    _spec = importlib.util.spec_from_file_location(
        "aumos_maturity_assessment.api._enterprise_schemas",
        str(_FLAT_FILE),
    )
    if _spec and _spec.loader:
        _enterprise_mod = importlib.util.module_from_spec(_spec)
        sys.modules[_spec.name] = _enterprise_mod
        _spec.loader.exec_module(_enterprise_mod)  # type: ignore[attr-defined]

        # Re-export all enterprise schema classes
        AssessmentListResponse = _enterprise_mod.AssessmentListResponse
        AssessmentResponse = _enterprise_mod.AssessmentResponse
        BenchmarkCompareRequest = _enterprise_mod.BenchmarkCompareRequest
        BenchmarkCompareResponse = _enterprise_mod.BenchmarkCompareResponse
        BenchmarkListResponse = _enterprise_mod.BenchmarkListResponse
        BenchmarkResponse = _enterprise_mod.BenchmarkResponse
        CreateAssessmentRequest = _enterprise_mod.CreateAssessmentRequest
        DesignPilotRequest = _enterprise_mod.DesignPilotRequest
        DetailedScoreResponse = _enterprise_mod.DetailedScoreResponse
        DimensionWeightsRequest = _enterprise_mod.DimensionWeightsRequest
        FailureModeItem = _enterprise_mod.FailureModeItem
        GenerateReportRequest = _enterprise_mod.GenerateReportRequest
        GenerateRoadmapRequest = _enterprise_mod.GenerateRoadmapRequest
        InitiativeItem = _enterprise_mod.InitiativeItem
        LogExecutionUpdateRequest = _enterprise_mod.LogExecutionUpdateRequest
        PilotResponse = _enterprise_mod.PilotResponse
        QuestionResponseItem = _enterprise_mod.QuestionResponseItem
        QuestionResponseRecord = _enterprise_mod.QuestionResponseRecord
        ReportResponse = _enterprise_mod.ReportResponse
        RoadmapResponse = _enterprise_mod.RoadmapResponse
        SubmitResponsesRequest = _enterprise_mod.SubmitResponsesRequest
        SubmitResponsesResponse = _enterprise_mod.SubmitResponsesResponse
        SuccessCriterionItem = _enterprise_mod.SuccessCriterionItem
        UpdatePilotStatusRequest = _enterprise_mod.UpdatePilotStatusRequest
    else:
        # Fallback — all None if loading fails
        AssessmentListResponse = None  # type: ignore[assignment,misc]
        AssessmentResponse = None  # type: ignore[assignment,misc]
        BenchmarkCompareRequest = None  # type: ignore[assignment,misc]
        BenchmarkCompareResponse = None  # type: ignore[assignment,misc]
        BenchmarkListResponse = None  # type: ignore[assignment,misc]
        BenchmarkResponse = None  # type: ignore[assignment,misc]
        CreateAssessmentRequest = None  # type: ignore[assignment,misc]
        DesignPilotRequest = None  # type: ignore[assignment,misc]
        DetailedScoreResponse = None  # type: ignore[assignment,misc]
        DimensionWeightsRequest = None  # type: ignore[assignment,misc]
        FailureModeItem = None  # type: ignore[assignment,misc]
        GenerateReportRequest = None  # type: ignore[assignment,misc]
        GenerateRoadmapRequest = None  # type: ignore[assignment,misc]
        InitiativeItem = None  # type: ignore[assignment,misc]
        LogExecutionUpdateRequest = None  # type: ignore[assignment,misc]
        PilotResponse = None  # type: ignore[assignment,misc]
        QuestionResponseItem = None  # type: ignore[assignment,misc]
        QuestionResponseRecord = None  # type: ignore[assignment,misc]
        ReportResponse = None  # type: ignore[assignment,misc]
        RoadmapResponse = None  # type: ignore[assignment,misc]
        SubmitResponsesRequest = None  # type: ignore[assignment,misc]
        SubmitResponsesResponse = None  # type: ignore[assignment,misc]
        SuccessCriterionItem = None  # type: ignore[assignment,misc]
        UpdatePilotStatusRequest = None  # type: ignore[assignment,misc]
else:
    AssessmentListResponse = None  # type: ignore[assignment,misc]
    AssessmentResponse = None  # type: ignore[assignment,misc]
    BenchmarkCompareRequest = None  # type: ignore[assignment,misc]
    BenchmarkCompareResponse = None  # type: ignore[assignment,misc]
    BenchmarkListResponse = None  # type: ignore[assignment,misc]
    BenchmarkResponse = None  # type: ignore[assignment,misc]
    CreateAssessmentRequest = None  # type: ignore[assignment,misc]
    DesignPilotRequest = None  # type: ignore[assignment,misc]
    DetailedScoreResponse = None  # type: ignore[assignment,misc]
    DimensionWeightsRequest = None  # type: ignore[assignment,misc]
    FailureModeItem = None  # type: ignore[assignment,misc]
    GenerateReportRequest = None  # type: ignore[assignment,misc]
    GenerateRoadmapRequest = None  # type: ignore[assignment,misc]
    InitiativeItem = None  # type: ignore[assignment,misc]
    LogExecutionUpdateRequest = None  # type: ignore[assignment,misc]
    PilotResponse = None  # type: ignore[assignment,misc]
    QuestionResponseItem = None  # type: ignore[assignment,misc]
    QuestionResponseRecord = None  # type: ignore[assignment,misc]
    ReportResponse = None  # type: ignore[assignment,misc]
    RoadmapResponse = None  # type: ignore[assignment,misc]
    SubmitResponsesRequest = None  # type: ignore[assignment,misc]
    SubmitResponsesResponse = None  # type: ignore[assignment,misc]
    SuccessCriterionItem = None  # type: ignore[assignment,misc]
    UpdatePilotStatusRequest = None  # type: ignore[assignment,misc]

# ---------------------------------------------------------------------------
# Lead magnet schemas
# ---------------------------------------------------------------------------

from aumos_maturity_assessment.api.schemas.assessment import (  # noqa: E402
    AnswerRequest,
    AnswerResponse,
    AssessmentResultSummary,
    BenchmarkComparisonSchema,
    BenchmarkListResponse as LMBenchmarkListResponse,
    BenchmarkResponse as LMBenchmarkResponse,
    CompleteAssessmentRequest,
    CompleteAssessmentResponse,
    QuestionSchema,
    RoadmapItemSchema,
    StartAssessmentRequest,
    StartAssessmentResponse,
)

__all__ = [
    # Enterprise schemas
    "AssessmentListResponse",
    "AssessmentResponse",
    "BenchmarkCompareRequest",
    "BenchmarkCompareResponse",
    "BenchmarkListResponse",
    "BenchmarkResponse",
    "CreateAssessmentRequest",
    "DesignPilotRequest",
    "DetailedScoreResponse",
    "DimensionWeightsRequest",
    "FailureModeItem",
    "GenerateReportRequest",
    "GenerateRoadmapRequest",
    "InitiativeItem",
    "LogExecutionUpdateRequest",
    "PilotResponse",
    "QuestionResponseItem",
    "QuestionResponseRecord",
    "ReportResponse",
    "RoadmapResponse",
    "SubmitResponsesRequest",
    "SubmitResponsesResponse",
    "SuccessCriterionItem",
    "UpdatePilotStatusRequest",
    # Lead magnet schemas
    "AnswerRequest",
    "AnswerResponse",
    "AssessmentResultSummary",
    "BenchmarkComparisonSchema",
    "LMBenchmarkListResponse",
    "LMBenchmarkResponse",
    "CompleteAssessmentRequest",
    "CompleteAssessmentResponse",
    "QuestionSchema",
    "RoadmapItemSchema",
    "StartAssessmentRequest",
    "StartAssessmentResponse",
]
