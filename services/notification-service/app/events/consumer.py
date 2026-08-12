"""
services/notification-service/app/events/consumer.py
------------------------------------------------------
RabbitMQ event consumer for the Notification Service.

Listens for events published by other services:
  - task.graded       (from Learning Service)
  - interview.completed (from Interview Service)

On receiving an event, creates a Notification row in the DB
so the user can see it via GET /api/v1/notifications.

Run alongside uvicorn:
    python -m app.events.consumer
or add a second CMD / entrypoint in the Dockerfile.
In production, run as a separate Kubernetes Deployment.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from typing import Any

import pika
from pika.exceptions import AMQPConnectionError

logger = logging.getLogger(__name__)

EXCHANGE_NAME = "career_platform_events"
QUEUE_NAME = "notification-service-queue"
ROUTING_KEYS = ["task.graded", "interview.completed"]


def _get_db_session():
    """Create a database session for the consumer (runs outside FastAPI request context)."""
    from app.db.session import SessionLocal
    return SessionLocal()


def _handle_task_graded(payload: dict[str, Any]) -> None:
    """Create a notification when a task is graded."""
    from app.models.notification import Notification

    db = _get_db_session()
    try:
        user_id_str = payload.get("user_id")
        task_title = payload.get("task_title", "Your task")
        score = payload.get("score", 0)

        if not user_id_str:
            logger.warning("task.graded event missing user_id — skipping")
            return

        notification = Notification(
            id=uuid.uuid4(),
            user_id=uuid.UUID(user_id_str),
            title="Task Graded",
            message=f"Your task '{task_title}' has been graded. Score: {score}%.",
            type="Task",
            is_read=False,
        )
        db.add(notification)
        db.commit()
        logger.info("Notification created for user %s (task graded)", user_id_str)
    except Exception as exc:
        logger.error("Failed to handle task.graded: %s", exc, exc_info=True)
        db.rollback()
    finally:
        db.close()


def _handle_interview_completed(payload: dict[str, Any]) -> None:
    """Create a notification when an interview is completed."""
    from app.models.notification import Notification

    db = _get_db_session()
    try:
        user_id_str = payload.get("user_id")
        interview_id = payload.get("interview_id", "")
        overall_score = payload.get("overall_score", 0)

        if not user_id_str:
            logger.warning("interview.completed event missing user_id — skipping")
            return

        notification = Notification(
            id=uuid.uuid4(),
            user_id=uuid.UUID(user_id_str),
            title="Interview Completed",
            message=f"Your mock interview has been evaluated. Overall score: {overall_score}%.",
            type="Interview",
            is_read=False,
        )
        db.add(notification)
        db.commit()
        logger.info("Notification created for user %s (interview completed)", user_id_str)
    except Exception as exc:
        logger.error("Failed to handle interview.completed: %s", exc, exc_info=True)
        db.rollback()
    finally:
        db.close()


_HANDLERS = {
    "task.graded": _handle_task_graded,
    "interview.completed": _handle_interview_completed,
}


def _on_message(
    channel: pika.channel.Channel,
    method: pika.spec.Basic.Deliver,
    properties: pika.spec.BasicProperties,
    body: bytes,
) -> None:
    """Callback invoked for every message received from RabbitMQ."""
    try:
        message = json.loads(body.decode("utf-8"))
        event_type = message.get("event_type") or method.routing_key
        payload = message.get("payload", {})

        logger.info("Received event: %s", event_type)

        handler = _HANDLERS.get(event_type)
        if handler:
            handler(payload)
        else:
            logger.warning("No handler for event type: %s", event_type)

        channel.basic_ack(delivery_tag=method.delivery_tag)

    except json.JSONDecodeError as exc:
        logger.error("Failed to decode message body: %s", exc)
        channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    except Exception as exc:
        logger.error("Unexpected error processing message: %s", exc, exc_info=True)
        channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)


def start_consumer() -> None:
    """
    Connect to RabbitMQ and start consuming events.
    Blocks indefinitely — run in a separate process or thread.
    """
    rabbitmq_url = os.getenv("RABBITMQ_URL", "amqp://career:career@localhost:5672/")
    params = pika.URLParameters(rabbitmq_url)
    params.connection_attempts = 5
    params.retry_delay = 5

    logger.info("Notification consumer connecting to RabbitMQ...")

    try:
        connection = pika.BlockingConnection(params)
        channel = connection.channel()

        # Declare the exchange (idempotent)
        channel.exchange_declare(
            exchange=EXCHANGE_NAME,
            exchange_type="topic",
            durable=True,
        )

        # Declare a durable queue
        channel.queue_declare(queue=QUEUE_NAME, durable=True)

        # Bind the queue to the exchange for each routing key we care about
        for routing_key in ROUTING_KEYS:
            channel.queue_bind(
                exchange=EXCHANGE_NAME,
                queue=QUEUE_NAME,
                routing_key=routing_key,
            )

        # Only process one message at a time
        channel.basic_qos(prefetch_count=1)
        channel.basic_consume(queue=QUEUE_NAME, on_message_callback=_on_message)

        logger.info(
            "Notification consumer started. Listening for: %s",
            ", ".join(ROUTING_KEYS),
        )
        channel.start_consuming()

    except AMQPConnectionError as exc:
        logger.error("Cannot connect to RabbitMQ: %s", exc)
        raise
    except KeyboardInterrupt:
        logger.info("Notification consumer stopped by KeyboardInterrupt.")
        if "channel" in dir():
            channel.stop_consuming()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
    )
    start_consumer()
