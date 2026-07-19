"""
backend/app/db/init_db.py
--------------------------
Database bootstrap — connection verification, schema creation, and seeding.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT THIS FILE DOES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. HEALTH CHECK
   Runs `SELECT 1` against the engine before anything else.  If the database
   is unreachable the process exits immediately with a clear log message
   rather than starting up and silently failing on every request.

2. SCHEMA BOOTSTRAP  (non-production only)
   Calls `Base.metadata.create_all()` which issues `CREATE TABLE IF NOT
   EXISTS` for every table registered in Base.metadata.  The call is safe
   to make on every startup — it is idempotent.

   In PRODUCTION the schema is owned exclusively by Alembic migrations.
   `create_all` is skipped and an INFO log reminds the operator to run:
       alembic upgrade head

3. MODEL DISCOVERY
   Importing `Base` from `app.db.base` triggers all model imports declared
   at the bottom of that file.  Every ORM class registers its `Table` with
   `Base.metadata` as a side-effect of being imported.  If a model is NOT
   imported here (via base.py), neither Alembic autogenerate nor `create_all`
   will know that table exists.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
IMPORT CHAIN
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   init_db.py
     ├── app.db.base  → Base (+ all model side-effect imports)
     ├── app.db.session → engine
     └── app.core.config → settings

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CALLER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   app/main.py lifespan hook:
       from app.db.init_db import initialize_database
       initialize_database()
"""

from __future__ import annotations

import logging
from typing import Final

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError, ProgrammingError, SQLAlchemyError

# ── Import Base first — this triggers every model import registered at the
#    bottom of base.py, populating Base.metadata with all table definitions.
from app.db.base import Base  # noqa: F401 (side-effect: model registration)

# ── Import the engine from session.py — single source of DB connectivity.
from app.db.session import engine

# ── Settings for environment-gated logic.
from app.core.config import settings

logger: logging.Logger = logging.getLogger(__name__)

# Log prefix for visual grouping in startup logs.
_BANNER: Final[str] = "─" * 60


# =========================================================================== #
#  Public API                                                                   #
# =========================================================================== #

def initialize_database() -> None:
    """
    Bootstrap the database at application startup.

    Steps
    -----
    1. Verify the DB connection is alive (raises on failure).
    2. Log the tables registered in Base.metadata (model discovery audit).
    3. Create missing tables in non-production environments.
    4. Log final status.

    This function is **idempotent** — calling it multiple times is safe.
    It will never drop or alter existing tables.

    Raises
    ------
    OperationalError
        If the PostgreSQL server is unreachable or rejects the connection.
    SQLAlchemyError
        If `create_all` fails due to a schema conflict or permission issue.
    RuntimeError
        If DATABASE_URL is not configured.
    """
    logger.info(_BANNER)
    logger.info("  DATABASE INITIALISATION — starting")
    logger.info(_BANNER)

    _verify_connection(engine)
    _log_registered_tables()

    if settings.ENVIRONMENT == "production":
        _skip_create_all_production()
    else:
        _create_tables(engine)

    logger.info(_BANNER)
    logger.info("  DATABASE INITIALISATION — complete ✓")
    logger.info(_BANNER)


def drop_all_tables() -> None:
    """
    Drop **every** table tracked by Base.metadata.

    .. warning::
        This permanently and irreversibly destroys all data.
        Intended **only** for test teardown or local development resets.
        Raises ``RuntimeError`` if called in a production environment.

    Raises
    ------
    RuntimeError
        If ``ENVIRONMENT == "production"``.
    SQLAlchemyError
        If the drop operation fails at the DB level.
    """
    if settings.ENVIRONMENT == "production":
        raise RuntimeError(
            "drop_all_tables() must NEVER be called in a production environment. "
            "Use Alembic's downgrade commands to manage schema changes safely."
        )

    tables = list(Base.metadata.tables.keys())
    logger.warning(
        "⚠️  Dropping ALL tables in environment '%s': %s",
        settings.ENVIRONMENT,
        tables,
    )

    try:
        Base.metadata.drop_all(bind=engine)
    except SQLAlchemyError as exc:
        logger.error("Failed to drop tables: %s", exc, exc_info=True)
        raise

    logger.warning("All tables dropped successfully in '%s'.", settings.ENVIRONMENT)


def get_registered_tables() -> list[str]:
    """
    Return the names of all tables currently registered in Base.metadata.

    Useful for health-check endpoints or startup audits.

    Returns
    -------
    list[str]
        Sorted list of table names known to SQLAlchemy metadata.
        Note: this reflects what *Python* knows about, not what actually
        exists in the database.  Use ``get_existing_tables()`` for the latter.
    """
    return sorted(Base.metadata.tables.keys())


def get_existing_tables() -> list[str]:
    """
    Return the names of tables that physically exist in the database.

    This queries the DB's information schema via SQLAlchemy's Inspector —
    it reflects the *actual* state of the database, not just metadata.

    Returns
    -------
    list[str]
        Sorted list of table names found in the connected PostgreSQL database.

    Raises
    ------
    OperationalError
        If the database connection fails during inspection.
    """
    try:
        inspector = inspect(engine)
        return sorted(inspector.get_table_names())
    except OperationalError as exc:
        logger.error(
            "Could not inspect database tables: %s", exc, exc_info=True
        )
        raise


