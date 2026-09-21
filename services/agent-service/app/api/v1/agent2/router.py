"""
services/agent-service/app/api/v1/agent2/router.py
----------------------------------------------------
Agent 2 API — Problem generation.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.agents.agent2_problems import problem_agent
from app.db.session import get_db
from app.schemas.problem import ProblemAssignRequest, ProblemGenerateRequest, ProblemOut

router = APIRouter()


@router.post(
    "/problems/generate",
    response_model=list[ProblemOut],
    status_code=status.HTTP_201_CREATED,
    summary="Agent 2 — Generate problems for a student",
)
def generate_problems(
    payload: ProblemGenerateRequest, db: Session = Depends(get_db)
) -> list[ProblemOut]:
    """
    **Agent 2**: Generates easy / medium / hard problems tailored to the student's profession.
    """
    try:
        problems = problem_agent.generate_problems(db, payload)
        return [ProblemOut.model_validate(p) for p in problems]
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get(
    "/problems/student/{student_id}",
    response_model=list[ProblemOut],
    summary="Get all problems for a student",
)
def get_student_problems(student_id: uuid.UUID, db: Session = Depends(get_db)) -> list[ProblemOut]:
    problems = problem_agent.get_student_problems(db, student_id)
    return [ProblemOut.model_validate(p) for p in problems]


@router.post(
    "/problems/assign",
    response_model=ProblemOut,
    summary="Assign a specific problem to student",
)
def assign_problem(payload: ProblemAssignRequest, db: Session = Depends(get_db)) -> ProblemOut:
    problem = problem_agent.assign_problem(db, payload.problem_id, payload.student_id)
    if not problem:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Problem not found.")
    return ProblemOut.model_validate(problem)
