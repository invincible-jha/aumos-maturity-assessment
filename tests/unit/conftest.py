"""Conftest for unit tests of the AI Readiness Assessment lead magnet.

Unit tests in this sub-package are isolated from aumos_common and all
infrastructure dependencies. This conftest ensures the package path is
correct and does NOT import any aumos_common or FastAPI symbols.
"""

import sys
import types
from pathlib import Path

# Ensure the src package is on the path
_SRC_PATH = str(Path(__file__).parent.parent.parent / "src")
if _SRC_PATH not in sys.path:
    sys.path.insert(0, _SRC_PATH)

# ---------------------------------------------------------------------------
# Stub out aumos_common so it can be imported without installation
# ---------------------------------------------------------------------------

if "aumos_common" not in sys.modules:
    _aumos_common = types.ModuleType("aumos_common")
    sys.modules["aumos_common"] = _aumos_common

    for _sub in [
        "auth",
        "database",
        "events",
        "errors",
        "schemas",
        "observability",
    ]:
        _mod = types.ModuleType(f"aumos_common.{_sub}")
        sys.modules[f"aumos_common.{_sub}"] = _mod

    import logging as _logging

    def _get_logger(name: str) -> _logging.Logger:
        return _logging.getLogger(name)

    sys.modules["aumos_common.observability"].get_logger = _get_logger  # type: ignore[attr-defined]
    sys.modules["aumos_common.database"].BaseRepository = object  # type: ignore[attr-defined]
    sys.modules["aumos_common.database"].AumOSModel = object  # type: ignore[attr-defined]
    sys.modules["aumos_common.database"].get_db_session = None  # type: ignore[attr-defined]
    sys.modules["aumos_common.auth"].get_current_tenant = None  # type: ignore[attr-defined]
    sys.modules["aumos_common.auth"].get_current_user = None  # type: ignore[attr-defined]
    sys.modules["aumos_common.events"].EventPublisher = object  # type: ignore[attr-defined]
    sys.modules["aumos_common.events"].get_event_publisher = None  # type: ignore[attr-defined]
    sys.modules["aumos_common.events"].Topics = None  # type: ignore[attr-defined]
    sys.modules["aumos_common.schemas"].TenantContext = None  # type: ignore[attr-defined]
    sys.modules["aumos_common.schemas"].UserContext = None  # type: ignore[attr-defined]
    sys.modules["aumos_common.errors"].ConflictError = Exception  # type: ignore[attr-defined]
    sys.modules["aumos_common.errors"].NotFoundError = Exception  # type: ignore[attr-defined]
    sys.modules["aumos_common.errors"].ErrorCode = None  # type: ignore[attr-defined]
