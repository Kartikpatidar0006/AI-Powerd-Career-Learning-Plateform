"""
backend/app/models/notification.py
----------------------------------
ORM model for the ``notifications`` table.

Table overview
--------------
``notifications``
    Stores platform notifications for learners, including task updates,
    interview alerts, progress milestones, and reminders.

Columns
-------
id          UUID PK — Python-generated (uuid4).
user_id     UUID FK → users.id NOT NULL — recipient user.
title       VARCHAR(255) NOT NULL — notification title.
message     TEXT NOT NULL — detailed notification message.
type        VARCHAR(30) NOT NULL DEFAULT 'Task' — Enum: 'Task', 'Interview', 'Progress', 'Reminder'.
is_read     BOOLEAN NOT NULL DEFAULT false — read flag.
created_at  TIMESTAMPTZ NOT NULL — creation timestamp.

Relationships
-------------
notification.user → User (many-to-one, unidirectional)

Registration
------------
Add the following line in ``app/db/base.py``::

    from app.models.notification import Notification  # noqa: F401
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User  # noqa: F401


class Notification(Base):
    """SQLAlchemy 2.x ORM model for the ``notifications`` table.

    Represents a notification event sent to a learner.

    Attributes:
        id: UUID primary key.
        user_id: FK to recipient ``User``.
        title: Short title summary.
        message: Detailed notification content.
        type: 'Task', 'Interview', 'Progress', or 'Reminder'.
        is_read: ``True`` if read by the user.
        created_at: Creation timestamp.
        user: ORM relationship to ``User``.
    """

    __tablename__ = "notifications"

    # ── Primary key ──────────────────────────────────────────────────────── #
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
        comment="Surrogate primary key — UUID v4.",
    )

    # ── Foreign key — User ───────────────────────────────────────────────── #
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="FK → users.id. Deleted when user is deleted.",
    )

    # ── Content fields ───────────────────────────────────────────────────── #
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Notification headline / title.",
    )

    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Detailed notification text.",
    )

    type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
        default="Task",
        server_default="Task",
        comment="Notification category: 'Task', 'Interview', 'Progress', or 'Reminder'.",
    )

    is_read: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        index=True,
        comment="True if learner has marked this notification as read.",
    )

    # ── Timestamps ───────────────────────────────────────────────────────── #
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="UTC timestamp of creation.",
    )

    # ── Relationships ─────────────────────────────────────────────────────── #
    user: Mapped["User"] = relationship(  # type: ignore[name-defined]
        "User",
        lazy="select",
    )

    def __repr__(self) -> str:
        return (
            f"Notification("
            f"id={self.id!r}, "
            f"user_id={self.user_id!r}, "
            f"type={self.type!r}, "
            f"is_read={self.is_read!r}"
            f")"
        )
