"""Seed initial roles and test user for Auth Service."""
from __future__ import annotations
import logging, uuid
from sqlalchemy import select
from app.db.session import SessionLocal
from app.models.role import Role
from app.models.user import User
from app.core.security import hash_password

logger = logging.getLogger(__name__)

def seed_auth_data() -> None:
    db = SessionLocal()
    try:
        roles = [
            {"name": "admin", "description": "Administrator with full system access"},
            {"name": "student", "description": "Learner pursuing career roadmaps"},
            {"name": "mentor", "description": "Industry mentor providing feedback"},
        ]
        role_map = {}
        for r_data in roles:
            stmt = select(Role).where(Role.name == r_data["name"])
            existing = db.execute(stmt).scalars().first()
            if not existing:
                role = Role(id=uuid.uuid4(), name=r_data["name"], description=r_data["description"])
                db.add(role)
                db.flush()
                role_map[r_data["name"]] = role
                logger.info("Created role: %s", r_data["name"])
            else:
                role_map[r_data["name"]] = existing

        # Seed default test user
        user_stmt = select(User).where(User.email == "testlearner@aicareer.com")
        existing_user = db.execute(user_stmt).scalars().first()
        if not existing_user:
            student_role = role_map.get("student")
            test_user = User(
                id=uuid.uuid4(),
                full_name="Test Learner",
                email="testlearner@aicareer.com",
                password_hash=hash_password("SecretPassword123!"),
                is_active=True,
                is_verified=True,
                role_id=student_role.id if student_role else None,
            )
            db.add(test_user)
            logger.info("Created test user: testlearner@aicareer.com")

        db.commit()
    except Exception as exc:
        logger.warning("Auth seed error: %s", exc)
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    seed_auth_data()

