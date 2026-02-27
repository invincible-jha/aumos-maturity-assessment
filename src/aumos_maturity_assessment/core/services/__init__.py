"""Services package for the AumOS Maturity Assessment service.

Re-exports enterprise services from the original flat services.py for
backward compatibility, and exposes the new lead magnet service.
"""

import importlib.util
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Load original enterprise services from the sibling flat services.py file.
# ---------------------------------------------------------------------------

_FLAT_FILE = Path(__file__).parent.parent / "services.py"

if _FLAT_FILE.exists():
    _spec = importlib.util.spec_from_file_location(
        "aumos_maturity_assessment.core._enterprise_services",
        str(_FLAT_FILE),
    )
    if _spec and _spec.loader:
        _enterprise_mod = importlib.util.module_from_spec(_spec)
        sys.modules[_spec.name] = _enterprise_mod
        _spec.loader.exec_module(_enterprise_mod)  # type: ignore[attr-defined]

        AssessmentService = _enterprise_mod.AssessmentService
        BenchmarkService = _enterprise_mod.BenchmarkService
        RoadmapService = _enterprise_mod.RoadmapService
        PilotService = _enterprise_mod.PilotService
        ReportService = _enterprise_mod.ReportService
    else:
        AssessmentService = None  # type: ignore[assignment,misc]
        BenchmarkService = None  # type: ignore[assignment,misc]
        RoadmapService = None  # type: ignore[assignment,misc]
        PilotService = None  # type: ignore[assignment,misc]
        ReportService = None  # type: ignore[assignment,misc]
else:
    AssessmentService = None  # type: ignore[assignment,misc]
    BenchmarkService = None  # type: ignore[assignment,misc]
    RoadmapService = None  # type: ignore[assignment,misc]
    PilotService = None  # type: ignore[assignment,misc]
    ReportService = None  # type: ignore[assignment,misc]

# ---------------------------------------------------------------------------
# Lead magnet service
# ---------------------------------------------------------------------------

from aumos_maturity_assessment.core.services.assessment_service import (  # noqa: E402
    AssessmentAlreadyCompletedError,
    AssessmentNotFoundError,
    AssessmentService as LeadMagnetAssessmentService,
    QuestionNotFoundError,
)

__all__ = [
    # Enterprise services (backward compat)
    "AssessmentService",
    "BenchmarkService",
    "RoadmapService",
    "PilotService",
    "ReportService",
    # Lead magnet service
    "LeadMagnetAssessmentService",
    "AssessmentNotFoundError",
    "AssessmentAlreadyCompletedError",
    "QuestionNotFoundError",
]
