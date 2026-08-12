"""services/learning-service/app/db/session.py — SQLAlchemy session."""
from __future__ import annotations
import logging
from collections.abc import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool
from app.core.config import settings

logger = logging.getLogger(__name__)

def _build_engine() -> Engine:
    return create_engine(
        url=settings.DATABASE_URL,
        poolclass=QueuePool,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_timeout=settings.DB_POOL_TIMEOUT,
        pool_recycle=settings.DB_POOL_RECYCLE,
        pool_pre_ping=True,
        echo=settings.DB_ECHO,
        future=True,
    )

engine: Engine = _build_engine()
SessionLocal: sessionmaker[Session] = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False, class_=Session)

def get_db() -> Generator[Session, None, None]:
    db: Session = SessionLocal()
    try:
        yield db
    except SQLAlchemyError as exc:
        db.rollback(); raise
    except Exception as exc:
        db.rollback(); raise
    finally:
        db.close()

def check_db_connection() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("DB connectivity OK")
        return True
    except OperationalError as exc:
        logger.critical("DB connectivity FAILED: %s", exc)
        return False
