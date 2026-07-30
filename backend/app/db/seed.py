"""
backend/app/db/seed.py
======================
Database Seeder Script.

Populates initial database seed data:
  - Default roles ('admin', 'student', 'mentor')
  - Initial admin user ('admin@aicareer.com')
  - Sample professions ('Backend Developer', 'Frontend Developer', 'AI Engineer')
  - Sample skills ('Python', 'FastAPI', 'PostgreSQL', 'React')
  - Sample career roadmaps & steps
  - Sample learning tasks

Usage
-----
Run via CLI::

    python -m app.db.seed
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.career_roadmap import CareerRoadmap, RoadmapStep
from app.models.profession import Profession
from app.models.role import Role
from app.models.skill import Skill
from app.models.task import Task
from app.models.user import User

logging.basicConfig(level=logging.INFO)
logger: logging.Logger = logging.getLogger(__name__)


def seed_database(db: Session) -> None:
    """Seed initial platform database records idempotently.

    Args:
        db: Active SQLAlchemy database session.
    """
    logger.info("Starting database seeding...")
    Base.metadata.create_all(bind=db.get_bind())

    # 1. Default Roles
    roles_data = [
        {"name": "admin", "description": "Administrator with full system privileges."},
        {"name": "student", "description": "Learner studying career roadmaps and completing tasks."},
        {"name": "mentor", "description": "Industry mentor providing feedback and guidance."},
    ]
    roles: dict[str, Role] = {}
    for r_info in roles_data:
        r_stmt = select(Role).where(Role.name == r_info["name"])
        existing_role = db.execute(r_stmt).scalars().first()
        if not existing_role:
            role_obj = Role(name=r_info["name"], description=r_info["description"])
            db.add(role_obj)
            db.flush()
            roles[r_info["name"]] = role_obj
            logger.info("Created role: %s", r_info["name"])
        else:
            roles[r_info["name"]] = existing_role

    # 2. Sample Professions
    professions_data = [
        {
            "name": "Backend Developer",
            "slug": "backend-developer",
            "description": "Master server-side architecture, APIs, databases, and microservices.",
        },
        {
            "name": "Frontend Developer",
            "slug": "frontend-developer",
            "description": "Build responsive, high-performance web applications using modern JS frameworks.",
        },
        {
            "name": "AI Engineer",
            "slug": "ai-engineer",
            "description": "Develop state-of-the-art AI systems, LLM agents, and machine learning pipelines.",
        },
    ]
    professions: dict[str, Profession] = {}
    for p_info in professions_data:
        p_stmt = select(Profession).where(Profession.slug == p_info["slug"])
        existing_p = db.execute(p_stmt).scalars().first()
        if not existing_p:
            p_obj = Profession(
                name=p_info["name"],
                slug=p_info["slug"],
                description=p_info["description"],
                is_active=True,
            )
            db.add(p_obj)
            db.flush()
            professions[p_info["slug"]] = p_obj
            logger.info("Created profession: %s", p_info["name"])
        else:
            professions[p_info["slug"]] = existing_p

    # 3. Admin User
    admin_email = "admin@aicareer.com"
    admin_stmt = select(User).where(User.email == admin_email)
    existing_admin = db.execute(admin_stmt).scalars().first()
    if not existing_admin:
        admin_user = User(
            email=admin_email,
            full_name="System Admin",
            password_hash=hash_password("AdminPassword123!"),
            role_id=roles["admin"].id,
            is_active=True,
            is_verified=True,
        )
        db.add(admin_user)
        db.flush()
        logger.info("Created admin user: %s", admin_email)

    # 4. Sample Skills
    skills_data = [
        {"name": "Python", "category": "Programming Language", "difficulty": "Beginner", "description": "Core Python 3.11+, OOP, async.", "profession_slug": "backend-developer"},
        {"name": "FastAPI", "category": "Web Framework", "difficulty": "Intermediate", "description": "High-performance RESTful API framework.", "profession_slug": "backend-developer"},
        {"name": "PostgreSQL", "category": "Database", "difficulty": "Intermediate", "description": "Relational database design, SQL & ORM.", "profession_slug": "backend-developer"},
        {"name": "React", "category": "Frontend Framework", "difficulty": "Beginner", "description": "Modern React 18, hooks, state management.", "profession_slug": "frontend-developer"},
    ]
    skills: dict[str, Skill] = {}
    for s_info in skills_data:
        s_stmt = select(Skill).where(Skill.name == s_info["name"])
        existing_s = db.execute(s_stmt).scalars().first()
        if not existing_s:
            s_obj = Skill(
                name=s_info["name"],
                category=s_info["category"],
                difficulty=s_info["difficulty"],
                description=s_info["description"],
                profession_id=professions[s_info["profession_slug"]].id,
            )
            db.add(s_obj)
            db.flush()
            skills[s_info["name"]] = s_obj
            logger.info("Created skill: %s", s_info["name"])
        else:
            skills[s_info["name"]] = existing_s

    # 5. Sample Career Roadmap
    rm_stmt = select(CareerRoadmap).where(CareerRoadmap.title == "Backend Developer Mastery")
    roadmap = db.execute(rm_stmt).scalars().first()
    if not roadmap:
        roadmap = CareerRoadmap(
            title="Backend Developer Mastery",
            description="Comprehensive step-by-step roadmap from beginner to Senior Backend Engineer.",
            profession_id=professions["backend-developer"].id,
            difficulty="Medium",
            estimated_months=6,
            is_active=True,
        )
        db.add(roadmap)
        db.flush()
        logger.info("Created career roadmap: Backend Developer Mastery")

        # Roadmap Steps
        steps_info = [
            {"order": 1, "skill": skills["FastAPI"], "hours": 40},
            {"order": 2, "skill": skills["PostgreSQL"], "hours": 30},
        ]
        roadmap_steps: list[RoadmapStep] = []
        for st in steps_info:
            step_obj = RoadmapStep(
                roadmap_id=roadmap.id,
                skill_id=st["skill"].id,
                step_order=st["order"],
                estimated_hours=st["hours"],
                required=True,
            )
            db.add(step_obj)
            db.flush()
            roadmap_steps.append(step_obj)
            logger.info("Created roadmap step order: %d", st["order"])

        # 6. Sample Tasks
        tasks_data = [
            {
                "title": "Build a REST API with FastAPI & Pydantic",
                "description": "Design and implement a fully validated REST API endpoint architecture.",
                "instructions": "Implement JWT auth, Pydantic schemas, and Dependency Injection.",
                "difficulty": "Medium",
                "estimated_minutes": 120,
                "order_no": 1,
                "roadmap_step_id": roadmap_steps[0].id,
            },
            {
                "title": "Design PostgreSQL Schema with SQLAlchemy ORM",
                "description": "Create relational database tables with foreign keys and index optimizations.",
                "instructions": "Write Alembic migrations and SQLAlchemy 2.x declarative models.",
                "difficulty": "Medium",
                "estimated_minutes": 90,
                "order_no": 2,
                "roadmap_step_id": roadmap_steps[1].id,
            },
        ]
        for t_info in tasks_data:
            t_obj = Task(
                title=t_info["title"],
                description=t_info["description"],
                instructions=t_info["instructions"],
                difficulty=t_info["difficulty"],
                estimated_minutes=t_info["estimated_minutes"],
                order_no=t_info["order_no"],
                is_active=True,
                roadmap_step_id=t_info["roadmap_step_id"],
            )
            db.add(t_obj)
            logger.info("Created sample task: %s", t_info["title"])

    db.commit()
    logger.info("Database seeding completed successfully!")


if __name__ == "__main__":
    db_session = SessionLocal()
    try:
        seed_database(db_session)
    finally:
        db_session.close()
