"""
services/auth-service/app/db/session.py
-----------------------------------------
SQLAlchemy engine, session factory, and FastAPI DB dependency.
Supports automatic local SQLite fallback if PostgreSQL is unreachable.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool, StaticPool

from app.core.config import settings

logger = logging.getLogger(__name__)


def _build_engine() -> Engine:
    if settings.DATABASE_URL and "postgresql" in settings.DATABASE_URL:
        try:
            # Test PostgreSQL connectivity with quick timeout
            test_eng = create_engine(
                url=settings.DATABASE_URL,
                pool_pre_ping=True,
                connect_args={"connect_timeout": 3},
            )
            with test_eng.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("Connected to PostgreSQL successfully.")
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
        except Exception as exc:
            logger.warning("PostgreSQL connection failed (%s). Falling back to SQLite.", exc)

    # SQLite Fallback
    db_name = getattr(settings, "POSTGRES_DB", "career_auth")
    db_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    db_path = os.path.join(db_dir, f"{db_name}.db")
    logger.info("Using SQLite fallback at: %s", db_path)
    return create_engine(
        url=f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        echo=settings.DB_ECHO,
        future=True,
    )


engine: Engine = _build_engine()

SessionLocal: sessionmaker[Session] = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    class_=Session,
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI Depends-compatible session generator."""
    db: Session = SessionLocal()
    try:
        logger.debug("DB session opened.")
        yield db
    except SQLAlchemyError as exc:
        logger.error("DB error — rolling back: %s", exc, exc_info=True)
        db.rollback()
        raise
    except Exception as exc:
        logger.warning("Non-DB exception — rolling back: %s", exc, exc_info=True)
        db.rollback()
        raise
    finally:
        db.close()
        logger.debug("DB session closed.")


def check_db_connection() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("DB connectivity OK ✓")
        return True
    except Exception as exc:
        logger.critical("DB connectivity FAILED: %s", exc)
        return False

