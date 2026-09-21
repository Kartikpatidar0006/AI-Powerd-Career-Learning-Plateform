"""Database session dependency for FastAPI routes."""

from sqlalchemy.orm import Session
from db.session import SessionLocal

def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
