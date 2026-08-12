"""
services/dashboard-bff/app/services/dashboard.py
--------------------------------------------------
Dashboard aggregation service — rewritten for microservices.

Instead of querying the monolith's single DB, this service
makes HTTP calls to the appropriate downstream services using httpx.

The async aggregation calls all services in parallel using asyncio.gather
for minimal latency.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class DashboardAggregatorService:
    """
    Aggregates data from multiple microservices to produce the
    student dashboard payload.

    All downstream calls use the Authorization header forwarded from the
    original request so services can apply their own auth checks.
    """

    def __init__(self, auth_header: str, user_id: uuid.UUID) -> None:
        self._auth_header = auth_header
        self._user_id = str(user_id)
        self._headers = {
            "Authorization": auth_header,
            "Content-Type": "application/json",
        }

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT, headers=self._headers)

    async def _safe_get(self, client: httpx.AsyncClient, url: str) -> Any:
        """Make a GET request; return None on any error."""
        try:
            resp = await client.get(url)
            if resp.status_code == 200:
                return resp.json()
            logger.warning("GET %s → %d", url, resp.status_code)
            return None
        except Exception as exc:
            logger.error("Failed GET %s: %s", url, exc)
            return None

    async def get_student_dashboard(self) -> dict[str, Any]:
        """
        Aggregate all dashboard data in parallel.

        Returns a dict matching the StudentDashboardResponse schema.
        """
        uid = self._user_id
        prefix = settings.API_V1_STR

        auth_url   = settings.AUTH_SERVICE_URL
        cat_url    = settings.CATALOG_SERVICE_URL
        learn_url  = settings.LEARNING_SERVICE_URL
        inter_url  = settings.INTERVIEW_SERVICE_URL
        prog_url   = settings.PROGRESS_SERVICE_URL
        notif_url  = settings.NOTIFICATION_SERVICE_URL

        async with self._client() as client:
            (
                user_data,
                progress_data,
                notifications_data,
                interviews_data,
            ) = await asyncio.gather(
                self._safe_get(client, f"{auth_url}{prefix}/users/{uid}"),
                self._safe_get(client, f"{prog_url}{prefix}/user-progress/me"),
                self._safe_get(client, f"{notif_url}{prefix}/notifications?limit=1"),
                self._safe_get(client, f"{inter_url}{prefix}/interviews/me?limit=1&status=Scheduled"),
            )

        # Fetch profession if we have a profession_id from user data
        profession_data = None
        roadmap_data = None
        if user_data:
            profession_id = user_data.get("profession_id")
            if profession_id:
                async with self._client() as client:
                    (profession_data, roadmap_data) = await asyncio.gather(
                        self._safe_get(client, f"{cat_url}{prefix}/professions/{profession_id}"),
                        self._safe_get(client, f"{cat_url}{prefix}/career-roadmaps?profession_id={profession_id}&is_active=true&limit=1"),
                    )

        # Unread notification count
        unread_count = 0
        if notifications_data:
            meta = notifications_data.get("meta") or notifications_data
            unread_count = meta.get("unread_count", 0)

        # Upcoming interview
        upcoming_interview = None
        if interviews_data:
            items = interviews_data.get("items") or interviews_data
            if isinstance(items, list) and items:
                upcoming_interview = items[0]

        # Active roadmap
        active_roadmap = None
        if roadmap_data:
            items = roadmap_data.get("items") or roadmap_data
            if isinstance(items, list) and items:
                active_roadmap = items[0]

        return {
            "user": user_data,
            "profession": profession_data,
            "roadmap": active_roadmap,
            "current_task": None,           # Phase 2: query learning-service for active task
            "latest_task_feedback": None,   # Phase 2: query learning-service
            "upcoming_interview": upcoming_interview,
            "latest_interview_feedback": None,  # Phase 2: query interview-service
            "progress": progress_data,
            "unread_notification_count": unread_count,
        }
