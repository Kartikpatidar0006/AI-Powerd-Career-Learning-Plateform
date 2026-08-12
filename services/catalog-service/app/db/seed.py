"""Seed professions & skills into Catalog Service database."""
from __future__ import annotations
import logging, uuid
from sqlalchemy import select
from app.db.session import SessionLocal
from app.models.profession import Profession
from app.models.skill import Skill

logger = logging.getLogger(__name__)

SEED_PROFESSIONS = [
    {
        "name": "Machine Learning Engineer",
        "slug": "machine-learning-engineer",
        "category": "AI & Machine Learning",
        "description": "Develop predictive models, feature pipelines, recommendation engines, and end-to-end MLOps production systems.",
        "average_salary": 145000.00,
        "growth_rate": 18.50,
        "required_skills": ["Feature Engineering", "Scikit-Learn", "MLOps"],
        "roadmap": {"phases": ["Data Engineering", "Model Development", "Deployment"]},
        "skills": [
            {"name": "Feature Engineering & Pandas", "category": "Data Science", "description": "Transform raw data into feature sets"},
            {"name": "Scikit-Learn & Model Tuning", "category": "Machine Learning", "description": "Train and tune classification and regression models"},
            {"name": "MLOps & MLflow Tracking", "category": "MLOps", "description": "Track experiments and deploy models"},
        ],
    },
    {
        "name": "Full Stack Web Developer",
        "slug": "full-stack-web-developer",
        "category": "Software Engineering",
        "description": "Build responsive web interfaces and scalable backend REST/GraphQL APIs.",
        "average_salary": 120000.00,
        "growth_rate": 15.00,
        "required_skills": ["React", "FastAPI / Node.js", "PostgreSQL"],
        "roadmap": {"phases": ["Frontend Foundations", "Backend Architecture", "Full-Stack System Integration"]},
        "skills": [
            {"name": "React & Modern UI State", "category": "Frontend", "description": "Build interactive SPAs with React"},
            {"name": "FastAPI Async Services", "category": "Backend", "description": "Build high-performance REST microservices"},
            {"name": "PostgreSQL Database Architecture", "category": "Database", "description": "Design relational schemas and optimize queries"},
        ],
    },
    {
        "name": "Cloud DevOps Engineer",
        "slug": "cloud-devops-engineer",
        "category": "Cloud & Infrastructure",
        "description": "Design CI/CD automation pipelines, Kubernetes clusters, and Infrastructure as Code.",
        "average_salary": 135000.00,
        "growth_rate": 20.00,
        "required_skills": ["Docker", "Kubernetes", "Terraform"],
        "roadmap": {"phases": ["Containerization", "Orchestration", "CI/CD & Observability"]},
        "skills": [
            {"name": "Docker Containerization", "category": "DevOps", "description": "Containerize microservices"},
            {"name": "Kubernetes Cluster Orchestration", "category": "DevOps", "description": "Deploy and manage container workloads"},
            {"name": "Terraform Infrastructure as Code", "category": "Cloud", "description": "Provision cloud resources declaratively"},
        ],
    },
]

def seed_catalog_data() -> None:
    db = SessionLocal()
    try:
        for p_data in SEED_PROFESSIONS:
            stmt = select(Profession).where(Profession.slug == p_data["slug"])
            prof = db.execute(stmt).scalars().first()
            if not prof:
                prof = Profession(
                    id=uuid.uuid4(),
                    name=p_data["name"],
                    slug=p_data["slug"],
                    category=p_data["category"],
                    description=p_data["description"],
                    average_salary=p_data["average_salary"],
                    growth_rate=p_data["growth_rate"],
                    required_skills=p_data["required_skills"],
                    roadmap=p_data["roadmap"],
                )
                db.add(prof)
                db.commit()
                db.refresh(prof)
                logger.info("Created Profession: %s", prof.name)

            for s_data in p_data["skills"]:
                s_stmt = select(Skill).where(Skill.name == s_data["name"], Skill.profession_id == prof.id)
                sk = db.execute(s_stmt).scalars().first()
                if not sk:
                    sk = Skill(
                        id=uuid.uuid4(),
                        profession_id=prof.id,
                        name=s_data["name"],
                        category=s_data["category"],
                        description=s_data["description"],
                        difficulty=s_data.get("difficulty", "Beginner"),
                    )
                    db.add(sk)
                    logger.info("  -> Added Skill: %s", sk.name)
        db.commit()
        logger.info("Catalog data seeded successfully.")
    except Exception as exc:
        logger.error("Catalog seed failed: %s", exc, exc_info=True)
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    seed_catalog_data()
