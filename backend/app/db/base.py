"""
backend/app/db/base.py
-----------------------
SQLAlchemy declarative Base and Alembic model registry.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHY THIS FILE EXISTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SQLAlchemy's ORM works by maintaining a registry that maps Python classes
to database tables.  That registry is anchored to `Base.metadata`.

Two things must happen for the full picture to work:

  1. DEFINE Base  — one canonical `DeclarativeBase` subclass for the whole
                    project.  Every ORM model class inherits from it.

  2. POPULATE metadata — before Alembic's `autogenerate` (or SQLAlchemy's
                    `create_all`) can "see" a table, the corresponding model
                    class must have been *imported* into the running process.
                    Python never imports a file it hasn't been asked to import.

This file satisfies both requirements:

  ┌─ base.py ──────────────────────────────────────────────────────────────┐
  │  class Base(DeclarativeBase): ...          ← single source of truth    │
  │                                                                         │
  │  from app.models.user import User          ← populates Base.metadata   │
  │  from app.models.profession import ...     ← add one line per model    │
  └─────────────────────────────────────────────────────────────────────────┘

  alembic/env.py imports `Base` from here  →  autogenerate sees all tables.
  app/db/init_db.py imports `Base` from here → create_all sees all tables.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ARCHITECTURE NOTE — why Base is NOT in session.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
session.py  = infrastructure concern  (engine, pool, sessions, get_db)
base.py     = schema concern          (table metadata, model registry)

Keeping them separate avoids circular imports: models import Base from
base.py, and base.py imports model *modules* — if Base lived in session.py
and models also imported session.py for get_db, Python would detect a cycle.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HOW TO ADD A NEW MODEL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. Create  backend/app/models/my_model.py
2. Define  class MyModel(Base): ...
3. Add one line at the bottom of this file:
       from app.models.my_model import MyModel  # noqa: F401
   The `# noqa: F401` suppresses the "imported but unused" linter warning —
   the import is intentional: its side-effect registers the table.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


# =========================================================================== #
#  Declarative Base — single definition for the entire project                 #
# =========================================================================== #

class Base(DeclarativeBase):
    """
    Project-wide SQLAlchemy ORM base class (SQLAlchemy 2.x style).

    All ORM models must subclass this — never instantiate Base directly.

    Why `DeclarativeBase` (SQLAlchemy 2.x) instead of the legacy factory?
    -----------------------------------------------------------------------
    SQLAlchemy 2.0 replaced the module-level `declarative_base()` factory
    with a proper class-based API.  Subclassing `DeclarativeBase` gives:

      • Native support for `Mapped[T]` / `mapped_column()` type annotations,
        enabling full IDE type inference on column attributes.
      • A single `Base.metadata` object that Alembic uses as the source of
        truth for all table definitions.
      • Easier customisation via `__init_subclass__` and class-level mixins.

    SQLAlchemy 1.x users: replace `DeclarativeBase` with:
        from sqlalchemy.orm import declarative_base
        Base = declarative_base()
    (but do upgrade — 1.x is EOL)
    """

    # No extra configuration needed here.
    # Add class-level mixins or __abstract__ = True helpers in
    # app/db/mixins.py and have models inherit from both Base and the mixin.
    pass


# =========================================================================== #
#  Model registry — Alembic autogenerate requires all models to be imported   #
# =========================================================================== #
#
# Rule: Add ONE import per model file, BELOW this comment block.
# Keep imports alphabetically sorted within each feature group for readability.
#
# The `# noqa: F401` comment on each line tells linters (flake8, ruff, pylint)
# that the import is intentional even though the name is never used directly
# in this file — its side-effect (registering the ORM class with Base.metadata)
# is the entire point.
#
# ──────────────────────────────────────────────────────────────────────────── #
# CURRENT MODELS                                                               #
# (Uncomment / add each line as the corresponding model file is created)       #
# ──────────────────────────────────────────────────────────────────────────── #
#
# Auth / Users
from app.models.user import User                          # noqa: F401

# Roles
from app.models.role import Role                            # noqa: F401
#
# Career
# from app.models.profession import Profession              # noqa: F401
#
# Learning
# from app.models.task import Task                          # noqa: F401
# from app.models.resume import Resume                      # noqa: F401
#
# Interviews
# from app.models.interview import Interview                # noqa: F401
#
# AI / Sessions
# from app.models.ai_session import AISession               # noqa: F401
#
# Dashboard
# from app.models.dashboard_metric import DashboardMetric  # noqa: F401
