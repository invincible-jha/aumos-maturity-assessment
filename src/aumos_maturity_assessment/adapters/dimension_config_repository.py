"""Repository for MatDimensionConfig — configurable assessment dimension persistence.

Provides CRUD operations for the mat_dimension_configs table, which stores
all assessment dimensions (including the new agentic_ai dimension) in the
database rather than hardcoded constants.
"""

from __future__ import annotations

import uuid
from typing import Any

from aumos_common.observability import get_logger

logger = get_logger(__name__)


class DimensionConfigRepository:
    """SQLAlchemy repository for MatDimensionConfig entities.

    Loads active dimension configurations from the database, enabling
    the assessment system to support new dimensions without code changes.
    """

    def __init__(self, session: Any) -> None:
        """Initialise with an async SQLAlchemy session.

        Args:
            session: AsyncSession for database access.
        """
        self._session = session

    async def get_active_dimensions(self) -> list[dict[str, Any]]:
        """Return all active dimension configurations ordered by default_weight descending.

        Returns:
            List of dimension config dicts with id, display_name, description,
            default_weight, question_bank, introduced_in_version, framework_alignment.
        """
        from sqlalchemy import text

        result = await self._session.execute(
            text(
                """
                SELECT id, display_name, description, default_weight,
                       question_bank, introduced_in_version, framework_alignment
                FROM mat_dimension_configs
                WHERE is_active = TRUE
                ORDER BY default_weight DESC
                """
            )
        )
        rows = result.fetchall()
        return [
            {
                "id": row[0],
                "display_name": row[1],
                "description": row[2],
                "default_weight": row[3],
                "question_bank": row[4],
                "introduced_in_version": row[5],
                "framework_alignment": row[6],
            }
            for row in rows
        ]

    async def get_by_ids(self, dimension_ids: list[str]) -> list[dict[str, Any]]:
        """Return dimension configs for the specified dimension IDs.

        Args:
            dimension_ids: List of dimension ID strings to retrieve.

        Returns:
            List of dimension config dicts for the requested IDs (active only).
        """
        from sqlalchemy import text

        if not dimension_ids:
            return []

        placeholders = ", ".join(f":id_{i}" for i in range(len(dimension_ids)))
        params = {f"id_{i}": dim_id for i, dim_id in enumerate(dimension_ids)}

        result = await self._session.execute(
            text(
                f"""
                SELECT id, display_name, description, default_weight,
                       question_bank, introduced_in_version, framework_alignment
                FROM mat_dimension_configs
                WHERE id IN ({placeholders}) AND is_active = TRUE
                ORDER BY default_weight DESC
                """
            ),
            params,
        )
        rows = result.fetchall()
        return [
            {
                "id": row[0],
                "display_name": row[1],
                "description": row[2],
                "default_weight": row[3],
                "question_bank": row[4],
                "introduced_in_version": row[5],
                "framework_alignment": row[6],
            }
            for row in rows
        ]
