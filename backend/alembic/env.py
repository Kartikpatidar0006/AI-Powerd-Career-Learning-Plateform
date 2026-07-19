"""
backend/alembic/env.py
-----------------------
Alembic migration environment — production-ready configuration.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT THIS FILE DOES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. Loads DATABASE_URL from app.core.config (pydantic-settings / .env).
   → No credentials are hardcoded in alembic.ini or this file.

2. Imports Base from app.db.base — which triggers all model imports,
   making every table visible to autogenerate.
   → `alembic revision --autogenerate` detects schema changes automatically.

3. Supports both Alembic run modes:
   • OFFLINE — generates raw SQL migration script without a live DB connection.
   • ONLINE  — connects to the DB and runs migrations directly using
               SQLAlchemy 2.x `create_engine()` (not the deprecated
               `engine_from_config()` helper from Alembic 1.x).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DESIGN DECISIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• NullPool is used for the migration engine.
  Alembic is a short-lived CLI process — it must open one connection, run
  migrations, and close cleanly.  QueuePool (used by the app server) would
  keep connections alive unnecessarily.

• create_engine() is called directly instead of engine_from_config().
  engine_from_config() is an Alembic 1.x convenience that reconstructs
  an engine from alembic.ini keys.  Calling create_engine() directly with
  the URL from pydantic settings gives us full control and avoids the
  ini-parsing indirection entirely.

• compare_server_default=True enables detection of server-side DEFAULT
  value changes (e.g., adding `DEFAULT now()` to a column).

• render_as_batch=False (default).  Set to True only if you need SQLite
  support (e.g., unit-test databases).  PostgreSQL supports ALTER TABLE
  directly, so batch mode is unnecessary and adds overhead.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
COMMON COMMANDS (run from backend/ directory)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  # Create a new auto-generated migration after editing models:
  .\\venv\\Scripts\\alembic revision --autogenerate -m "describe your change"

  # Apply all pending migrations to the database:
  .\\venv\\Scripts\\alembic upgrade head

  # Roll back the last migration:
  .\\venv\\Scripts\\alembic downgrade -1

  # Downgrade to a specific revision:
  .\\venv\\Scripts\\alembic downgrade <revision_id>

  # View current migration status:
  .\\venv\\Scripts\\alembic current

  # View full migration history:
  .\\venv\\Scripts\\alembic history --verbose

  # Generate offline SQL script (no live DB required):
  .\\venv\\Scripts\\alembic upgrade head --sql > migration.sql
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

# ── Add backend/ to sys.path so `app.*` imports resolve correctly ─────────── #
# Alembic executes env.py as a plain script from the alembic/ subdirectory.
# Without this, Python cannot locate the `app` package.
# os.path.dirname twice: alembic/ → backend/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── Load project settings (reads .env automatically via pydantic-settings) ── #
# Must happen AFTER sys.path is patched.
from app.core.config import settings  # noqa: E402

# ── Import Base — side-effect: registers ALL models into Base.metadata ─────── #
# This is the critical step for `--autogenerate` to work.
# Every model file is imported inside app/db/base.py.  If a model is not
# listed there, Alembic will not detect its table and will silently miss
# schema changes for that table.
from app.db.base import Base  # noqa: E402, F401


# =========================================================================== #
#  Alembic config object                                                        #
# =========================================================================== #

# `config` gives access to alembic.ini values and Alembic's runtime context.
config = context.config

# ── Inject DATABASE_URL from pydantic settings ────────────────────────────── #
# This overrides the (commented-out) sqlalchemy.url in alembic.ini at runtime,
# keeping credentials out of version control entirely.
# Guard: settings.DATABASE_URL is assembled by a model_validator and is
# guaranteed non-None at this point, but we assert for defensive safety.
_db_url: str = settings.DATABASE_URL  # type: ignore[assignment]
if not _db_url:
    raise RuntimeError(
        "DATABASE_URL is not set.  "
        "Ensure your .env file contains POSTGRES_* variables or DATABASE_URL."
    )

config.set_main_option("sqlalchemy.url", _db_url)

# ── Set up Python logging from alembic.ini [loggers] section ─────────────── #
# Only configure if the ini file is present (it is when running via the CLI).
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ── MetaData object Alembic inspects to detect schema differences ────────── #
# Must reference Base.metadata (not None) for --autogenerate to work.
target_metadata = Base.metadata


# =========================================================================== #
#  Shared context.configure() options                                           #
# =========================================================================== #

def _get_configure_kwargs() -> dict:
    """
    Return the shared keyword arguments passed to context.configure() in both
    offline and online modes.

    Centralising these options in one place ensures offline SQL output and
    online migration runs behave identically — a common source of production
    surprises when the two diverge.

    Options explained
    -----------------
    target_metadata
        The MetaData Alembic diffs against the live DB schema.

    compare_server_default
        Detect changes to server-side DEFAULT values
        (e.g., adding `server_default="now()"` to a column).
        Without this, Alembic silently ignores DEFAULT changes.

    render_as_batch
        Required for SQLite (which cannot ALTER TABLE directly).
        Set to False for PostgreSQL — batch mode adds a costly table-copy
        step that is unnecessary when the DB supports ALTER TABLE natively.
        Flip to True if you introduce an SQLite test fixture.

    include_schemas
        Set to True only if you use multiple PostgreSQL schemas
        (e.g., `public` + `analytics`).  False keeps autogenerate
        focused on the default search_path schema.
    """
    return {
        "target_metadata": target_metadata,
        "compare_server_default": True,
        "render_as_batch": False,
        "include_schemas": False,
    }


# =========================================================================== #
#  Offline migrations                                                           #
# =========================================================================== #

def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    Generates raw SQL migration statements without connecting to the database.
    Useful for:
      • Reviewing what SQL will be executed before applying it.
      • Generating scripts for DBAs to apply manually in production.
      • CI environments where no live DB is available.

    In offline mode the URL is read from the main config option (which was
    injected above from pydantic settings) and passed directly to
    context.configure().  No Engine or Connection object is created.

    Usage:
        .\\venv\\Scripts\\alembic upgrade head --sql > migration.sql
        .\\venv\\Scripts\\alembic downgrade -1 --sql >> rollback.sql
    """
    url = config.get_main_option("sqlalchemy.url")

    context.configure(
        url=url,
        literal_binds=True,         # Render bind params as literals in SQL output.
        dialect_opts={"paramstyle": "named"},
        **_get_configure_kwargs(),
    )

    with context.begin_transaction():
        context.run_migrations()


