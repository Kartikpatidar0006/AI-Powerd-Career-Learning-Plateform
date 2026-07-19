"""
backend/app/db/session.py
--------------------------
SQLAlchemy 2.x engine, session factory, and FastAPI DB dependency.

Architecture role (Clean Architecture):
    Infrastructure layer — this module is the only place that knows how
    to physically connect to PostgreSQL.  All higher layers (repositories,
    services, routes) receive a `Session` object via dependency injection
    and never import the engine directly.

What this module provides:
    engine        — SQLAlchemy Engine configured with QueuePool.
    SessionLocal  — Session factory (sessionmaker) bound to the engine.
    get_db()      — FastAPI Depends-compatible generator that yields a
                    scoped, transactional session per HTTP request.

Connection pool choice — QueuePool:
    QueuePool is SQLAlchemy's default (and most production-tested) pool
    implementation.  It maintains a fixed number of persistent connections
    (`pool_size`) and allows a configurable burst capacity (`max_overflow`).
    It is the right choice for PostgreSQL workloads where each request is
    short-lived and connections are expensive to create.

    NullPool (for serverless / Lambda):
        Use `poolclass=NullPool` and set DB_POOL_SIZE=0 if deploying to a
        stateless environment.  Switch by changing one import here.
"""

from __future__ import annotations

import logging
from collections.abc import Generator
from typing import Any

from sqlalchemy import URL, create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool

from app.core.config import settings

logger = logging.getLogger(__name__)


# =========================================================================== #
#  Engine                                                                       #
# =========================================================================== #

def _build_engine() -> Engine:
    """
    Construct and return a production-grade SQLAlchemy Engine.

    All configuration values are pulled from `settings` (app/core/config.py)
    so that nothing is hardcoded here and changes only require updating .env.

    Raises:
        ValueError: If DATABASE_URL is not set in settings.
        OperationalError: If the initial connectivity check fails.
    """
    if not settings.DATABASE_URL:
        raise ValueError(
            "DATABASE_URL is not configured.  "
            "Check your .env file or POSTGRES_* environment variables."
        )

    logger.debug(
        "Creating SQLAlchemy engine | pool_size=%d | max_overflow=%d | "
        "pool_timeout=%ds | pool_recycle=%ds",
        settings.DB_POOL_SIZE,
        settings.DB_MAX_OVERFLOW,
        settings.DB_POOL_TIMEOUT,
        settings.DB_POOL_RECYCLE,
    )

    engine: Engine = create_engine(
        # ── Connection target ──────────────────────────────────────────── #
        url=settings.DATABASE_URL,

        # ── Pool configuration (QueuePool is the explicit choice) ──────── #
        # QueuePool keeps `pool_size` connections alive and allows up to
        # `pool_size + max_overflow` connections during traffic spikes.
        poolclass=QueuePool,
        pool_size=settings.DB_POOL_SIZE,        # persistent connections
        max_overflow=settings.DB_MAX_OVERFLOW,  # burst connections
        pool_timeout=settings.DB_POOL_TIMEOUT,  # seconds to wait for a slot
        pool_recycle=settings.DB_POOL_RECYCLE,  # recycle age (avoids stale conns)

        # ── Reliability ────────────────────────────────────────────────── #
        # Execute "SELECT 1" before handing a connection to the app.
        # Transparently handles DB restarts, firewall resets, and idle timeouts
        # with no visible error to the caller.
        pool_pre_ping=True,

        # ── Observability ──────────────────────────────────────────────── #
        # DB_ECHO=True logs every SQL statement — useful in development,
        # must be False in production to avoid sensitive data in logs.
        echo=settings.DB_ECHO,

        # ── SQLAlchemy 2.x compatibility ───────────────────────────────── #
        # future=True opts into the 2.0-style API (required for SQLAlchemy ≥2).
        future=True,
    )

    return engine


# Module-level engine singleton.
# All SessionLocal instances share this engine and its connection pool.
engine: Engine = _build_engine()


# ── Optional: listen for pool checkout events for logging ─────────────────── #
@event.listens_for(engine, "connect")
def _on_connect(dbapi_connection: Any, connection_record: Any) -> None:
    """
    Fired once per new physical database connection being established.
    Use this hook for connection-level setup (e.g., setting search_path,
    registering custom types, or emitting a connect log).
    """
    logger.debug("New DB connection opened: %s", connection_record)


