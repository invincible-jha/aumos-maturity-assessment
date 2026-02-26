"""Test fixtures for aumos-maturity-assessment.

Imports shared fixtures from aumos_common.testing and adds
maturity-assessment-specific factories and overrides.
"""

import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from aumos_common.auth import get_current_tenant, get_current_user
from aumos_common.events import EventPublisher

from aumos_maturity_assessment.main import app


# ---------------------------------------------------------------------------
# Auth overrides
# ---------------------------------------------------------------------------


@pytest.fixture()
def tenant_id() -> uuid.UUID:
    """Fixed tenant UUID for tests."""
    return uuid.UUID("11111111-1111-1111-1111-111111111111")


@pytest.fixture()
def user_id() -> uuid.UUID:
    """Fixed user UUID for tests."""
    return uuid.UUID("22222222-2222-2222-2222-222222222222")


@pytest.fixture()
def mock_tenant(tenant_id: uuid.UUID) -> MagicMock:
    """Mock TenantContext."""
    tenant = MagicMock()
    tenant.tenant_id = tenant_id
    return tenant


@pytest.fixture()
def mock_user(user_id: uuid.UUID) -> MagicMock:
    """Mock UserContext."""
    user = MagicMock()
    user.user_id = user_id
    return user


@pytest.fixture()
def mock_publisher() -> AsyncMock:
    """Mock EventPublisher."""
    publisher = AsyncMock(spec=EventPublisher)
    return publisher


@pytest_asyncio.fixture()
async def client(
    mock_tenant: MagicMock,
    mock_user: MagicMock,
) -> AsyncGenerator[AsyncClient, None]:
    """Async test client with auth dependencies overridden."""
    app.dependency_overrides[get_current_tenant] = lambda: mock_tenant
    app.dependency_overrides[get_current_user] = lambda: mock_user

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as test_client:
        yield test_client

    app.dependency_overrides.clear()
