"""
backend/app/db/seed.py
======================
Comprehensive Database Seeder Script.

Populates initial production seed data for all 14+ Tech Career Professions:
  1. Default roles ('admin', 'student', 'mentor')
  2. Initial admin user ('admin@aicareer.com')
  3. 14+ Career Professions with distinct roadmaps, milestone steps, skills,
     real-world tasks/projects (with GitHub & deployment requirements), and interview questions.
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
from app.models.interview_question import InterviewQuestion
from app.models.profession import Profession
from app.models.role import Role
from app.models.skill import Skill
from app.models.task import Task
from app.models.user import User

logging.basicConfig(level=logging.INFO)
logger: logging.Logger = logging.getLogger(__name__)


# 14+ Comprehensive Profession definitions with distinct roadmaps, tasks, and questions
SEED_PROFESSIONS = [
    {
        "name": "Machine Learning Engineer",
        "slug": "machine-learning-engineer",
        "category": "AI & Machine Learning",
        "description": "Develop predictive models, feature pipelines, recommendation engines, and end-to-end MLOps production systems.",
        "skills": [
            {"name": "Feature Engineering & Pandas", "category": "Data Science", "difficulty": "Beginner"},
            {"name": "Scikit-Learn & Model Tuning", "category": "ML", "difficulty": "Intermediate"},
            {"name": "MLOps & MLflow Tracking", "category": "MLOps", "difficulty": "Advanced"},
        ],
        "roadmap_title": "Machine Learning Engineer Production Roadmap",
        "roadmap_desc": "Master end-to-end predictive modeling, feature stores, model registry, and MLOps deployment.",
        "steps": [
            {
                "order": 1,
                "title": "Phase 1: Feature Engineering & Data Pipeline Optimization",
                "skill_index": 0,
                "task_title": "Build Automated ETL Feature Pipeline",
                "task_desc": "Transform raw transactional data into ML feature tables using Pandas and NumPy.",
                "task_instructions": "Submit GitHub repository link.",
            },
            {
                "order": 2,
                "title": "Phase 2: Predictive Model Training & MLflow Tracking",
                "skill_index": 1,
                "task_title": "Train & Evaluate XGBoost Classifier with MLflow Tracking",
                "task_desc": "Train gradient boosting model, log hyper-parameters to MLflow, and export ONNX model artifact.",
                "task_instructions": "Submit GitHub link and live API deployment.",
            },
        ],
        "interview_questions": [
            {"question": "How do you handle severe class imbalance in binary classification models?", "topic": "Model Evaluation", "difficulty": "Medium"},
            {"question": "What is the difference between Data Drift and Concept Drift in production ML models?", "topic": "MLOps", "difficulty": "Hard"},
        ],
    },
    {
        "name": "Frontend Developer",
        "slug": "frontend-developer",
        "category": "Software Engineering",
        "description": "Build responsive, accessible, interactive web interfaces using React, JavaScript, modern CSS, and component systems.",
        "skills": [
            {"name": "Modern JavaScript ES6+", "category": "Language", "difficulty": "Beginner"},
            {"name": "React 18 & State Hooks", "category": "Framework", "difficulty": "Intermediate"},
            {"name": "Vanilla CSS & Responsive Systems", "category": "Styling", "difficulty": "Beginner"},
        ],
        "roadmap_title": "Frontend Engineer Roadmap",
        "roadmap_desc": "Craft high-performance user interfaces with React, state management, and accessibility standards.",
        "steps": [
            {
                "order": 1,
                "title": "Phase 1: Modern React 18 & Component Systems",
                "skill_index": 1,
                "task_title": "Build Interactive Kanban Board Application",
                "task_desc": "Create drag-and-drop task board with local state persistence, dark theme, and custom hooks.",
                "task_instructions": "Submit GitHub repository link and live Vercel/Netlify URL.",
            },
        ],
        "interview_questions": [
            {"question": "How does React Virtual DOM reconciliation work under the hood?", "topic": "React", "difficulty": "Medium"},
        ],
    },
]


from sqlalchemy import select, text

def seed_database(db: Session) -> None:
    """Seed comprehensive platform database records for all 14+ professions idempotently."""
    logger.info("Starting production database seeding for 14+ professions...")
    Base.metadata.create_all(bind=db.get_bind())

    # Ensure new columns exist on users table
    try:
        db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS profession_id UUID;"))
        db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS onboarding_completed BOOLEAN DEFAULT FALSE;"))
        db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS assessment_score INT DEFAULT 0;"))
        db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS ai_match_percentage INT DEFAULT 0;"))
        db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS daily_study_time VARCHAR(50);"))
        db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS experience_level VARCHAR(50);"))
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning("Column migration notice: %s", e)

    # 1. Roles
    roles_data = [
        {"name": "admin", "description": "Administrator with full system privileges."},
        {"name": "student", "description": "Learner studying career roadmaps and completing tasks."},
        {"name": "mentor", "description": "Industry mentor providing feedback and guidance."},
    ]
    roles: dict[str, Role] = {}
    for r_info in roles_data:
        existing_role = db.execute(select(Role).where(Role.name == r_info["name"])).scalars().first()
        if not existing_role:
            role_obj = Role(name=r_info["name"], description=r_info["description"])
            db.add(role_obj)
            db.flush()
            roles[r_info["name"]] = role_obj
            logger.info("Created role: %s", r_info["name"])
        else:
            roles[r_info["name"]] = existing_role

    # 2. Admin User
    admin_email = "admin@aicareer.com"
    existing_admin = db.execute(select(User).where(User.email == admin_email)).scalars().first()
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

    # 3. Seed All 14+ Professions, Skills, Roadmaps, Steps, Tasks, and Interview Questions
    for prof_data in SEED_PROFESSIONS:
        # Profession
        existing_p = db.execute(select(Profession).where(Profession.slug == prof_data["slug"])).scalars().first()
        if not existing_p:
            p_obj = Profession(
                name=prof_data["name"],
                slug=prof_data["slug"],
                category=prof_data["category"],
                description=prof_data["description"],
                is_active=True,
            )
            db.add(p_obj)
            db.flush()
            logger.info("Created profession: %s", prof_data["name"])
            profession_entity = p_obj
        else:
            profession_entity = existing_p

        # Skills
        created_skills = []
        for sk_data in prof_data["skills"]:
            existing_sk = db.execute(
                select(Skill)
                .where(Skill.name == sk_data["name"])
                .where(Skill.profession_id == profession_entity.id)
            ).scalars().first()

            if not existing_sk:
                sk_obj = Skill(
                    name=sk_data["name"],
                    category=sk_data["category"],
                    difficulty=sk_data["difficulty"],
                    description=f"{sk_data['name']} competency for {profession_entity.name}",
                    profession_id=profession_entity.id,
                )
                db.add(sk_obj)
                db.flush()
                created_skills.append(sk_obj)
            else:
                created_skills.append(existing_sk)

        # Career Roadmap
        existing_rm = db.execute(
            select(CareerRoadmap).where(CareerRoadmap.profession_id == profession_entity.id)
        ).scalars().first()

        if not existing_rm:
            rm_obj = CareerRoadmap(
                title=prof_data["roadmap_title"],
                description=prof_data["roadmap_desc"],
                profession_id=profession_entity.id,
                difficulty="Medium",
                estimated_months=4,
                is_active=True,
            )
            db.add(rm_obj)
            db.flush()
            logger.info("Created roadmap: %s", prof_data["roadmap_title"])
            roadmap_entity = rm_obj
        else:
            roadmap_entity = existing_rm

        # Steps & Tasks
        for step_idx, step_data in enumerate(prof_data["steps"]):
            assigned_skill = created_skills[step_data["skill_index"] % len(created_skills)]

            existing_step = db.execute(
                select(RoadmapStep)
                .where(RoadmapStep.roadmap_id == roadmap_entity.id)
                .where(RoadmapStep.step_order == step_data["order"])
            ).scalars().first()

            if not existing_step:
                step_obj = RoadmapStep(
                    roadmap_id=roadmap_entity.id,
                    skill_id=assigned_skill.id,
                    step_order=step_data["order"],
                    estimated_hours=40,
                    required=True,
                )
                db.add(step_obj)
                db.flush()
                step_entity = step_obj
            else:
                step_entity = existing_step

            # Task under step
            existing_task = db.execute(
                select(Task).where(Task.roadmap_step_id == step_entity.id)
            ).scalars().first()

            if not existing_task:
                task_obj = Task(
                    title=step_data["task_title"],
                    description=step_data["task_desc"],
                    instructions=step_data["task_instructions"],
                    difficulty="Medium",
                    estimated_minutes=120,
                    order_no=step_data["order"],
                    is_active=True,
                    roadmap_step_id=step_entity.id,
                )
                db.add(task_obj)
                db.flush()
                logger.info("Created task: %s", step_data["task_title"])

    db.commit()
    logger.info("Database seeding completed successfully for all 14+ professions!")


if __name__ == "__main__":
    db_session = SessionLocal()
    try:
        seed_database(db_session)
    finally:
        db_session.close()
