"""
services/agent-service/app/agents/agent3_evaluation.py
--------------------------------------------------------
Agent 3: GitHub repo evaluation + interview question generation.
- Fetches GitHub repo info via API
- Evaluates code quality, structure, documentation
- Generates 8-15 targeted interview questions
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone

import httpx
from sqlalchemy.orm import Session

from app.agents.llm_client import chat_complete, parse_json_response
from app.core.config import settings
from app.models.evaluation import Evaluation
from app.models.problem import Problem
from app.models.student import Student
from app.schemas.evaluation import EvaluationRequest

logger = logging.getLogger(__name__)

EVALUATION_SYSTEM_PROMPT = """You are a senior software engineer conducting a thorough code review.
Evaluate the GitHub repository and provide detailed, constructive feedback.
Return ONLY valid JSON with no markdown or extra text.
"""

QUESTION_SYSTEM_PROMPT = """You are an experienced technical interviewer preparing questions 
based on a student's submitted project and their profession.
Generate insightful questions that probe deep understanding.
Return ONLY valid JSON with no markdown or extra text.
"""


def _extract_repo_info(github_url: str) -> tuple[str, str] | None:
    """Extract owner and repo name from a GitHub URL."""
    patterns = [
        r"github\.com[:/]([^/]+)/([^/\s.]+?)(?:\.git)?/?$",
        r"github\.com/([^/]+)/([^/\s.]+)",
    ]
    for pattern in patterns:
        m = re.search(pattern, github_url)
        if m:
            return m.group(1), m.group(2)
    return None


def _fetch_repo_metadata(owner: str, repo: str) -> dict:
    """Fetch repo metadata from GitHub API."""
    headers = {"Accept": "application/vnd.github.v3+json"}
    if settings.GITHUB_TOKEN:
        headers["Authorization"] = f"token {settings.GITHUB_TOKEN}"

    base = f"https://api.github.com/repos/{owner}/{repo}"
    result: dict = {}

    try:
        with httpx.Client(timeout=10.0) as client:
            # Repo info
            r = client.get(base, headers=headers)
            if r.status_code == 200:
                d = r.json()
                result["name"] = d.get("name")
                result["description"] = d.get("description")
                result["language"] = d.get("language")
                result["stars"] = d.get("stargazers_count", 0)
                result["forks"] = d.get("forks_count", 0)
                result["open_issues"] = d.get("open_issues_count", 0)
                result["has_readme"] = False
                result["topics"] = d.get("topics", [])
                result["default_branch"] = d.get("default_branch", "main")

            # README presence
            rr = client.get(f"{base}/readme", headers=headers)
            result["has_readme"] = rr.status_code == 200

            # Commits count (first page)
            cr = client.get(f"{base}/commits?per_page=100", headers=headers)
            if cr.status_code == 200:
                result["commit_count"] = len(cr.json())
            else:
                result["commit_count"] = 0

            # Languages breakdown
            lr = client.get(f"{base}/languages", headers=headers)
            result["languages"] = lr.json() if lr.status_code == 200 else {}

            # File tree (top level)
            tr = client.get(
                f"{base}/git/trees/{result.get('default_branch', 'main')}",
                headers=headers,
            )
            if tr.status_code == 200:
                result["root_files"] = [item["path"] for item in tr.json().get("tree", [])]
            else:
                result["root_files"] = []

    except Exception as exc:
        logger.warning("GitHub API fetch error: %s", exc)

    return result


def _build_evaluation_prompt(
    profession: str, repo_meta: dict, problem_title: str | None
) -> str:
    return f"""
Evaluate this GitHub repository submitted by a {profession} student.
{"Problem they were solving: " + problem_title if problem_title else ""}

Repository metadata:
- Name: {repo_meta.get("name")}
- Description: {repo_meta.get("description")}
- Primary language: {repo_meta.get("language")}
- Languages used: {repo_meta.get("languages")}
- Has README: {repo_meta.get("has_readme")}
- Commit count: {repo_meta.get("commit_count")}
- Root files: {repo_meta.get("root_files")}
- Topics: {repo_meta.get("topics")}

Return a JSON object with:
{{
  "code_quality_score": 0-100,
  "functionality_score": 0-100,
  "documentation_score": 0-100,
  "best_practices_score": 0-100,
  "overall_score": 0-100,
  "strengths": ["strength 1", "strength 2", ...],
  "improvements": ["improvement 1", "improvement 2", ...],
  "raw_analysis": "Detailed 2-3 paragraph analysis"
}}
"""


def _build_questions_prompt(
    profession: str, repo_meta: dict, evaluation: dict, experience: str
) -> str:
    return f"""
Generate 10 technical interview questions for a {experience} {profession} student 
based on their GitHub project.

Project: {repo_meta.get("name")} | Language: {repo_meta.get("language")}
Their scores — Code Quality: {evaluation.get("code_quality_score")}, 
Functionality: {evaluation.get("functionality_score")}, 
Documentation: {evaluation.get("documentation_score")}

