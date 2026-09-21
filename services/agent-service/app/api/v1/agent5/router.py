"""
services/agent-service/app/api/v1/agent5/router.py
----------------------------------------------------
Agent 5 API — Career guidance & mentoring.
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.agents.agent5_guidance import guidance_agent
from app.db.session import get_db
from app.schemas.guidance import GuidanceOut

router = APIRouter()


@router.post(
    "/guidance/{student_id}",
    response_model=GuidanceOut,
    status_code=status.HTTP_201_CREATED,
    summary="Agent 5 — Generate career guidance",
)
def generate_guidance(
    student_id: uuid.UUID,
    interview_id: Optional[uuid.UUID] = Query(default=None),
    db: Session = Depends(get_db),
) -> GuidanceOut:
    """
    **Agent 5**: Analyzes all student data (problems, evaluations, interviews)
    and generates a comprehensive career guidance report with next steps.
    """
    try:
        guidance = guidance_agent.generate_guidance(db, student_id, interview_id)
        return GuidanceOut.model_validate(guidance)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.get(
    "/guidance/{student_id}/latest",
    response_model=GuidanceOut,
    summary="Get latest guidance for a student",
)
def get_latest_guidance(student_id: uuid.UUID, db: Session = Depends(get_db)) -> GuidanceOut:
    guidance = guidance_agent.get_latest_guidance(db, student_id)
    if not guidance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No guidance found. Generate guidance first.",
        )
    return GuidanceOut.model_validate(guidance)


@router.get(
    "/guidance/{student_id}/history",
    response_model=list[GuidanceOut],
    summary="Get all guidance history for a student",
)
def get_guidance_history(student_id: uuid.UUID, db: Session = Depends(get_db)) -> list[GuidanceOut]:
    guidances = guidance_agent.get_all_guidance(db, student_id)
    return [GuidanceOut.model_validate(g) for g in guidances]
