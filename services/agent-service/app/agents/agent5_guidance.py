"""
services/agent-service/app/agents/agent5_guidance.py
------------------------------------------------------
Agent 5: Final career guidance & mentoring agent.
- Synthesizes all data: problems solved, evaluation scores, interview performance
- Identifies strengths and weak areas
- Provides detailed, personalized next-steps roadmap
- Recommends specific learning resources
"""
from __future__ import annotations

import json
import logging
import uuid

from sqlalchemy.orm import Session

from app.agents.llm_client import chat_complete, parse_json_response
from app.models.evaluation import Evaluation
from app.models.guidance import Guidance
from app.models.interview import Interview
from app.models.problem import Problem
from app.models.student import Student
from app.schemas.guidance import GuidanceOut

logger = logging.getLogger(__name__)

GUIDANCE_SYSTEM_PROMPT = """You are an expert career mentor and coach with 15+ years 
of experience in the tech industry. You have deep knowledge of career development,
technical skills, and the software engineering job market.

Your role is to provide actionable, personalized career guidance based on a student's
performance data. Be encouraging, specific, and realistic.

Return ONLY valid JSON. No markdown or extra text.
"""


def _build_guidance_prompt(
    student: Student,
    problems: list[Problem],
    evaluations: list[Evaluation],
    interviews: list[Interview],
) -> str:
    # Summarize evaluation performance
    eval_summary = []
    for ev in evaluations:
        eval_summary.append({
            "github_url": ev.github_url,
            "overall_score": ev.overall_score,
            "code_quality_score": ev.code_quality_score,
            "documentation_score": ev.documentation_score,
        })

    # Summarize interview performance
    interview_summary = []
    for iv in interviews:
        interview_summary.append({
            "overall_score": iv.overall_score,
            "technical_score": iv.technical_score,
            "communication_score": iv.communication_score,
            "status": iv.status,
        })

    return f"""
Provide detailed career guidance for this student:

STUDENT PROFILE:
- Name: {student.full_name}
- Profession goal: {student.profession}
- Experience level: {student.experience_level}
- Goals: {student.goals}
- Preferred stack: {student.preferred_stack}
- Weekly study hours: {student.weekly_hours}

PERFORMANCE DATA:
- Problems assigned: {len(problems)}
- Evaluations completed: {len([e for e in evaluations if e.status == "completed"])}
- Average evaluation score: {sum(e.overall_score for e in evaluations) / len(evaluations) if evaluations else 0:.1f}
- Interviews completed: {len([i for i in interviews if i.status == "completed"])}
- Average interview score: {sum(i.overall_score for i in interviews) / len(interviews) if interviews else 0:.1f}

EVALUATION DETAILS:
{json.dumps(eval_summary, indent=2)}

INTERVIEW DETAILS:
{json.dumps(interview_summary, indent=2)}

Return a JSON object:
{{
  "readiness_score": 0-100 (overall career readiness),
  "summary": "2-3 paragraph personalized summary",
  "strengths": ["strength 1", "strength 2", "strength 3"],
  "weak_areas": ["weak area 1", "weak area 2", "weak area 3"],
  "next_steps": [
    "Specific action 1 with timeline",
    "Specific action 2 with timeline",
    "Specific action 3 with timeline"
  ],
  "recommended_resources": [
    "Resource name: URL or platform",
    "Resource name: URL or platform"
  ],
  "career_path_advice": "Detailed paragraph about career path forward"
}}
"""


class GuidanceAgent:
    """Agent 5 — generates comprehensive career guidance based on all student data."""

    def generate_guidance(
        self, db: Session, student_id: uuid.UUID, interview_id: uuid.UUID | None = None
    ) -> Guidance:
        student = db.query(Student).filter(Student.id == student_id).first()
        if not student:
            raise ValueError(f"Student {student_id} not found.")

        problems = db.query(Problem).filter(Problem.student_id == student_id).all()
        evaluations = db.query(Evaluation).filter(Evaluation.student_id == student_id).all()
        interviews = db.query(Interview).filter(Interview.student_id == student_id).all()

        logger.info(
            "Generating guidance for student %s: %d problems, %d evals, %d interviews",
            student.email, len(problems), len(evaluations), len(interviews)
        )

        prompt = _build_guidance_prompt(student, problems, evaluations, interviews)
        raw = chat_complete(GUIDANCE_SYSTEM_PROMPT, prompt)
        data = parse_json_response(raw)

        if isinstance(data, dict) and "mock" in data:
            data = _mock_guidance(student.profession)

        guidance = Guidance(
            student_id=student_id,
            interview_id=interview_id,
            readiness_score=int(data.get("readiness_score", 0)),
            summary=data.get("summary"),
            strengths=json.dumps(data.get("strengths", [])),
            weak_areas=json.dumps(data.get("weak_areas", [])),
            next_steps=json.dumps(data.get("next_steps", [])),
            recommended_resources=json.dumps(data.get("recommended_resources", [])),
            career_path_advice=data.get("career_path_advice"),
        )
        db.add(guidance)
        db.commit()
        db.refresh(guidance)

        logger.info("Guidance generated for student %s. Readiness score: %d",
                    student.email, guidance.readiness_score)
        return guidance

    def get_latest_guidance(self, db: Session, student_id: uuid.UUID) -> Guidance | None:
        return (
            db.query(Guidance)
            .filter(Guidance.student_id == student_id)
            .order_by(Guidance.created_at.desc())
            .first()
        )

    def get_all_guidance(self, db: Session, student_id: uuid.UUID) -> list[Guidance]:
        return (
            db.query(Guidance)
            .filter(Guidance.student_id == student_id)
            .order_by(Guidance.created_at.desc())
            .all()
        )


def _mock_guidance(profession: str) -> dict:
    return {
        "readiness_score": 68,
        "summary": (
            f"You are making solid progress on your journey to becoming a {profession}. "
            "Your project submissions show a good grasp of fundamentals and enthusiasm for learning. "
            "With focused effort on the identified weak areas, you will be job-ready within 3-4 months."
        ),
        "strengths": [
            "Strong problem-solving approach",
            "Good project structure and organization",
            "Consistent commit history demonstrating work ethic",
        ],
        "weak_areas": [
            "Test coverage needs improvement (aim for >70%)",
            "API error handling is inconsistent",
            "Documentation could be more detailed",
        ],
        "next_steps": [
            "Week 1-2: Complete the TDD Fundamentals course on freeCodeCamp",
            "Week 3-4: Add 80%+ test coverage to your last submitted project",
            "Month 2: Build one more medium-difficulty project focusing on scalability",
            "Month 3: Prepare resume and start applying to junior positions",
        ],
        "recommended_resources": [
            "The Odin Project — Full Stack path: https://www.theodinproject.com",
            "Clean Code by Robert C. Martin — focus on chapters 1-5",
            "LeetCode — solve 2 easy problems daily for 30 days",
            "Frontend Masters — System Design course",
        ],
        "career_path_advice": (
            f"As a {profession}, your next milestone should be landing a junior role. "
            "Focus on building a portfolio of 3 polished projects, each demonstrating a different skill. "
            "Start networking on LinkedIn and contributing to open-source to increase visibility."
        ),
    }


# Singleton
guidance_agent = GuidanceAgent()
