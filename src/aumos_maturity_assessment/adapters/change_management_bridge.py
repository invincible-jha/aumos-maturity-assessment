"""Change Management integration bridge for the Maturity Assessment service.

Publishes Kafka events to trigger change management readiness assessments
when maturity gaps are detected in people or governance dimensions.

Event-driven integration — no direct HTTP dependency on aumos-change-management.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from aumos_common.events import EventPublisher, Topics
from aumos_common.observability import get_logger

logger = get_logger(__name__)


@dataclass
class ChangeManagementTriggerResult:
    """Result of a change management trigger evaluation.

    Attributes:
        triggered: Whether a change management event was published.
        reason: Human-readable explanation of the trigger decision.
        people_score: People dimension score at time of evaluation.
        governance_score: Governance dimension score at time of evaluation.
    """

    triggered: bool
    reason: str
    people_score: float
    governance_score: float


class MaturityChangeManagementBridge:
    """Publishes Kafka events triggering change management assessments.

    When maturity gaps are detected in people or governance dimensions below
    the configured threshold, this bridge publishes a Kafka event that
    aumos-change-management consumes to initiate a readiness assessment.

    Uses event-driven integration (not direct HTTP) to avoid tight coupling
    between aumos-maturity-assessment and aumos-change-management.
    """

    # Default threshold below which a change management trigger is fired
    DEFAULT_TRIGGER_THRESHOLD: float = 50.0

    def __init__(
        self,
        event_publisher: EventPublisher,
        trigger_threshold: float = DEFAULT_TRIGGER_THRESHOLD,
        integration_enabled: bool = True,
    ) -> None:
        """Initialise the change management bridge.

        Args:
            event_publisher: Kafka event publisher from aumos-common.
            trigger_threshold: Score below which a trigger is fired (0-100).
            integration_enabled: Feature flag to disable integration without code changes.
        """
        self._event_publisher = event_publisher
        self._trigger_threshold = trigger_threshold
        self._integration_enabled = integration_enabled

    async def trigger_change_management_if_needed(
        self,
        assessment_id: uuid.UUID,
        tenant_id: uuid.UUID,
        dimension_scores: dict[str, float],
    ) -> ChangeManagementTriggerResult:
        """Evaluate dimension scores and publish a trigger event if needed.

        Triggers when people_score < threshold OR governance_score < threshold.
        Publishes the event 'maturity.assessment.change_management_recommended'
        to the MATURITY_ASSESSMENT Kafka topic.

        Args:
            assessment_id: UUID of the completed assessment.
            tenant_id: Tenant UUID for scoping.
            dimension_scores: Dict mapping dimension name to score (0-100).

        Returns:
            ChangeManagementTriggerResult indicating whether an event was published.
        """
        if not self._integration_enabled:
            logger.debug(
                "change_management_integration_disabled",
                assessment_id=str(assessment_id),
            )
            return ChangeManagementTriggerResult(
                triggered=False,
                reason="Integration disabled via configuration",
                people_score=dimension_scores.get("people", 100.0),
                governance_score=dimension_scores.get("governance", 100.0),
            )

        people_score = dimension_scores.get("people", 100.0)
        governance_score = dimension_scores.get("governance", 100.0)

        should_trigger = (
            people_score < self._trigger_threshold
            or governance_score < self._trigger_threshold
        )

        if not should_trigger:
            logger.debug(
                "change_management_trigger_not_needed",
                assessment_id=str(assessment_id),
                people_score=people_score,
                governance_score=governance_score,
                threshold=self._trigger_threshold,
            )
            return ChangeManagementTriggerResult(
                triggered=False,
                reason=(
                    f"Scores above threshold: people={people_score:.1f}, "
                    f"governance={governance_score:.1f} (threshold={self._trigger_threshold})"
                ),
                people_score=people_score,
                governance_score=governance_score,
            )

        trigger_reason: dict[str, Any] = {
            "people_score": people_score,
            "governance_score": governance_score,
            "threshold": self._trigger_threshold,
            "triggered_dimensions": [],
        }
        if people_score < self._trigger_threshold:
            trigger_reason["triggered_dimensions"].append("people")
        if governance_score < self._trigger_threshold:
            trigger_reason["triggered_dimensions"].append("governance")

        await self._event_publisher.publish(
            Topics.MATURITY_ASSESSMENT,
            {
                "event_type": "maturity.assessment.change_management_recommended",
                "assessment_id": str(assessment_id),
                "tenant_id": str(tenant_id),
                "trigger_reason": trigger_reason,
            },
        )

        logger.info(
            "change_management_trigger_published",
            assessment_id=str(assessment_id),
            tenant_id=str(tenant_id),
            people_score=people_score,
            governance_score=governance_score,
            triggered_dimensions=trigger_reason["triggered_dimensions"],
        )

        return ChangeManagementTriggerResult(
            triggered=True,
            reason=(
                f"Gap detected below threshold={self._trigger_threshold}: "
                f"people={people_score:.1f}, governance={governance_score:.1f}"
            ),
            people_score=people_score,
            governance_score=governance_score,
        )
