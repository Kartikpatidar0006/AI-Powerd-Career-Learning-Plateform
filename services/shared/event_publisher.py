"""
services/shared/event_publisher.py
------------------------------------
RabbitMQ event publisher utility.

Usage (in Learning Service after a task is graded):

    from app.events.event_publisher import publish_event

    publish_event(
        event_type="task.graded",
        payload={
            "user_id": str(user_id),
            "task_id": str(task_id),
            "task_title": task.title,
            "score": score,
        }
    )

Events are published to the `career_platform` topic exchange with
the routing key equal to the event_type.

The Notification Service subscribes to:
  - task.graded
  - interview.completed

This module is copied into each service that needs to publish events.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

import pika
from pika.exceptions import AMQPConnectionError

logger = logging.getLogger(__name__)

# Exchange name (topic exchange — routing key = event type)
EXCHANGE_NAME = "career_platform_events"


def _get_connection() -> pika.BlockingConnection:
    """Create a RabbitMQ connection from the RABBITMQ_URL environment variable."""
    rabbitmq_url = os.getenv("RABBITMQ_URL", "amqp://career:career@localhost:5672/")
    params = pika.URLParameters(rabbitmq_url)
    params.connection_attempts = 3
    params.retry_delay = 2
    return pika.BlockingConnection(params)


def publish_event(event_type: str, payload: dict[str, Any]) -> bool:
    """
    Publish an event to RabbitMQ.

    Args:
        event_type: Routing key, e.g. "task.graded", "interview.completed".
        payload: Event data dictionary. Will be JSON-serialised.

    Returns:
        True on success, False on failure (non-blocking — caller continues).
    """
    message = {
        "event_type": event_type,
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "payload": payload,
    }

    try:
        connection = _get_connection()
        channel = connection.channel()

        # Declare the topic exchange (idempotent — safe to call every time)
        channel.exchange_declare(
            exchange=EXCHANGE_NAME,
            exchange_type="topic",
            durable=True,
        )

        channel.basic_publish(
            exchange=EXCHANGE_NAME,
            routing_key=event_type,
            body=json.dumps(message),
            properties=pika.BasicProperties(
                delivery_mode=pika.DeliveryMode.Persistent,  # survive broker restart
                content_type="application/json",
            ),
        )

        connection.close()
        logger.info("Event published: %s", event_type)
        return True

    except AMQPConnectionError as exc:
        logger.error(
            "Failed to publish event '%s' — RabbitMQ unavailable: %s",
            event_type,
            exc,
        )
        return False
    except Exception as exc:
        logger.error("Unexpected error publishing event '%s': %s", event_type, exc)
        return False
