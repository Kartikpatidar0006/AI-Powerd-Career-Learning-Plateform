"""
backend/app/schemas/notification.py
====================================
Pydantic v2 schemas for the Notification System feature.

This module defines request and response schemas for user notifications:

  NotificationType         — Enum: 'Task' | 'Interview' | 'Progress' | 'Reminder'.
  NotificationResponse     — Single notification representation.
  NotificationListResponse — Paginated list of notifications with unread count.

Design notes:
  - ``ConfigDict(from_attributes=True)`` enables ORM → Pydantic conversion.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class NotificationType(str, Enum):
    """Allowed notification categories."""

    TASK = "Task"
    INTERVIEW = "Interview"
    PROGRESS = "Progress"
    REMINDER = "Reminder"


class NotificationResponse(BaseModel):
    """API response schema representing a single notification.

    Attributes:
        id: UUID primary key.
        user_id: UUID of recipient user.
        title: Notification headline.
        message: Detailed notification content.
        type: Notification type ('Task', 'Interview', 'Progress', 'Reminder').
        is_read: True if read.
        created_at: Creation timestamp.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    message: str
    type: str
    is_read: bool
    created_at: datetime


class NotificationListResponse(BaseModel):
    """Paginated list of notifications.

    Attributes:
        items: List of ``NotificationResponse`` objects.
        total: Total notification count.
        unread_count: Total unread notification count.
        skip: Pagination offset.
        limit: Maximum results returned.
    """

    items: list[NotificationResponse]
    total: int
    unread_count: int
    skip: int
    limit: int