# =========================================================================== #
#  Online migrations                                                            #
# =========================================================================== #

def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode.

    Creates a live connection to the database and applies migrations directly.
    This is the standard mode used during development and in CI/CD pipelines.

    Why create_engine() instead of engine_from_config()?
    ----------------------------------------------------
    engine_from_config() is an Alembic 1.x convenience that reconstructs
    an Engine from alembic.ini key-value pairs.  It has two drawbacks:
      1. It hides configuration — you cannot see what kwargs are passed.
      2. It re-reads alembic.ini at runtime, creating a second source of
         truth that can drift from the app's own settings.

    Calling create_engine() directly means:
      • The URL comes from pydantic settings (the single source of truth).
      • NullPool is set explicitly — no accidental connection pooling.
      • future=True explicitly opts into the SQLAlchemy 2.x query API.

    Why NullPool?
    -------------
    Alembic is a short-lived CLI process.  It needs exactly one connection,
    runs all pending migrations, then exits.  QueuePool would keep connections
    alive after the migration completes, preventing clean process termination.
    NullPool ensures: open → migrate → close, with no lingering connections.
    """
    # Build a dedicated, single-use engine for the migration run.
    # This engine is completely independent of the app's QueuePool engine
    # defined in app/db/session.py.
    connectable = create_engine(
        url=_db_url,
        poolclass=pool.NullPool,   # No connection pooling for CLI tools.
        future=True,               # SQLAlchemy 2.x API.
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            **_get_configure_kwargs(),
        )

        with context.begin_transaction():
            context.run_migrations()


# =========================================================================== #
#  Entry point — Alembic calls this file directly                               #
# =========================================================================== #

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
