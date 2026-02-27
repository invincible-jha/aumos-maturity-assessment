"""Root conftest.py — ensures aumos_common stub is loaded before any test conftest.

This file is loaded by pytest before tests/conftest.py. It stubs out
aumos_common so that unit tests can run without the full package installed.
In the CI/CD environment where aumos_common IS installed, this stub is
ignored because aumos_common will already be in sys.modules.
"""

import logging as _logging
import sys
import types
import uuid as _uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

# Ensure src is on the path for all tests
_SRC_PATH = str(Path(__file__).parent / "src")
if _SRC_PATH not in sys.path:
    sys.path.insert(0, _SRC_PATH)


def _make_package(name: str) -> types.ModuleType:
    """Create a stub package module that Python treats as a package.

    Args:
        name: Fully-qualified module name (e.g., 'aumos_common').

    Returns:
        Module set up as a package with __path__ and __package__.
    """
    mod = types.ModuleType(name)
    mod.__path__ = []  # type: ignore[attr-defined]
    mod.__package__ = name
    sys.modules[name] = mod
    return mod


# Only stub if aumos_common is not already installed as a real package
try:
    import aumos_common as _existing  # type: ignore[import]

    # Real package is installed — no stubbing needed
except ImportError:
    # Build a complete stub of aumos_common

    # Root package
    _aumos_common = _make_package("aumos_common")

    # All sub-packages and modules we need to stub
    _sub_names = [
        "app",
        "auth",
        "config",
        "database",
        "errors",
        "events",
        "observability",
        "schemas",
    ]

    for _sub in _sub_names:
        _make_package(f"aumos_common.{_sub}")

    # -----------------------------------------------------------------------
    # aumos_common.observability
    # -----------------------------------------------------------------------
    def _get_logger(name: str) -> _logging.Logger:
        return _logging.getLogger(name)

    sys.modules["aumos_common.observability"].get_logger = _get_logger  # type: ignore[attr-defined]

    # -----------------------------------------------------------------------
    # aumos_common.database
    # -----------------------------------------------------------------------
    class _BaseRepository:
        def __init__(self, session: object, model: object) -> None:
            self.session = session
            self.model = model

    class _AumOSModel:
        pass

    sys.modules["aumos_common.database"].BaseRepository = _BaseRepository  # type: ignore[attr-defined]
    sys.modules["aumos_common.database"].AumOSModel = _AumOSModel  # type: ignore[attr-defined]
    sys.modules["aumos_common.database"].get_db_session = MagicMock()  # type: ignore[attr-defined]
    sys.modules["aumos_common.database"].init_database = MagicMock()  # type: ignore[attr-defined]

    # -----------------------------------------------------------------------
    # aumos_common.auth
    # -----------------------------------------------------------------------
    _mock_tenant = MagicMock()
    _mock_tenant.tenant_id = _uuid.uuid4()
    _mock_user = MagicMock()
    _mock_user.user_id = _uuid.uuid4()

    sys.modules["aumos_common.auth"].get_current_tenant = MagicMock(return_value=_mock_tenant)  # type: ignore[attr-defined]
    sys.modules["aumos_common.auth"].get_current_user = MagicMock(return_value=_mock_user)  # type: ignore[attr-defined]

    # -----------------------------------------------------------------------
    # aumos_common.events
    # -----------------------------------------------------------------------
    sys.modules["aumos_common.events"].EventPublisher = MagicMock  # type: ignore[attr-defined]
    sys.modules["aumos_common.events"].get_event_publisher = MagicMock()  # type: ignore[attr-defined]
    sys.modules["aumos_common.events"].Topics = MagicMock()  # type: ignore[attr-defined]

    # -----------------------------------------------------------------------
    # aumos_common.schemas
    # -----------------------------------------------------------------------
    sys.modules["aumos_common.schemas"].TenantContext = MagicMock  # type: ignore[attr-defined]
    sys.modules["aumos_common.schemas"].UserContext = MagicMock  # type: ignore[attr-defined]

    # -----------------------------------------------------------------------
    # aumos_common.errors
    # -----------------------------------------------------------------------
    class _NotFoundError(Exception):
        pass

    class _ConflictError(Exception):
        pass

    sys.modules["aumos_common.errors"].ConflictError = _ConflictError  # type: ignore[attr-defined]
    sys.modules["aumos_common.errors"].NotFoundError = _NotFoundError  # type: ignore[attr-defined]
    sys.modules["aumos_common.errors"].ErrorCode = MagicMock()  # type: ignore[attr-defined]

    # -----------------------------------------------------------------------
    # aumos_common.config
    # -----------------------------------------------------------------------
    class _AumOSSettings:
        service_name: str = "aumos-test"
        database: object = MagicMock()

    sys.modules["aumos_common.config"].AumOSSettings = _AumOSSettings  # type: ignore[attr-defined]

    # -----------------------------------------------------------------------
    # aumos_common.app
    # -----------------------------------------------------------------------
    def _create_app(
        service_name: str,
        version: str,
        settings: object,
        lifespan: object = None,
        health_checks: list = None,
    ) -> object:
        """Stub create_app returning a real FastAPI instance."""
        from fastapi import FastAPI

        return FastAPI(title=service_name, version=version, lifespan=lifespan)

    sys.modules["aumos_common.app"].create_app = _create_app  # type: ignore[attr-defined]

    # -----------------------------------------------------------------------
    # aumos_proto (Kafka protobuf definitions)
    # -----------------------------------------------------------------------
    _aumos_proto = _make_package("aumos_proto")