@event.listens_for(engine, "checkout")
def _on_checkout(
    dbapi_connection: Any,
    connection_record: Any,
    connection_proxy: Any,
) -> None:
    """
    Fired every time a connection is checked out of the pool for use.
    Useful for metrics (connection acquisition count, pool utilisation).
    """
    logger.debug("DB connection checked out from pool.")


# =========================================================================== #
#  Session Factory                                                              #
# =========================================================================== #

SessionLocal: sessionmaker[Session] = sessionmaker(
    bind=engine,

    # ── Transaction control ────────────────────────────────────────────── #
    # autocommit=False: every write must be committed explicitly.
    # This gives the application full transactional control and makes
    # rollbacks on errors deterministic.
    autocommit=False,

    # ── Flush control ─────────────────────────────────────────────────── #
    # autoflush=False: SQLAlchemy will NOT automatically flush pending
    # changes before executing a query.  This prevents subtle bugs in
    # multi-step business logic where partial state might be flushed
    # prematurely.  Flush explicitly or let get_db() handle commit.
    autoflush=False,

    # ── Post-commit attribute access ───────────────────────────────────── #
    # expire_on_commit=False: after a commit, ORM attribute access does NOT
    # trigger a lazy-load SELECT.  This is essential in service layers that
    # access model attributes after committing and before the session closes.
    expire_on_commit=False,

    # Explicitly target the Session class (not async variants).
    class_=Session,
)


# =========================================================================== #
#  FastAPI Dependency                                                           #
# =========================================================================== #

def get_db() -> Generator[Session, None, None]:
    """
    Yield a database session scoped to a single HTTP request.

    Lifecycle per request:
        1. Open  — a Session is obtained from SessionLocal (which pulls a
                   connection from QueuePool).
        2. Yield — the session is injected into the route handler via
                   FastAPI's `Depends(get_db)`.
        3. Happy path — if the handler returns normally, the session is
                        committed and then closed.
        4. Error path — if any exception escapes the handler, the session
                        is rolled back before closing, keeping the DB clean.
        5. Close — the connection is returned to QueuePool for reuse.

    Usage in a route handler:
        from fastapi import APIRouter, Depends
        from sqlalchemy.orm import Session
        from app.db.session import get_db

        router = APIRouter()

        @router.get("/items")
        def list_items(db: Session = Depends(get_db)):
            return db.execute(select(Item)).scalars().all()

    Usage in a service / repository (preferred pattern):
        Pass the session received from the route into the service class
        or repository function — never call SessionLocal() directly in
        business-logic code.

    Raises:
        SQLAlchemyError: Re-raised after rollback so FastAPI's exception
                         handlers can return an appropriate HTTP response.
    """
    db: Session = SessionLocal()
    try:
        logger.debug("DB session opened.")
        yield db
        db.commit()
        logger.debug("DB session committed.")
    except SQLAlchemyError as exc:
        logger.error(
            "DB error — rolling back session. Reason: %s",
            exc,
            exc_info=True,
        )
        db.rollback()
        raise
    except Exception as exc:
        # Catch non-SQLAlchemy exceptions (e.g., Pydantic validation errors
        # inside service code) and still ensure the session is rolled back.
        logger.warning(
            "Non-DB exception inside DB session — rolling back. Reason: %s",
            exc,
            exc_info=True,
        )
        db.rollback()
        raise
    finally:
        db.close()
        logger.debug("DB session closed.")


# =========================================================================== #
#  Health-check utility (used by init_db and /health endpoint)                 #
# =========================================================================== #

def check_db_connection() -> bool:
    """
    Verify that the database is reachable by running a lightweight query.

    Returns:
        True  — database is healthy and accepting connections.
        False — database is unreachable or returned an error.

    Usage:
        from app.db.session import check_db_connection

        if not check_db_connection():
            raise RuntimeError("Database unreachable at startup.")
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Database connectivity check: OK ✓")
        return True
    except OperationalError as exc:
        logger.critical(
            "Database connectivity check FAILED. "
            "Verify DATABASE_URL and that PostgreSQL is running. Error: %s",
            exc,
        )
        return False
