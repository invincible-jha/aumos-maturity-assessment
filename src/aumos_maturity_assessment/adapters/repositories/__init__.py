"""Repository sub-package for the AumOS Maturity Assessment service.

This package provides:
- Original enterprise assessment repositories (re-exported for backward compatibility
  with existing imports in api/router.py and core/services.py)
- New self-service lead magnet repositories in assessment_repository.py

The enterprise repositories are loaded from the sibling repositories.py flat
module via importlib to avoid the directory shadowing the flat file.
"""

import importlib.util
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Load the original enterprise repositories from the sibling flat file.
# The repositories/ directory takes precedence over repositories.py in Python's
# import system, so we must load it explicitly.
# ---------------------------------------------------------------------------

_FLAT_FILE = Path(__file__).parent.parent / "repositories.py"

if _FLAT_FILE.exists():
    _spec = importlib.util.spec_from_file_location(
        "aumos_maturity_assessment.adapters._enterprise_repositories",
        str(_FLAT_FILE),
    )
    if _spec and _spec.loader:
        _enterprise_mod = importlib.util.module_from_spec(_spec)
        sys.modules[_spec.name] = _enterprise_mod
        _spec.loader.exec_module(_enterprise_mod)  # type: ignore[attr-defined]

        AssessmentRepository = _enterprise_mod.AssessmentRepository
        BenchmarkRepository = _enterprise_mod.BenchmarkRepository
        RoadmapRepository = _enterprise_mod.RoadmapRepository
        PilotRepository = _enterprise_mod.PilotRepository
        ReportRepository = _enterprise_mod.ReportRepository
        # Alias to avoid name collision with lead magnet repo of same name
        EnterpriseAssessmentResponseRepository = (
            _enterprise_mod.AssessmentResponseRepository
        )
    else:
        # Graceful fallback if loading fails — enterprise repos unavailable
        AssessmentRepository = None  # type: ignore[assignment,misc]
        BenchmarkRepository = None  # type: ignore[assignment,misc]
        RoadmapRepository = None  # type: ignore[assignment,misc]
        PilotRepository = None  # type: ignore[assignment,misc]
        ReportRepository = None  # type: ignore[assignment,misc]
        EnterpriseAssessmentResponseRepository = None  # type: ignore[assignment,misc]
else:
    AssessmentRepository = None  # type: ignore[assignment,misc]
    BenchmarkRepository = None  # type: ignore[assignment,misc]
    RoadmapRepository = None  # type: ignore[assignment,misc]
    PilotRepository = None  # type: ignore[assignment,misc]
    ReportRepository = None  # type: ignore[assignment,misc]
    EnterpriseAssessmentResponseRepository = None  # type: ignore[assignment,misc]

# ---------------------------------------------------------------------------
# Lead magnet repositories from the sub-module
# ---------------------------------------------------------------------------

from aumos_maturity_assessment.adapters.repositories.assessment_repository import (  # noqa: E402
    AssessmentBenchmarkRepository,
    AssessmentResponseRepository,
    AssessmentResultRepository,
)

__all__ = [
    # Enterprise repositories (backward compat)
    "AssessmentRepository",
    "EnterpriseAssessmentResponseRepository",
    "BenchmarkRepository",
    "PilotRepository",
    "ReportRepository",
    "RoadmapRepository",
    # Lead magnet repositories
    "AssessmentResponseRepository",
    "AssessmentResultRepository",
    "AssessmentBenchmarkRepository",
]
