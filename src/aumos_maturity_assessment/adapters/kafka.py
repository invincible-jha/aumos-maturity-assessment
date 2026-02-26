"""Kafka event publishing for the AumOS Maturity Assessment service.

Wraps the aumos-common EventPublisher to provide maturity-specific
topic routing and event schema enforcement.
"""

from typing import Any

from aumos_common.events import EventPublisher, Topics
from aumos_common.observability import get_logger

logger = get_logger(__name__)


class MaturityEventPublisher:
    """Thin wrapper around aumos-common EventPublisher for maturity events.

    Routes maturity-specific events to the appropriate Kafka topics defined
    in aumos-common Topics. Delegates all actual publishing to the base publisher.
    """

    def __init__(self, publisher: EventPublisher) -> None:
        """Initialise with the aumos-common event publisher.

        Args:
            publisher: Configured aumos-common EventPublisher instance.
        """
        self._publisher = publisher

    async def publish(
        self,
        topic: str,
        event: dict[str, Any],
    ) -> None:
        """Publish an event to the specified topic.

        Delegates to the underlying aumos-common EventPublisher which
        handles serialization, correlation IDs, and delivery guarantees.

        Args:
            topic: Kafka topic name (use Topics.* constants).
            event: Event payload dict (must include tenant_id and event_type).
        """
        await self._publisher.publish(topic, event)

        logger.debug(
            "Maturity event published",
            topic=topic,
            event_type=event.get("event_type"),
            tenant_id=event.get("tenant_id"),
        )