# =========================================================================== #
#  Private helpers                                                              #
# =========================================================================== #

def _verify_connection(eng: Engine) -> None:
    """
    Execute a lightweight ``SELECT 1`` to confirm the database is reachable.

    Parameters
    ----------
    eng:
        The SQLAlchemy engine to test.

    Raises
    ------
    OperationalError
        If the PostgreSQL server is unreachable, credentials are wrong, or
        the database does not exist.
    RuntimeError
        If the engine's URL is not set.
    """
    logger.info("  [1/3] Verifying database connection...")

    if not settings.DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL is not configured. "
            "Check your .env file or POSTGRES_* environment variables."
        )

    try:
        with eng.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.close()

        logger.info(
            "  [1/3] Connection OK ✓ — %s:%s/%s",
            settings.POSTGRES_SERVER,
            settings.POSTGRES_PORT,
            settings.POSTGRES_DB,
        )

    except OperationalError as exc:
        logger.critical(
            "  [1/3] ✗ Cannot connect to the database.\n"
            "        Host    : %s:%s\n"
            "        Database: %s\n"
            "        User    : %s\n"
            "        Error   : %s\n"
            "        → Check that PostgreSQL is running and credentials are correct.",
            settings.POSTGRES_SERVER,
            settings.POSTGRES_PORT,
            settings.POSTGRES_DB,
            settings.POSTGRES_USER,
            exc,
        )
        raise

    except SQLAlchemyError as exc:
        logger.critical(
            "  [1/3] ✗ Unexpected SQLAlchemy error during connection check: %s",
            exc,
            exc_info=True,
        )
        raise


def _log_registered_tables() -> None:
    """
    Audit and log every table registered in Base.metadata.

    This is purely informational — it shows which models have been imported
    and are therefore known to SQLAlchemy.  If a table is missing here, its
    model was not imported in ``app/db/base.py``.
    """
    tables = get_registered_tables()
    count = len(tables)

    logger.info("  [2/3] ORM model registry — %d table(s) found in metadata:", count)

    if count == 0:
        logger.warning(
            "  [2/3] ⚠  No tables registered in Base.metadata.\n"
            "        → Add model imports to app/db/base.py to register tables."
        )
    else:
        for table_name in tables:
            logger.info("        • %s", table_name)


def _create_tables(eng: Engine) -> None:
    """
    Create all tables defined in Base.metadata that do not yet exist.

    Uses ``checkfirst=True`` (the default) so SQLAlchemy emits
    ``CREATE TABLE IF NOT EXISTS`` — existing tables are never touched.

    Parameters
    ----------
    eng:
        The SQLAlchemy engine to use for DDL execution.

    Raises
    ------
    ProgrammingError
        If a schema conflict (e.g., type mismatch) prevents table creation.
    SQLAlchemyError
        For any other database-level failure.
    """
    logger.info(
        "  [3/3] Creating missing tables (environment: '%s')...",
        settings.ENVIRONMENT,
    )

    registered = get_registered_tables()

    if not registered:
        logger.warning(
            "  [3/3] No tables in metadata — nothing to create.\n"
            "        Register models in app/db/base.py and restart."
        )
        return

    try:
        # checkfirst=True (default) → CREATE TABLE IF NOT EXISTS per table.
        # This is safe to call on every startup.
        Base.metadata.create_all(bind=eng, checkfirst=True)

        # Post-creation audit: compare metadata vs actual DB tables.
        existing = get_existing_tables()
        created = [t for t in registered if t in existing]
        missing = [t for t in registered if t not in existing]

        logger.info(
            "  [3/3] Table sync complete ✓ — %d/%d tables confirmed in DB:",
            len(created),
            len(registered),
        )
        for table_name in created:
            logger.info("        ✓ %s", table_name)

        if missing:
            logger.warning(
                "  [3/3] ⚠  %d table(s) in metadata but NOT found in DB "
                "(possible DDL issue): %s",
                len(missing),
                missing,
            )

    except ProgrammingError as exc:
        logger.error(
            "  [3/3] Schema conflict while creating tables: %s\n"
            "        → This may indicate a column type mismatch between "
            "your models and an existing table. Consider running Alembic.",
            exc,
            exc_info=True,
        )
        raise

    except SQLAlchemyError as exc:
        logger.error(
            "  [3/3] Unexpected error during table creation: %s",
            exc,
            exc_info=True,
        )
        raise


def _skip_create_all_production() -> None:
    """
    Log the appropriate message when running in production.

    Production schema changes must go through Alembic migration files only.
    This function makes the skip explicit and visible in startup logs.
    """
    existing = []
    try:
        existing = get_existing_tables()
    except OperationalError:
        pass  # Already raised in _verify_connection; don't duplicate.

    logger.info(
        "  [3/3] Environment is 'production' — auto table creation SKIPPED.\n"
        "        Schema is managed exclusively by Alembic migrations.\n"
        "        → Run: alembic upgrade head\n"
        "        DB currently has %d table(s): %s",
        len(existing),
        existing,
    )
