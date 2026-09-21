"""
services/agent-service/app/api/v1/agent3/router.py
----------------------------------------------------
Agent 3 API — GitHub evaluation & interview question generation.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.agents.agent3_evaluation import evaluation_agent
from app.db.session import get_db
from app.schemas.evaluation import EvaluationOut, EvaluationRequest

router = APIRouter()


@router.post(
    "/evaluations",
    response_model=EvaluationOut,
    status_code=status.HTTP_201_CREATED,
    summary="Agent 3 — Evaluate GitHub submission",
)
def evaluate_submission(
    payload: EvaluationRequest, db: Session = Depends(get_db)
) -> EvaluationOut:
    """
    **Agent 3**: Evaluates a student's GitHub repo and generates 8-15 interview questions.
    This is an async-like operation — may take 10-30s depending on repo size.
    """
    try:
        evaluation = evaluation_agent.evaluate(db, payload)
        return EvaluationOut.model_validate(evaluation)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.get(
    "/evaluations/{evaluation_id}",
    response_model=EvaluationOut,
    summary="Get evaluation result",
)
def get_evaluation(evaluation_id: uuid.UUID, db: Session = Depends(get_db)) -> EvaluationOut:
    evaluation = evaluation_agent.get_evaluation(db, evaluation_id)
    if not evaluation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation not found.")
    return EvaluationOut.model_validate(evaluation)


@router.get(
    "/evaluations/student/{student_id}",
    response_model=list[EvaluationOut],
    summary="Get all evaluations for a student",
)
def get_student_evaluations(
    student_id: uuid.UUID, db: Session = Depends(get_db)
) -> list[EvaluationOut]:
    evaluations = evaluation_agent.get_student_evaluations(db, student_id)
    return [EvaluationOut.model_validate(e) for e in evaluations]
