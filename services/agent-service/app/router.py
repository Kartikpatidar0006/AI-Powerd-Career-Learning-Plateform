"""API router defining endpoints for each agent workflow."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from .dependencies import get_db
from . import crud

router = APIRouter(prefix="/agents", tags=["agents"])

class StudentInfo(BaseModel):
    name: str
    email: str
    profession: str
    # additional fields as needed

@router.post("/student", response_model=dict)
async def collect_student(info: StudentInfo, db=Depends(get_db)):
    """Agent 1 – store student info and create dashboard entry."""
    student_id = await crud.create_student(db, info)
    return {"student_id": student_id}

class ProblemRequest(BaseModel):
    student_id: int
    difficulty: str  # easy|medium|hard

@router.post("/problems", response_model=list)
async def generate_problems(req: ProblemRequest, db=Depends(get_db)):
    """Agent 2 – generate problems based on student's chosen profession."""
    return await crud.generate_problems(db, req.student_id, req.difficulty)

class EvaluationRequest(BaseModel):
    student_id: int
    github_url: str

@router.post("/evaluate", response_model=dict)
async def evaluate_task(req: EvaluationRequest, db=Depends(get_db)):
    """Agent 3 – evaluate completed task, generate interview questions."""
    result = await crud.evaluate_task(db, req.student_id, req.github_url)
    return result

@router.post("/interview", response_model=dict)
async def run_interview(student_id: int, db=Depends(get_db)):
    """Agent 4 – conduct AI interview using generated questions."""
    return await crud.run_interview(db, student_id)

@router.get("/guidance/{student_id}", response_model=dict)
async def final_guidance(student_id: int, db=Depends(get_db)):
    """Agent 5 – provide guidance and skill gap analysis."""
    return await crud.get_guidance(db, student_id)
