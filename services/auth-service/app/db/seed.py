"""Seed initial roles for Auth Service."""
from __future__ import annotations
import logging, uuid
from sqlalchemy import select
from app.db.session import SessionLocal
from app.models.role import Role

logger = logging.getLogger(__name__)

def seed_auth_data() -> None:
    db = SessionLocal()
    try:
        roles = [
            {"name": "admin", "description": "Administrator with full system access"},
            {"name": "student", "description": "Learner pursuing career roadmaps"},
            {"name": "mentor", "description": "Industry mentor providing feedback"},
        ]
        for r_data in roles:
            stmt = select(Role).where(Role.name == r_data["name"])
            existing = db.execute(stmt).scalars().first()
            if not existing:
                role = Role(id=uuid.uuid4(), name=r_data["name"], description=r_data["description"])
                db.add(role)
                logger.info("Created role: %s", r_data["name"])
        db.commit()
    except Exception as exc:
        logger.warning("Auth seed error: %s", exc)
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    seed_auth_data()
