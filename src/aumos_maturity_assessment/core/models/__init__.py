"""ORM models package for the AumOS Maturity Assessment service.

Exports:
- Original enterprise assessment models (Assessment, AssessmentResponse,
  Benchmark, Roadmap, Pilot, Report) for backward compatibility
- Lead magnet models (LMAssessmentResponse, LMAssessmentResult,
  LMAssessmentBenchmark) for the self-service assessment flow
"""

import importlib.util
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Load original enterprise models from the sibling flat models.py file.
# The models/ directory takes precedence over models.py in Python's import
# system, so we must load the flat file explicitly.
# ---------------------------------------------------------------------------

_FLAT_FILE = Path(__file__).parent.parent / "models.py"

if _FLAT_FILE.exists():
    _spec = importlib.util.spec_from_file_location(
        "aumos_maturity_assessment.core._enterprise_models",
        str(_FLAT_FILE),
    )
    if _spec and _spec.loader:
        _enterprise_mod = importlib.util.module_from_spec(_spec)
        sys.modules[_spec.name] = _enterprise_mod
        _spec.loader.exec_module(_enterprise_mod)  # type: ignore[attr-defined]

        # Re-export enterprise model classes
        Assessment = _enterprise_mod.Assessment
        AssessmentResponse = _enterprise_mod.AssessmentResponse
        Benchmark = _enterprise_mod.Benchmark
        Roadmap = _enterprise_mod.Roadmap
        Pilot = _enterprise_mod.Pilot
        Report = _enterprise_mod.Report
    else:
        Assessment = None  # type: ignore[assignment,misc]
        AssessmentResponse = None  # type: ignore[assignment,misc]
        Benchmark = None  # type: ignore[assignment,misc]
        Roadmap = None  # type: ignore[assignment,misc]
        Pilot = None  # type: ignore[assignment,misc]
        Report = None  # type: ignore[assignment,misc]
else:
    Assessment = None  # type: ignore[assignment,misc]
    AssessmentResponse = None  # type: ignore[assignment,misc]
    Benchmark = None  # type: ignore[assignment,misc]
    Roadmap = None  # type: ignore[assignment,misc]
    Pilot = None  # type: ignore[assignment,misc]
    Report = None  # type: ignore[assignment,misc]

# ---------------------------------------------------------------------------
# Lead magnet ORM models
# ---------------------------------------------------------------------------

from aumos_maturity_assessment.core.models.assessment import (  # noqa: E402
    LMAssessmentBenchmark,
    LMAssessmentResponse,
    LMAssessmentResult,
    LeadMagnetBase,
)

__all__ = [
    # Enterprise models (backward compat)
    "Assessment",
    "AssessmentResponse",
    "Benchmark",
    "Roadmap",
    "Pilot",
    "Report",
    # Lead magnet models
    "LeadMagnetBase",
    "LMAssessmentResponse",
    "LMAssessmentResult",
    "LMAssessmentBenchmark",
]
