"""Database bootstrap with automatic DB creation for local PostgreSQL."""
from __future__ import annotations
import logging
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from app.core.config import settings
from app.db.base import Base
from app.db.session import check_db_connection, engine

logger = logging.getLogger(__name__)

def _ensure_postgres_db_exists() -> None:
    try:
        conn = psycopg2.connect(
            host=settings.POSTGRES_SERVER,
            port=settings.POSTGRES_PORT,
            user=settings.POSTGRES_USER,
            password=settings.POSTGRES_PASSWORD,
            dbname="postgres",
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s;", (settings.POSTGRES_DB,))
        exists = cur.fetchone()
        if not exists:
            cur.execute(f'CREATE DATABASE "{settings.POSTGRES_DB}";')
            logger.info("Created PostgreSQL database '%s'", settings.POSTGRES_DB)
        cur.close()
        conn.close()
    except Exception as exc:
        logger.warning("Auto database creation note: %s", exc)

def initialize_database() -> None:
    try:
        _ensure_postgres_db_exists()
        if check_db_connection():
            Base.metadata.create_all(bind=engine)
            logger.info("Database tables created/verified ✓")
        else:
            logger.warning("Database offline — service starting without DB auto-creation.")
    except Exception as exc:
        logger.warning("Database initialization note: %s", exc)