Questions should:
1. Start with what they built and why (2 questions)
2. Probe technical depth on languages/frameworks used (3 questions)
3. Ask about architecture and design decisions (2 questions)
4. Cover testing and debugging approach (1 question)
5. Focus on improvements and future work (2 questions)

Return a JSON array of question strings (10 questions total).
"""


class EvaluationAgent:
    """Agent 3 — evaluates GitHub submissions and generates interview questions."""

    def evaluate(self, db: Session, request: EvaluationRequest) -> Evaluation:
        student = db.query(Student).filter(Student.id == request.student_id).first()
        if not student:
            raise ValueError(f"Student {request.student_id} not found")

        problem_title = None
        if request.problem_id:
            prob = db.query(Problem).filter(Problem.id == request.problem_id).first()
            if prob:
                problem_title = prob.title

        # Create evaluation record
        evaluation = Evaluation(
            student_id=request.student_id,
            problem_id=request.problem_id,
            github_url=request.github_url,
            status="evaluating",
        )
        db.add(evaluation)
        db.commit()
        db.refresh(evaluation)

        try:
            # Fetch GitHub metadata
            repo_info = _extract_repo_info(request.github_url)
            repo_meta: dict = {}
            if repo_info:
                owner, repo = repo_info
                repo_meta = _fetch_repo_metadata(owner, repo)
            else:
                logger.warning("Could not parse GitHub URL: %s", request.github_url)
                repo_meta = {"name": "unknown", "language": "unknown"}

            # Step 1: Evaluate the repo
            eval_prompt = _build_evaluation_prompt(student.profession, repo_meta, problem_title)
            eval_raw = chat_complete(EVALUATION_SYSTEM_PROMPT, eval_prompt)
            eval_data = parse_json_response(eval_raw)

            if isinstance(eval_data, dict) and "mock" in eval_data:
                eval_data = _mock_evaluation()

            # Step 2: Generate interview questions
            q_prompt = _build_questions_prompt(
                student.profession, repo_meta, eval_data, student.experience_level
            )
            q_raw = chat_complete(QUESTION_SYSTEM_PROMPT, q_prompt)
            q_data = parse_json_response(q_raw)

            if isinstance(q_data, dict) and "mock" in q_data:
                q_data = _mock_questions(student.profession)

            # Update evaluation record
            evaluation.code_quality_score = int(eval_data.get("code_quality_score", 0))
            evaluation.functionality_score = int(eval_data.get("functionality_score", 0))
            evaluation.documentation_score = int(eval_data.get("documentation_score", 0))
            evaluation.best_practices_score = int(eval_data.get("best_practices_score", 0))
            evaluation.overall_score = int(eval_data.get("overall_score", 0))
            evaluation.strengths = json.dumps(eval_data.get("strengths", []))
            evaluation.improvements = json.dumps(eval_data.get("improvements", []))
            evaluation.raw_analysis = eval_data.get("raw_analysis", "")
            evaluation.interview_questions = json.dumps(q_data if isinstance(q_data, list) else [])
            evaluation.status = "completed"
            evaluation.completed_at = datetime.now(timezone.utc)

        except Exception as exc:
            logger.error("Evaluation failed: %s", exc, exc_info=True)
            evaluation.status = "failed"
            evaluation.raw_analysis = str(exc)

        db.commit()
        db.refresh(evaluation)
        return evaluation

    def get_evaluation(self, db: Session, evaluation_id: uuid.UUID) -> Evaluation | None:
        return db.query(Evaluation).filter(Evaluation.id == evaluation_id).first()

    def get_student_evaluations(self, db: Session, student_id: uuid.UUID) -> list[Evaluation]:
        return (
            db.query(Evaluation)
            .filter(Evaluation.student_id == student_id)
            .order_by(Evaluation.created_at.desc())
            .all()
        )


def _mock_evaluation() -> dict:
    return {
        "code_quality_score": 72,
        "functionality_score": 78,
        "documentation_score": 65,
        "best_practices_score": 70,
        "overall_score": 71,
        "strengths": ["Good project structure", "Meaningful commit messages", "Responsive UI"],
        "improvements": ["Add unit tests", "Improve API error handling", "Add environment variable documentation"],
        "raw_analysis": (
            "The project demonstrates a solid understanding of core concepts. "
            "The code is reasonably well-organized with a clear separation of concerns. "
            "Some areas for improvement include test coverage and more detailed documentation."
        ),
    }


def _mock_questions(profession: str) -> list[str]:
    return [
        f"Walk me through your {profession} project — what problem does it solve?",
        "Why did you choose this tech stack over alternatives?",
        "Explain your database schema design decisions.",
        "How does your authentication/authorization work?",
        "What was the most challenging bug you encountered and how did you fix it?",
        "How would you scale this application to handle 10,000 concurrent users?",
        "Describe your API design — did you follow REST conventions?",
        "How did you handle error states in both frontend and backend?",
        "What testing strategy did you use? What would you add?",
        "If you had one more week, what would you improve first and why?",
    ]


# Singleton
evaluation_agent = EvaluationAgent()
