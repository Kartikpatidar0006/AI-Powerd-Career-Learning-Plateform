"""
services/agent-service/app/agents/agent2_problems.py
------------------------------------------------------
Agent 2: Problem generation agent.
- Generates easy / medium / hard professional problems using LLM
- Stores them in DB for the student
"""
from __future__ import annotations

import json
import logging
import uuid

from sqlalchemy.orm import Session

from app.agents.llm_client import chat_complete, parse_json_response
from app.models.problem import Problem
from app.models.student import Student
from app.schemas.problem import ProblemGenerateRequest, ProblemOut

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert software engineering mentor with 15+ years of experience.
Your job is to generate realistic, professional coding/project problems for students 
based on their chosen profession and difficulty level.

Each problem MUST be a real-world mini-project that would genuinely help the student grow.
Return ONLY valid JSON. No extra text or markdown fences.
"""


def _build_user_prompt(profession: str, experience: str, stack: str | None, difficulty: str, count: int) -> str:
    stack_info = f"Preferred tech stack: {stack}" if stack else "Tech stack: use appropriate modern technologies"
    return f"""
Generate {count} {difficulty}-level project problem(s) for a {experience} student 
targeting the profession: "{profession}".
{stack_info}

Return a JSON array of problem objects, each with:
{{
  "title": "Problem title",
  "description": "Detailed problem description (2-3 paragraphs)",
  "difficulty": "{difficulty}",
  "tech_stack": "comma-separated technologies",
  "estimated_hours": integer (realistic hours to complete),
  "requirements": ["requirement 1", "requirement 2", ...],
  "acceptance_criteria": ["criteria 1", "criteria 2", ...]
}}

Make the problems genuinely educational and industry-relevant.
"""


class ProblemAgent:
    """Agent 2 — generates profession-appropriate problems via LLM."""

    def generate_problems(
        self, db: Session, request: ProblemGenerateRequest
    ) -> list[Problem]:
        student = db.query(Student).filter(Student.id == request.student_id).first()
        if not student:
            raise ValueError(f"Student {request.student_id} not found")

        logger.info(
            "Generating %d %s problems for student %s (profession: %s)",
            request.count, request.difficulty, student.email, student.profession
        )

        user_prompt = _build_user_prompt(
            profession=student.profession,
            experience=student.experience_level,
            stack=student.preferred_stack,
            difficulty=request.difficulty,
            count=request.count,
        )

        raw = chat_complete(SYSTEM_PROMPT, user_prompt)
        data = parse_json_response(raw)

        # Handle mock / error cases
        if isinstance(data, dict) and "mock" in data:
            logger.info("Mock mode — generating placeholder problems.")
            data = _mock_problems(request.difficulty, request.count, student.profession)

        if not isinstance(data, list):
            data = [data]

        problems: list[Problem] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            problem = Problem(
                student_id=student.id,
                title=item.get("title", "Untitled Problem"),
                description=item.get("description", ""),
                difficulty=request.difficulty,
                tech_stack=item.get("tech_stack"),
                estimated_hours=int(item.get("estimated_hours", 8)),
                requirements=json.dumps(item.get("requirements", [])),
                acceptance_criteria=json.dumps(item.get("acceptance_criteria", [])),
                is_assigned=False,
            )
            db.add(problem)
            problems.append(problem)

        db.commit()
        for p in problems:
            db.refresh(p)

        logger.info("Generated and saved %d problems.", len(problems))
        return problems

    def get_student_problems(self, db: Session, student_id: uuid.UUID) -> list[Problem]:
        return db.query(Problem).filter(Problem.student_id == student_id).order_by(Problem.created_at.desc()).all()

    def assign_problem(self, db: Session, problem_id: uuid.UUID, student_id: uuid.UUID) -> Problem | None:
        problem = db.query(Problem).filter(
            Problem.id == problem_id, Problem.student_id == student_id
        ).first()
        if not problem:
            return None
        problem.is_assigned = True
        db.commit()
        db.refresh(problem)
        return problem


def _mock_problems(difficulty: str, count: int, profession: str) -> list[dict]:
    templates = {
        "easy": {
            "title": f"Build a Simple {profession} Portfolio Page",
            "description": (
                f"Create a clean, responsive personal portfolio page that showcases your skills as a {profession}. "
                "The page should include sections for About, Skills, Projects, and Contact. "
                "Focus on clean HTML structure and CSS styling."
            ),
            "estimated_hours": 6,
            "requirements": ["Responsive layout", "At least 3 sections", "Contact form"],
            "acceptance_criteria": ["Renders correctly on mobile", "Valid HTML", "CSS animations on hover"],
        },
        "medium": {
            "title": f"Build a {profession} Task Management App",
            "description": (
                f"Develop a full-featured task management application relevant to {profession} workflows. "
                "Include user authentication, CRUD for tasks, and basic filtering/sorting. "
                "Use a modern frontend framework and a REST API backend."
            ),
            "estimated_hours": 20,
            "requirements": ["User login/register", "Task CRUD", "Filter by status", "REST API"],
            "acceptance_criteria": ["JWT auth works", "All CRUD operations tested", "API documented"],
        },
        "hard": {
            "title": f"Build a Real-time {profession} Collaboration Platform",
            "description": (
                f"Design and implement a real-time collaborative platform tailored to {profession} workflows. "
                "Features include live updates via WebSockets, role-based access control, notifications, "
                "and a production-grade CI/CD pipeline."
            ),
            "estimated_hours": 40,
            "requirements": ["WebSocket real-time updates", "RBAC", "Notifications", "Docker deployment"],
            "acceptance_criteria": ["Real-time sync < 200ms", "RBAC tested", "Docker compose runs"],
        },
    }
    template = templates.get(difficulty, templates["medium"])
    return [
        {**template, "difficulty": difficulty, "tech_stack": "React, FastAPI, PostgreSQL"}
        for _ in range(count)
    ]


# Singleton
problem_agent = ProblemAgent()
